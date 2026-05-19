from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
import logging

from db.database import Database

logger = logging.getLogger(__name__)

class MigrationManager:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._migrations: list[tuple[int, str, Callable]] = []
        
        # Self-register migrations here
        self.register(1, "Initialize Business Layer (Client/Task/Snapshot)", _v1_business_layer)
        self.register(2, "Add client_id column to tasks", _v2_tasks_client_id)
        self.register(3, "Add task_id column to snapshots", _v3_fix_snapshots_schema)
        self.register(4, "Refactor snapshot_products with product_id", _v4_refactor_snapshot_products)
        self.register(5, "Add client metadata (contact_info, notes)", _v5_fix_clients_schema)
        self.register(6, "Add task configuration (task_type, config)", _v6_extend_tasks_schema)
        self.register(7, "Finalize task schema (description)", _v7_tasks_schema_update)
        self.register(8, "Add attributes/extra columns", _v8_add_attributes_extra)
        self.register(9, "Phase 3 cleanup — removed legacy tables & created views", _v9_schema_cleanup)
        self.register(10, "Add category support to snapshots", _v10_add_category_to_snapshots)
        self.register(11, "Remove obsolete raw_json column", _v11_remove_raw_json)
        self.register(12, "Add image column to snapshot_products", _v12_add_image_to_snapshots)
        self.register(13, "Fix orphan product_id foreign key in snapshot_products", _v13_fix_orphan_fk)

    def register(self, version: int, description: str, migration_fn: Callable) -> None:
        self._migrations.append((version, description, migration_fn))
        self._migrations.sort(key=lambda item: item[0])

    def _current_version(self) -> int:
        conn = self.db.get_connection()
        try:
            row = conn.execute("SELECT MAX(db_version) AS version FROM schema_versions").fetchone()
            return int(row["version"] or 0)
        except:
            return 0

    def apply_pending(self) -> int:
        conn = self.db.get_connection()
        current = self._current_version()
        applied = 0

        for version, description, migration_fn in self._migrations:
            if version <= current:
                continue
            
            logger.info(f"Applying migration v{version}: {description}")
            migration_fn(conn)
            
            conn.execute(
                """
                INSERT INTO schema_versions (db_version, applied_at, description)
                VALUES (?, ?, ?)
                """,
                (version, datetime.now(timezone.utc).isoformat(), description),
            )
            conn.commit()
            applied += 1

        return applied

# --- Migration Functions ---

def _v1_business_layer(conn) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            contact_info TEXT,
            notes      TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id     INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            title         TEXT NOT NULL,
            description   TEXT,
            task_type     TEXT DEFAULT 'discovery',
            schedule_type TEXT DEFAULT 'one_time',
            query_params  TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id       INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            run_at        TEXT NOT NULL,
            product_count INTEGER DEFAULT 0,
            status        TEXT,
            notes         TEXT
        );

        CREATE TABLE IF NOT EXISTS snapshot_products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id   INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
            product_id    INTEGER,
            mp            TEXT,
            sku           TEXT,
            name          TEXT,
            price         REAL,
            avail_code    INTEGER,
            merchant_name TEXT,
            url           TEXT
        );
    """)

def _v2_tasks_client_id(conn):
    pass # Managed by CREATE TABLE IF NOT EXISTS or ALTER

def _v3_fix_snapshots_schema(conn):
    pass

def _v4_refactor_snapshot_products(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(snapshot_products)").fetchall()]
    if "product_id" not in cols:
        conn.execute("ALTER TABLE snapshot_products ADD COLUMN product_id INTEGER")

def _v5_fix_clients_schema(conn):
    pass

def _v6_extend_tasks_schema(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "config" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN config TEXT DEFAULT '{}'")

def _v7_tasks_schema_update(conn):
    pass

def _v8_add_attributes_extra(conn) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(snapshot_products)").fetchall()]
    if "attributes" not in cols:
        conn.execute("ALTER TABLE snapshot_products ADD COLUMN attributes TEXT DEFAULT '{}'")
    if "extra" not in cols:
        conn.execute("ALTER TABLE snapshot_products ADD COLUMN extra TEXT DEFAULT '{}'")

def _v9_schema_cleanup(conn) -> None:
    # Aggressive drop of legacy tables
    legacy = [
        "price_history", "price_observations", "monitored_products", 
        "project_products", "competitors", "projects", 
        "report_runs", "content_templates", 
        "product_specs", "products", "scrape_sessions"
    ]
    for table in legacy:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    
    # Create baseline views
    conn.executescript("""
        DROP VIEW IF EXISTS all_products;
        CREATE VIEW all_products AS
        SELECT 
            sp.id, sp.snapshot_id, sp.mp, sp.sku, sp.name,
            sp.price, sp.avail_code, sp.merchant_name,
            sp.url, sp.url_tag, sp.attributes, sp.extra,
            s.run_at, t.title as task_name, t.task_type,
            c.name as client_name
        FROM snapshot_products sp
        LEFT JOIN snapshots s ON sp.snapshot_id = s.id
        LEFT JOIN tasks t ON s.task_id = t.id
        LEFT JOIN clients c ON t.client_id = c.id;

        DROP VIEW IF EXISTS scrape_log;
        CREATE VIEW scrape_log AS
        SELECT
            s.id as snapshot_id, s.run_at, s.product_count,
            s.status, t.title as task, t.task_type,
            c.name as client
        FROM snapshots s
        LEFT JOIN tasks t ON s.task_id = t.id
        LEFT JOIN clients c ON t.client_id = c.id
        ORDER BY s.run_at DESC;
    """)

def _v10_add_category_to_snapshots(conn) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(snapshot_products)").fetchall()]
    if "category" not in cols:
        conn.execute("ALTER TABLE snapshot_products ADD COLUMN category TEXT")
    
    conn.executescript("""
        DROP VIEW IF EXISTS all_products;
        CREATE VIEW all_products AS
        SELECT 
            sp.id, sp.snapshot_id, sp.mp, sp.sku, sp.name, sp.category,
            sp.price, sp.avail_code, sp.merchant_name,
            sp.url, sp.url_tag, sp.attributes, sp.extra,
            s.run_at, t.title as task_name, t.task_type,
            c.name as client_name
        FROM snapshot_products sp
        LEFT JOIN snapshots s ON sp.snapshot_id = s.id
        LEFT JOIN tasks t ON s.task_id = t.id
        LEFT JOIN clients c ON t.client_id = c.id;
    """)

def _v11_remove_raw_json(conn) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(snapshot_products)").fetchall()]
    if "raw_json" in cols:
        try:
            conn.execute("ALTER TABLE snapshot_products DROP COLUMN raw_json")
        except:
            # Fallback for old SQLite: Recreate table
            logger.info("Sqlite version too old for DROP COLUMN, skipping physical drop of raw_json.")
            pass

def _v12_add_image_to_snapshots(conn) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(snapshot_products)").fetchall()]
    if "image" not in cols:
        conn.execute("ALTER TABLE snapshot_products ADD COLUMN image TEXT")
    
    conn.executescript("""
        DROP VIEW IF EXISTS all_products;
        CREATE VIEW all_products AS
        SELECT 
            sp.id, sp.snapshot_id, sp.mp, sp.sku, sp.name, sp.category, sp.image,
            sp.price, sp.avail_code, sp.merchant_name,
            sp.url, sp.url_tag, sp.attributes, sp.extra,
            s.run_at, t.title as task_name, t.task_type,
            c.name as client_name
        FROM snapshot_products sp
        LEFT JOIN snapshots s ON sp.snapshot_id = s.id
        LEFT JOIN tasks t ON s.task_id = t.id
        LEFT JOIN clients c ON t.client_id = c.id;
    """)


def _v13_fix_orphan_fk(conn) -> None:
    # 1. Recover from broken state where table was dropped but rename failed
    res_orig = conn.execute("SELECT name FROM sqlite_master WHERE name='snapshot_products'").fetchone()
    res_new = conn.execute("SELECT name FROM sqlite_master WHERE name='snapshot_products_new'").fetchone()
    
    if not res_orig and res_new:
        # We crashed right before rename
        logger.info("Recovering from broken v13 migration: renaming snapshot_products_new -> snapshot_products")
        conn.execute("DROP VIEW IF EXISTS all_products")
        conn.execute("ALTER TABLE snapshot_products_new RENAME TO snapshot_products")
        res_orig = True # proceed to setup view
    
    # 2. If it's still missing altogether, we have a bigger issue but let's just abort this migration logic
    if not res_orig:
        return

    # 3. Check if FK actually needs removing
    sql_res = conn.execute("SELECT sql FROM sqlite_master WHERE name='snapshot_products'").fetchone()
    if sql_res and "REFERENCES products(id)" in sql_res[0]:
        logger.info("Recreating snapshot_products to remove orphan FK on product_id...")
        
        conn.execute("DROP VIEW IF EXISTS all_products")
        conn.execute("DROP TABLE IF EXISTS snapshot_products_new")
        
        conn.execute("""
            CREATE TABLE snapshot_products_new (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id   INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
                product_id    INTEGER,
                mp            TEXT,
                sku           TEXT,
                name          TEXT,
                price         REAL,
                avail_code    INTEGER,
                merchant_name TEXT,
                url           TEXT,
                url_tag       TEXT,
                category      TEXT,
                image         TEXT,
                attributes    TEXT DEFAULT '{}',
                extra         TEXT DEFAULT '{}'
            )
        """)
        
        cols = [r[1] for r in conn.execute("PRAGMA table_info(snapshot_products)").fetchall()]
        new_cols = ["snapshot_id", "product_id", "mp", "sku", "name", "price", "avail_code", "merchant_name", "url", "url_tag", "category", "image", "attributes", "extra"]
        common = [c for c in cols if c in new_cols]
        col_str = ", ".join(common)
        
        conn.execute(f"INSERT INTO snapshot_products_new ({col_str}) SELECT {col_str} FROM snapshot_products")
        
        conn.execute("DROP TABLE snapshot_products")
        conn.execute("ALTER TABLE snapshot_products_new RENAME TO snapshot_products")
    
    # 4. Enforce indexing and view recreation (happens if recovered or fully migrated)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_products_snap ON snapshot_products(snapshot_id)")
    
    # Needs to recreate the view safely
    conn.executescript("""
        DROP VIEW IF EXISTS all_products;
        CREATE VIEW all_products AS
        SELECT 
            sp.id, sp.snapshot_id, sp.mp, sp.sku, sp.name, sp.category, sp.image,
            sp.price, sp.avail_code, sp.merchant_name,
            sp.url, sp.url_tag, sp.attributes, sp.extra,
            s.run_at, t.title as task_name, t.task_type,
            c.name as client_name
        FROM snapshot_products sp
        LEFT JOIN snapshots s ON sp.snapshot_id = s.id
        LEFT JOIN tasks t ON s.task_id = t.id
        LEFT JOIN clients c ON t.client_id = c.id;
    """)
