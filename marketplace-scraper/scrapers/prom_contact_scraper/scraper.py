import os
import json
import time
import random
import threading
import sqlite3
import yaml
from pathlib import Path
from curl_cffi import requests

from scrapers.mapi_scraper.http import _PROM_HEADERS

def get_db_path() -> Path:
    # Project root is 3 levels up from scrapers/prom_contact_scraper/scraper.py
    base_dir = Path(__file__).resolve().parent.parent.parent
    config_path = base_dir / "config.yaml"
    
    if not config_path.exists():
        raise RuntimeError(f"config.yaml not found at {config_path}")
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            
        # Support both 'database.path' and 'app.db_path' for robustness
        db_path_str = None
        if "database" in config and "path" in config["database"]:
            db_path_str = config["database"]["path"]
        elif "app" in config and "db_path" in config["app"]:
            db_path_str = config["app"]["db_path"]
            
        if db_path_str:
            p = Path(db_path_str)
            if p.is_absolute():
                return p
            return base_dir / p
            
        # Fallback to data/products.db based on project structure
        return base_dir / "data" / "products.db"
    except Exception as e:
        raise RuntimeError(f"Failed to read or parse config.yaml: {e}")

def get_db_connection() -> sqlite3.Connection:
    db_p = get_db_path()
    db_p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS prom_contacts (
            company_id   INTEGER PRIMARY KEY,
            name         TEXT,
            slug         TEXT,
            email        TEXT,
            phones       TEXT,   -- JSON array of phone number strings
            category_alias TEXT,
            category_caption TEXT,
            scraped_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS prom_crawl_progress (
            alias        TEXT PRIMARY KEY,
            caption      TEXT,
            total        INTEGER,
            offset       INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'pending'  -- pending | running | done | error
        );
    """)
    conn.commit()

def run_category(alias: str, caption: str, on_progress: callable, stop_event: threading.Event) -> None:
    """
    Scrapes contacts for a given category.
    on_progress(current_offset: int, total: int, new_contacts: int)
    """
    try:
        conn = get_db_connection()
    except Exception as e:
        on_progress(0, 0, 0) # Trigger callback before raising or stopping? We can just raise.
        raise e
        
    init_db(conn)
    
    # 1. Check prom_crawl_progress
    row = conn.execute("SELECT * FROM prom_crawl_progress WHERE alias = ?", (alias,)).fetchone()
    
    if row:
        if row["status"] == "done":
            on_progress(row["total"], row["total"], 0)
            print(f"Skipping {caption} ({alias}) - already marked as 'done'.")
            conn.close()
            return
        
        offset = row["offset"]
        total = row["total"] or 0
        conn.execute("UPDATE prom_crawl_progress SET status = 'running' WHERE alias = ?", (alias,))
        conn.commit()
    else:
        offset = 0
        total = 0
        conn.execute(
            "INSERT INTO prom_crawl_progress (alias, caption, total, offset, status) VALUES (?, ?, ?, ?, 'running')",
            (alias, caption, total, offset)
        )
        conn.commit()

    base_query = {
        "operationName": "CategoryListingQuery",
        "variables": {
            "alias": alias,
            "params": {"binary_filters": []},
            "offset": offset,
            "limit": 96,
            "regionId": None,
            "subdomain": None,
            "sort": None,
            "manufacturer_id": None,
            "company_id": None,
            "includePremiumAdvBlock": True,
            "regionDelivery": None
        },
        "query": "query CategoryListingQuery($alias: String!, $manufacturer_id: Int, $params: Any, $company_id: Int, $sort: String, $offset: Int, $limit: Int, $regionId: Int, $includePremiumAdvBlock: Boolean = false, $subdomain: String, $regionDelivery: String) {\n  listing: categoryListing(\n    alias: $alias\n    manufacturer_id: $manufacturer_id\n    params: $params\n    company_id: $company_id\n    sort: $sort\n    offset: $offset\n    limit: $limit\n    region: {id: $regionId, subdomain: $subdomain}\n  ) {\n\n    page {\n      total\n      products {\n        product {     \n      company { id name slug contactEmail phones }\n        }\n      }\n    }\n  }\n}"
    }

    url = "https://prom.ua/graphql"
    headers = _PROM_HEADERS.copy()
    
    new_contacts_accum = 0
    first_request = True
    
    try:
        while True:
            if stop_event.is_set():
                conn.execute("UPDATE prom_crawl_progress SET status = 'error', offset = ? WHERE alias = ?", (offset, alias))
                conn.commit()
                break
                
            base_query["variables"]["offset"] = offset
            
            # Fetch using curl_cffi with impersonate
            resp = requests.post(url, headers=headers, json=base_query, impersonate="chrome124", timeout=15)
            
            if resp.status_code != 200:
                print(f"GraphQL returned {resp.status_code}")
                # We could retry or error out. Let's error out to save current state
                conn.execute("UPDATE prom_crawl_progress SET status = 'error', offset = ? WHERE alias = ?", (offset, alias))
                conn.commit()
                break
                
            data = resp.json()
            try:
                listing = data.get("data", {}).get("listing", {}) or {}
                page_data = listing.get("page", {}) or {}
                
                if first_request:
                    total = page_data.get("total", 0)
                    conn.execute("UPDATE prom_crawl_progress SET total = ? WHERE alias = ?", (total, alias))
                    conn.commit()
                    first_request = False
                    
                products = page_data.get("products", [])
            except Exception as e:
                print(f"Error parsing GraphQL response: {e}")
                conn.execute("UPDATE prom_crawl_progress SET status = 'error', offset = ? WHERE alias = ?", (offset, alias))
                conn.commit()
                break
                
            if not products:
                # No more products
                break
                
            companies_seen = set()
            new_contacts_this_page = 0
            
            for p in products:
                prod = p.get("product") if p else None
                if not prod:
                    continue
                
                company = prod.get("company")
                if not company:
                    continue
                    
                cid = company.get("id")
                if not cid or cid in companies_seen:
                    continue
                companies_seen.add(cid)
                
                email = company.get("contactEmail")
                phones = company.get("phones", [])
                
                # Check filter condition
                if not email and not phones:
                    continue
                    
                name = company.get("name")
                slug = company.get("slug")
                
                phones_json = json.dumps(phones, ensure_ascii=False)
                
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT OR IGNORE INTO prom_contacts (company_id, name, slug, email, phones, category_alias, category_caption) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (cid, name, slug, email, phones_json, alias, caption)
                    )
                    if cur.rowcount > 0:
                        new_contacts_this_page += 1
                except Exception as e:
                    print(f"DB Error inserting company {cid}: {e}")
                    
            new_contacts_accum += new_contacts_this_page
            offset += 96
            
            # Update offset in progress table
            conn.execute("UPDATE prom_crawl_progress SET offset = ? WHERE alias = ?", (offset, alias))
            conn.commit()
            
            # Notify progress
            on_progress(offset, total, new_contacts_accum)
            
            if offset >= total:
                conn.execute("UPDATE prom_crawl_progress SET status = 'done', offset = ? WHERE alias = ?", (offset, alias))
                conn.commit()
                break
                
            # Add delay
            time.sleep(0.5 + random.uniform(0.3, 0.8))

    except Exception as e:
        print(f"Runtime Exception in run_category: {e}")
        conn.execute("UPDATE prom_crawl_progress SET status = 'error', offset = ? WHERE alias = ?", (offset, alias))
        conn.commit()
        raise e
    finally:
        conn.close()
