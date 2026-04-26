from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any

from core.models import NormalizedProduct, RawProduct
from db.database import Database

logger = logging.getLogger(__name__)

class ProductRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_product_by_url(self, url: str) -> Optional[Any]:
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT * FROM products WHERE url = ?", (url,)
        ).fetchone()
        if not row: return None
        
        specs_row = conn.execute(
            "SELECT raw_specs_json FROM product_specs WHERE product_id = ?", (row["id"],)
        ).fetchone()
        
        raw_specs = {}
        if specs_row and specs_row["raw_specs_json"]:
            try:
                raw_specs = json.loads(specs_row["raw_specs_json"])
            except: pass
            
        from dataclasses import dataclass
        @dataclass
        class SimpleProduct:
            url: str
            raw_specs: dict
            product_type: Optional[str]
        
        return SimpleProduct(url=row["url"], raw_specs=raw_specs, product_type=row["product_type"])

    def upsert_product(self, product: RawProduct, session_id: str) -> tuple[int, bool, Optional[float]]:
        conn = self.db.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        existing = conn.execute(
            """
            SELECT p.id, ph.price
            FROM products p
            LEFT JOIN price_history ph ON ph.product_id = p.id
            WHERE p.url = ?
            ORDER BY ph.scraped_at DESC
            LIMIT 1
            """,
            (product.url,),
        ).fetchone()

        is_new = existing is None
        old_price = None if is_new else float(existing["price"]) if existing["price"] is not None else None
        
        if is_new:
            cursor = conn.execute(
                """
                INSERT INTO products (
                    url, marketplace, title, brand, model, category_path, product_type,
                    image_url, description, first_seen_at, last_seen_at, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    product.url,
                    product.marketplace,
                    product.title,
                    product.brand,
                    product.model,
                    product.category_path,
                    None,
                    product.image_url,
                    product.description,
                    now,
                    now,
                ),
            )
            product_id = int(cursor.lastrowid)
            logger.info("New product found: %s", product.url)
        else:
            product_id = int(existing["id"])
            conn.execute(
                """
                UPDATE products
                SET title = ?, brand = ?, model = ?, category_path = ?,
                    image_url = ?, description = ?, last_seen_at = ?, is_active = 1
                WHERE id = ?
                """,
                (
                    product.title,
                    product.brand,
                    product.model,
                    product.category_path,
                    product.image_url,
                    product.description,
                    now,
                    product_id,
                ),
            )
            if old_price != product.price:
                logger.info("Price change for %s: %s -> %s", product.url, old_price, product.price)

        if product.price is not None:
            conn.execute(
                """
                INSERT INTO price_history (
                    product_id, price, currency, availability, scraped_at, scrape_session
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    product.price,
                    product.currency or "UAH",
                    product.availability or "InStock",
                    product.scraped_at.isoformat(),
                    session_id,
                ),
            )
        
        if hasattr(product, 'raw_specs') and product.raw_specs:
             self._save_raw_specs(product_id, product.raw_specs)

        conn.commit()
        # B4 fix: guard both sides — delta is only meaningful when both prices exist
        if old_price is not None and product.price is not None:
            delta = float(product.price) - old_price
        else:
            delta = None
        return product_id, is_new, delta

    def _save_raw_specs(self, product_id: int, specs: dict) -> None:
        conn = self.db.get_connection()
        # B23 fix: removed redundant double-serialization of same data
        specs_str = json.dumps(specs, ensure_ascii=False)
        conn.execute(
            """
            INSERT OR REPLACE INTO product_specs (
                product_id, schema_version, specs_json, raw_specs_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                product_id,
                "1.2",
                specs_str,
                specs_str,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        
        conn.execute(
            """
            UPDATE products
            SET norm_brand = ?, norm_model = ?, norm_voltage = ?, 
                norm_capacity = ?, norm_category = ?, is_relevant = ?
            WHERE id = ?
            """,
            (
                specs.get("Brand"),
                specs.get("Model"),
                specs.get("Voltage"),
                specs.get("Capacity"),
                specs.get("Category"),
                1 if specs.get("is_relevant", True) else 0,
                product_id
            )
        )
        conn.commit()

    def save_specs(self, product_id: int, normalized: NormalizedProduct) -> None:
        self._save_raw_specs(product_id, normalized.normalized_specs)

    def get_products_by_query(self, query: str, marketplace: str | None = None) -> list[dict]:
        return self.search_products(query, filters={"marketplace": marketplace} if marketplace else None)

    def get_price_history(self, product_id: int) -> list[dict]:
        conn = self.db.get_connection()
        rows = conn.execute("SELECT * FROM price_history WHERE product_id = ? ORDER BY scraped_at ASC", (product_id,)).fetchall()
        return [dict(row) for row in rows]

    def search_products(self, query: str = "", filters: dict | None = None) -> list[dict]:
        conn = self.db.get_connection()
        filters = filters or {}
        
        sql = """
            SELECT p.*, ph.price, ph.currency, ph.scraped_at as latest_scraped_at
            FROM products p
            LEFT JOIN (
                SELECT product_id, price, currency, scraped_at,
                       ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY scraped_at DESC) as rn
                FROM price_history
            ) ph ON p.id = ph.product_id AND ph.rn = 1
            WHERE 1=1
        """
        params: list = []

        if query:
            sql += " AND (p.title LIKE ? OR p.norm_brand LIKE ? OR p.norm_model LIKE ?)"
            p = f"%{query}%"
            params.extend([p, p, p])

        if filters.get("marketplace"):
            sql += " AND p.marketplace = ?"
            params.append(filters["marketplace"])

        if filters.get("product_type"):
            sql += " AND p.product_type = ?"
            params.append(filters["product_type"])

        if filters.get("is_relevant") is not None:
            sql += " AND p.is_relevant = ?"
            params.append(1 if filters["is_relevant"] else 0)

        sql += " ORDER BY p.last_seen_at DESC"
        
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def mark_inactive(self, urls: list[str]) -> None:
        if not urls: return
        conn = self.db.get_connection()
        placeholders = ",".join("?" for _ in urls)
        conn.execute(f"UPDATE products SET is_active = 0 WHERE url IN ({placeholders})", urls)
        conn.commit()
