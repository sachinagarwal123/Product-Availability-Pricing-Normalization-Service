"""
Redis cache service for product data caching and vendor performance tracking.
"""

import json
import redis
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from models import ProductResponse, VendorPerformance, CircuitBreakerState, CircuitState
from config import settings


class CacheService:
    """Redis-based caching service with TTL and performance tracking"""
    
    def __init__(self):
        """Initialize Redis connection"""
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        
    async def get_product(self, sku: str) -> Optional[ProductResponse]:
        """Retrieve cached product data"""
        try:
            cached_data = self.redis_client.get(f"product:{sku}")
            if cached_data:
                data = json.loads(cached_data)
                data['cache_hit'] = True
                return ProductResponse(**data)
        except Exception as e:
            print(f"Cache get error for {sku}: {e}")
        return None
        
    async def set_product(self, sku: str, product: ProductResponse) -> None:
        """Cache product data with TTL"""
        try:
            product_dict = product.dict()
            product_dict['cache_hit'] = False  # Reset cache hit flag
            self.redis_client.setex(
                f"product:{sku}",
                settings.CACHE_TTL_SECONDS,
                json.dumps(product_dict, default=str)
            )
        except Exception as e:
            print(f"Cache set error for {sku}: {e}")
            
    async def get_vendor_performance(self, vendor_name: str) -> VendorPerformance:
        """Get vendor performance metrics"""
        try:
            cached_data = self.redis_client.get(f"performance:{vendor_name}")
            if cached_data:
                return VendorPerformance(**json.loads(cached_data))
        except Exception as e:
            print(f"Performance get error for {vendor_name}: {e}")
        return VendorPerformance(vendor_name=vendor_name)
        
    async def update_vendor_performance(self, vendor_name: str, success: bool, latency_ms: float) -> None:
        """Update vendor performance metrics"""
        try:
            perf = await self.get_vendor_performance(vendor_name)
            perf.total_requests += 1
            
            if success:
                perf.successful_requests += 1
            else:
                perf.failed_requests += 1
                perf.last_failure = datetime.now()
                
            # Update average latency (simple moving average)
            if perf.total_requests == 1:
                perf.avg_latency_ms = latency_ms
            else:
                perf.avg_latency_ms = (perf.avg_latency_ms * (perf.total_requests - 1) + latency_ms) / perf.total_requests
                
            self.redis_client.setex(
                f"performance:{vendor_name}",
                86400,  # 24 hours
                json.dumps(perf.dict(), default=str)
            )
        except Exception as e:
            print(f"Performance update error for {vendor_name}: {e}")
            
    async def get_circuit_state(self, vendor_name: str) -> CircuitBreakerState:
        """Get circuit breaker state for vendor"""
        try:
            cached_data = self.redis_client.get(f"circuit:{vendor_name}")
            if cached_data:
                data = json.loads(cached_data)
                # Convert string timestamps back to datetime
                if data.get('last_failure_time'):
                    data['last_failure_time'] = datetime.fromisoformat(data['last_failure_time'])
                if data.get('next_attempt_time'):
                    data['next_attempt_time'] = datetime.fromisoformat(data['next_attempt_time'])
                return CircuitBreakerState(**data)
        except Exception as e:
            print(f"Circuit state get error for {vendor_name}: {e}")
        return CircuitBreakerState(vendor_name=vendor_name)
        
    async def update_circuit_state(self, state: CircuitBreakerState) -> None:
        """Update circuit breaker state"""
        try:
            self.redis_client.setex(
                f"circuit:{state.vendor_name}",
                3600,  # 1 hour
                json.dumps(state.dict(), default=str)
            )
        except Exception as e:
            print(f"Circuit state update error for {state.vendor_name}: {e}")
            
    async def increment_rate_limit(self, api_key: str) -> int:
        """Increment rate limit counter and return current count"""
        try:
            key = f"rate_limit:{api_key}"
            current = self.redis_client.incr(key)
            if current == 1:
                self.redis_client.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)
            return current
        except Exception as e:
            print(f"Rate limit error for {api_key}: {e}")
            return 0
            
    async def get_popular_skus_stats(self) -> Dict[str, int]:
        """Get request count statistics for popular SKUs"""
        try:
            stats = {}
            for sku in settings.POPULAR_SKUS:
                count = self.redis_client.get(f"sku_requests:{sku}")
                stats[sku] = int(count) if count else 0
            return stats
        except Exception as e:
            print(f"Popular SKUs stats error: {e}")
            return {}
            
    async def increment_sku_requests(self, sku: str) -> None:
        """Increment request counter for SKU tracking"""
        try:
            key = f"sku_requests:{sku}"
            self.redis_client.incr(key)
            self.redis_client.expire(key, 86400)  # 24 hours
        except Exception as e:
            print(f"SKU request increment error for {sku}: {e}")


# Global cache service instance
cache_service = CacheService()