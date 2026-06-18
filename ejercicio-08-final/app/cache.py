import time
import threading
from typing import Dict, Tuple, Any, Optional


class InMemoryCache:
    """Thread-safe in-memory cache with TTL expiration and hit/miss metrics."""
    def __init__(self):
        # Dictionary storing key -> (value, expire_at)
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._hits = 0
        self._misses = 0
        # Thread safety lock for concurrent execution in multi-threaded environment
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                value, expire_at = self._cache[key]
                if time.time() < expire_at:
                    self._hits += 1
                    return value
                else:
                    # Item expired, remove from cache
                    del self._cache[key]
            self._misses += 1
            return None

    def set(self, key: str, value: Any, ttl: int):
        with self._lock:
            expire_at = time.time() + ttl
            self._cache[key] = (value, expire_at)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def metrics(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate
            }


# Global thread-safe cache instance
cache = InMemoryCache()
