from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone


class CacheManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._schema_cache: dict[str, tuple[dict, datetime]] = {}
        self._session_cache: dict[str, dict] = {}
        self._ttl = timedelta(hours=6)

    def set_schema(self, product_type: str, schema: dict) -> None:
        with self._lock:
            self._schema_cache[product_type] = (schema, datetime.now(timezone.utc))

    def get_schema(self, product_type: str) -> dict | None:
        with self._lock:
            value = self._schema_cache.get(product_type)
            if value is None:
                return None
            schema, cached_at = value
            if datetime.now(timezone.utc) - cached_at > self._ttl:
                self._schema_cache.pop(product_type, None)
                return None
            return schema

    def set_session_value(self, session_id: str, key: str, value: object) -> None:
        with self._lock:
            if session_id not in self._session_cache:
                self._session_cache[session_id] = {}
            self._session_cache[session_id][key] = value

    def get_session_value(self, session_id: str, key: str, default: object = None) -> object:
        with self._lock:
            return self._session_cache.get(session_id, {}).get(key, default)

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._session_cache.pop(session_id, None)
