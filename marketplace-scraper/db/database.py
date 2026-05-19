from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class Database:
    def __init__(self, db_path: str | None = None) -> None:
        base_dir = Path(__file__).parent.parent
        if db_path is None:
            # Default to data/products.db inside common project root
            self.db_path = base_dir / "data" / "products.db"
        else:
            p = Path(db_path)
            if not p.is_absolute():
                self.db_path = (base_dir / p).resolve()
            else:
                self.db_path = p
        self._local = threading.local()

    def _create_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # B5 fix: thread-safety is handled by threading.local() — each thread gets its
        # own connection. Removed check_same_thread=False which would mask cross-thread bugs.
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        # Allow up to 5s of retry when another thread holds the write lock,
        # instead of immediately raising "database is locked".
        conn.execute("PRAGMA busy_timeout=5000")
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
                config        TEXT DEFAULT '{}',
                schedule_type TEXT CHECK(schedule_type IN ('one_time','recurring')),
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
                product_id    INTEGER, -- Optional link for normalized entities
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
            );

            CREATE TABLE IF NOT EXISTS schema_versions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                db_version      INTEGER NOT NULL UNIQUE,
                applied_at      TEXT NOT NULL,
                description     TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_client ON tasks(client_id);
            CREATE INDEX IF NOT EXISTS idx_snapshots_task ON snapshots(task_id);
            CREATE INDEX IF NOT EXISTS idx_snapshot_products_snap ON snapshot_products(snapshot_id);
            """
        )
        conn.commit()

        # Apply schema migrations
        from db.migrations import MigrationManager
        mgr = MigrationManager(self)
        mgr.apply_pending()
