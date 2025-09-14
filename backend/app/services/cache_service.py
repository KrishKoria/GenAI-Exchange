"""
In-memory cache service for improving performance by caching frequently accessed data.
"""
import logging
import time
from typing import Any, Dict, List, Optional, Union
from functools import lru_cache
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with value and expiration."""
    value: Any
    expires_at: float
    created_at: float


class InMemoryCache:
    """
    Thread-safe in-memory cache with TTL support.
    Designed for caching document clauses, embeddings, and Q&A results.
    """
    
    def __init__(self, default_ttl: int = 3600, max_size: int = 1000):
        """
        Initialize cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (1 hour)
            max_size: Maximum number of entries (1000 entries)
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self.misses += 1
                return None
            
            current_time = time.time()
            
            # Check if expired
            if current_time > entry.expires_at:
                del self._cache[key]
                self._access_times.pop(key, None)
                self.misses += 1
                return None
            
            # Update access time for LRU
            self._access_times[key] = current_time
            self.hits += 1
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        async with self._lock:
            ttl = ttl or self.default_ttl
            current_time = time.time()
            
            # Create cache entry
            entry = CacheEntry(
                value=value,
                expires_at=current_time + ttl,
                created_at=current_time
            )
            
            # Check if we need to evict entries
            if len(self._cache) >= self.max_size and key not in self._cache:
                await self._evict_lru()
            
            self._cache[key] = entry
            self._access_times[key] = current_time
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._access_times.pop(key, None)
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        value = await self.get(key)
        return value is not None
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
    
    async def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._access_times:
            return
        
        # Find least recently used key
        lru_key = min(self._access_times.items(), key=lambda x: x[1])[0]
        
        # Remove from cache
        self._cache.pop(lru_key, None)
        self._access_times.pop(lru_key, None)
        self.evictions += 1
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        async with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._cache.items():
                if current_time > entry.expires_at:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                self._access_times.pop(key, None)
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hit_rate = self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": round(hit_rate, 3),
            "default_ttl": self.default_ttl
        }


# Cache keys for different data types
class CacheKeys:
    """Standard cache key patterns."""
    
    @staticmethod
    def document_clauses(doc_id: str) -> str:
        return f"doc_clauses:{doc_id}"
    
    @staticmethod
    def clause_embeddings(doc_id: str) -> str:
        return f"doc_embeddings:{doc_id}"
    
    @staticmethod
    def qa_result(doc_id: str, question_hash: str) -> str:
        return f"qa_result:{doc_id}:{question_hash}"
    
    @staticmethod
    def conversation_context(session_id: str) -> str:
        return f"conv_context:{session_id}"
    
    @staticmethod
    def document_metadata(doc_id: str) -> str:
        return f"doc_meta:{doc_id}"


# Global cache instance
_cache_instance: Optional[InMemoryCache] = None


@lru_cache()
def get_cache() -> InMemoryCache:
    """Get singleton cache instance."""
    global _cache_instance
    if _cache_instance is None:
        logger.info("Initializing in-memory cache")
        _cache_instance = InMemoryCache(
            default_ttl=3600,  # 1 hour
            max_size=1000      # 1000 entries
        )
    return _cache_instance


async def start_cache_cleanup_task():
    """Start background task for cache cleanup."""
    cache = get_cache()
    
    async def cleanup_loop():
        while True:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                removed = await cache.cleanup_expired()
                if removed > 0:
                    logger.info(f"Cache cleanup: removed {removed} expired entries")
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    asyncio.create_task(cleanup_loop())
    logger.info("Cache cleanup task started")