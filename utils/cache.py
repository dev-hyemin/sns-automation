import hashlib
import json
import os
from typing import Any, Optional

from .logger import get_logger

logger = get_logger()

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")


class CacheManager:
    """Simple JSON-based cache to avoid re-generating identical content."""

    def __init__(self, cache_dir: str = CACHE_DIR) -> None:
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _key(self, *parts: str) -> str:
        raw = "_".join(parts).encode("utf-8")
        return hashlib.md5(raw).hexdigest()

    def _path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, *parts: str) -> Optional[Any]:
        """Return cached value or None."""
        path = self._path(self._key(*parts))
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Cache hit: {parts}")
            return data
        except Exception as exc:
            logger.warning(f"Cache read error ({path}): {exc}")
            return None

    def set(self, value: Any, *parts: str) -> None:
        """Persist value to cache."""
        path = self._path(self._key(*parts))
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
            logger.info(f"Cache saved: {parts}")
        except Exception as exc:
            logger.warning(f"Cache write error ({path}): {exc}")

    def exists(self, *parts: str) -> bool:
        return os.path.exists(self._path(self._key(*parts)))

    def invalidate(self, *parts: str) -> None:
        path = self._path(self._key(*parts))
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Cache invalidated: {parts}")
