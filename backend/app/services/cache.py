"""In-process caches keyed by data_version (docs/api-contracts.md#caching-and-invalidation)."""

import threading
import time
from collections.abc import Callable, Hashable
from typing import Any

from cachetools import TTLCache


class Memo[T]:
    """One value recomputed at most once per ttl."""

    def __init__(self, ttl: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._value: T | None = None
        self._expires = 0.0

    def get(self, compute: Callable[[], T]) -> T:
        with self._lock:
            if self._value is None or self._clock() >= self._expires:
                self._value = compute()
                self._expires = self._clock() + self._ttl
            return self._value

    def clear(self) -> None:
        with self._lock:
            self._value = None


class VersionedCache:
    """TTL caches per namespace; every key includes the current data_version."""

    def __init__(self, maxsize: int = 2048, enabled: bool = True) -> None:
        self._maxsize = maxsize
        self._enabled = enabled
        self._caches: dict[str, TTLCache[Hashable, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set[T](
        self, namespace: str, ttl: float, key: Hashable, version: int | None,
        compute: Callable[[], T],
    ) -> T:  # fmt: skip
        if not self._enabled:
            return compute()
        full_key = (version, key)
        with self._lock:
            cache = self._caches.setdefault(namespace, TTLCache(self._maxsize, ttl))
            if full_key in cache:
                return cache[full_key]
        value = compute()
        with self._lock:
            cache[full_key] = value
        return value

    def clear(self) -> None:
        with self._lock:
            self._caches.clear()
