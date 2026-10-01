# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""In-memory TTL cache for SAT lookups (per worker)."""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Tuple, Optional


class TtlCache:
    def __init__(self, ttl_seconds: int = 86400):
        self._ttl = ttl_seconds
        self._data: Dict[Any, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key) -> Optional[Any]:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < time.time():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key, value):
        with self._lock:
            self._data[key] = (time.time() + self._ttl, value)

    def clear(self):
        with self._lock:
            self._data.clear()


_lista69b_cache = TtlCache(ttl_seconds=86400)
_cfdi_status_cache = TtlCache(ttl_seconds=3600)


def lista69b_cache() -> TtlCache:
    return _lista69b_cache


def cfdi_status_cache() -> TtlCache:
    return _cfdi_status_cache
