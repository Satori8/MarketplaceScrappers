from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from db.database import Database


class MigrationManager:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._migrations: list[tuple[int, str, Callable]] = []

    def register(self, version: int, description: str, migration_fn: Callable) -> None:
        self._migrations.append((version, description, migration_fn))
        self._migrations.sort(key=lambda item: item[0])

    def _current_version(self) -> int:
        conn = self.db.get_connection()
        row = conn.execute("SELECT MAX(db_version) AS version FROM schema_versions").fetchone()
        return int(row["version"] or 0)

    def apply_pending(self) -> int:
        conn = self.db.get_connection()
        current = self._current_version()
        applied = 0

        for version, description, migration_fn in self._migrations:
            if version <= current:
                continue
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
