from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class Database:
    def __init__(self, db_path: str = "data/products.db") -> None:
        self.db_path = Path(db_path)
        self._local = threading.local()

    def _create_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # B5 fix: thread-safety is handled by threading.local() — each thread gets its
        # own connection. Removed check_same_thread=False which would mask cross-thread bugs.
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = self._create_connection()
            self._local.connection = conn
        return conn

    def close_connection(self) -> None:
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            conn.close()
            self._local.connection = None

    def initialize(self) -> None:
        conn = self.get_connection()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                url             TEXT NOT NULL UNIQUE,
                marketplace     TEXT NOT NULL,
                title           TEXT NOT NULL,
                brand           TEXT,
                model           TEXT,
                norm_brand      TEXT,
                norm_model      TEXT,
                norm_voltage    TEXT,
                norm_capacity   TEXT,
                norm_category   TEXT,
                is_relevant     INTEGER DEFAULT 1,
                category_path   TEXT,
                product_type    TEXT,
                image_url       TEXT,
                description     TEXT,
                first_seen_at   TEXT NOT NULL,
                last_seen_at    TEXT NOT NULL,
                is_active       INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      INTEGER NOT NULL REFERENCES products(id),
                price           REAL NOT NULL,
                currency        TEXT NOT NULL DEFAULT 'UAH',
                availability    TEXT,
                scraped_at      TEXT NOT NULL,
                scrape_session  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS product_specs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      INTEGER NOT NULL REFERENCES products(id),
                schema_version  TEXT NOT NULL,
                specs_json      TEXT NOT NULL,
                raw_specs_json  TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scrape_sessions (
                id              TEXT PRIMARY KEY,
                query           TEXT NOT NULL,
                product_type    TEXT,
                marketplaces    TEXT NOT NULL,
                status          TEXT NOT NULL,
                products_found  INTEGER NOT NULL DEFAULT 0,
                errors_json     TEXT,
                started_at      TEXT NOT NULL,
                finished_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS schema_versions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                db_version      INTEGER NOT NULL UNIQUE,
                applied_at      TEXT NOT NULL,
                description     TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_products_marketplace ON products(marketplace);
            CREATE INDEX IF NOT EXISTS idx_products_type        ON products(product_type);
            CREATE INDEX IF NOT EXISTS idx_price_history_product ON price_history(product_id);
            CREATE INDEX IF NOT EXISTS idx_price_history_scraped ON price_history(scraped_at);
            CREATE INDEX IF NOT EXISTS idx_scrape_sessions_status ON scrape_sessions(status);
            """
        )
        conn.commit()
        
        # Simple migration for existing DB
        for col in ["norm_brand", "norm_model", "norm_voltage", "norm_capacity", "norm_category"]:
            try: conn.execute(f"ALTER TABLE products ADD COLUMN {col} TEXT")
            except: pass
        try: conn.execute("ALTER TABLE products ADD COLUMN is_relevant INTEGER DEFAULT 1")
        except: pass
        conn.commit()
