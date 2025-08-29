import asyncio
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, redis_config: dict, ttl_seconds: int = 3600):
        self.redis_config = redis_config
        self.ttl_seconds = ttl_seconds
        self.redis_client = None
        self.is_enabled = False
        
    async def initialize(self):
        """Initialize cache - simplified version without Redis for now."""
        try:
            # For now, just enable in-memory caching
            self.cache_store = {}
            self.is_enabled = True
            logger.info("✅ Basic cache initialized (in-memory)")
        except Exception as e:
            logger.error(f"❌ Cache initialization failed: {e}")
            self.is_enabled = False
    
    async def close(self):
        """Close cache connections."""
        pass
    
    def _generate_cache_key(self, query: str, instance_url: str, user_context: Dict = None) -> str:
        """Generate a cache key."""
        key_data = {
            "query": query.strip().lower(),
            "instance": instance_url,
            "context": user_context or {}
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    async def get_cached_response(
        self, 
        query: str, 
        instance_url: str, 
        user_context: Dict = None,
        similarity_threshold: float = 0.85
    ) -> Optional[Dict[str, Any]]:
        """Get cached response."""
        if not self.is_enabled:
            return None
        
        try:
            cache_key = self._generate_cache_key(query, instance_url, user_context)
            cached_data = self.cache_store.get(cache_key)
            
            if cached_data:
                logger.info(f"🎯 Cache HIT: {cache_key[:20]}...")
                return cached_data
            
            logger.info(f"💨 Cache MISS: {query[:50]}...")
            return None
            
        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
            return None
    
    async def cache_response(
        self, 
        query: str, 
        response: str, 
        instance_url: str, 
        user_context: Dict = None,
        metadata: Dict = None
    ) -> bool:
        """Cache the response."""
        if not self.is_enabled:
            return False
        
        try:
            cache_key = self._generate_cache_key(query, instance_url, user_context)
            
            cache_data = {
                "query": query,
                "response": response,
                "instance_url": instance_url,
                "user_context": user_context or {},
                "metadata": metadata or {},
                "cached_at": datetime.now().isoformat()
            }
            
            self.cache_store[cache_key] = cache_data
            logger.info(f"💾 Cached response: {cache_key[:20]}...")
            return True
            
        except Exception as e:
            logger.error(f"Cache storage error: {e}")
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.is_enabled:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "total_keys": len(self.cache_store),
            "cache_type": "in-memory"
        }
    
    async def clear_cache(self, pattern: str = "") -> int:
        """Clear cache entries."""
        if not self.is_enabled:
            return 0
        
        try:
            count = len(self.cache_store)
            self.cache_store.clear()
            logger.info(f"🗑️ Cleared {count} cache entries")
            return count
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0