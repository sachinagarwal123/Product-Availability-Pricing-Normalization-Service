"""
Background job scheduler for cache prewarming and vendor performance logging.
Runs every 5 minutes as per senior requirements.
"""

import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from vendor_service import vendor_service
from business_logic import business_logic_service
from cache_service import cache_service
from config import settings


class BackgroundJobService:
    """Service for managing background tasks"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        
    def start(self):
        """Start the background job scheduler"""
        # Schedule cache prewarming every 5 minutes
        self.scheduler.add_job(
            func=self.prewarm_cache_job,
            trigger=IntervalTrigger(minutes=settings.CACHE_PREWARM_INTERVAL_MINUTES),
            id='prewarm_cache',
            name='Prewarm cache for popular SKUs',
            replace_existing=True
        )
        
        # Schedule vendor performance logging every 5 minutes
        self.scheduler.add_job(
            func=self.log_vendor_performance,
            trigger=IntervalTrigger(minutes=settings.CACHE_PREWARM_INTERVAL_MINUTES),
            id='log_performance',
            name='Log vendor performance metrics',
            replace_existing=True
        )
        
        self.scheduler.start()
        print("Background job scheduler started")
        
    def stop(self):
        """Stop the background job scheduler"""
        self.scheduler.shutdown()
        print("Background job scheduler stopped")
        
    async def prewarm_cache_job(self):
        """
        Prewarm cache for most frequently requested SKUs.
        This job runs every 5 minutes to ensure popular products are always cached.
        """
        try:
            print(f"[{datetime.now()}] Starting cache prewarm job...")
            
            # Get popular SKUs statistics
            sku_stats = await cache_service.get_popular_skus_stats()
            
            # Sort SKUs by request count (most popular first)
            popular_skus = sorted(sku_stats.items(), key=lambda x: x[1], reverse=True)
            
            # If no stats available, use default popular SKUs
            if not popular_skus:
                popular_skus = [(sku, 0) for sku in settings.POPULAR_SKUS]
                
            # Prewarm cache for top SKUs
            prewarmed_count = 0
            for sku, request_count in popular_skus[:10]:  # Top 10 SKUs
                try:
                    # Check if already cached
                    cached_product = await cache_service.get_product(sku)
                    if cached_product:
                        continue  # Skip if already cached
                        
                    # Fetch fresh data from vendors
                    vendor_data = await vendor_service.get_all_vendor_data(sku)
                    if vendor_data:
                        # Apply business logic to select best vendor
                        result = business_logic_service.select_best_vendor(vendor_data)
                        
                        # Cache the result
                        await cache_service.set_product(sku, result)
                        prewarmed_count += 1
                        
                except Exception as e:
                    print(f"Error prewarming cache for SKU {sku}: {e}")
                    
            print(f"Cache prewarm completed. Prewarmed {prewarmed_count} SKUs")
            
        except Exception as e:
            print(f"Cache prewarm job failed: {e}")
            
    async def log_vendor_performance(self):
        """
        Log vendor performance metrics including latency and failure rates.
        This provides insights into vendor reliability and response times.
        """
        try:
            print(f"[{datetime.now()}] Logging vendor performance...")
            
            vendors = ["vendor1", "vendor2", "vendor3"]
            
            for vendor_name in vendors:
                try:
                    performance = await cache_service.get_vendor_performance(vendor_name)
                    
                    if performance.total_requests > 0:
                        success_rate = (performance.successful_requests / performance.total_requests) * 100
                        failure_rate = (performance.failed_requests / performance.total_requests) * 100
                        
                        print(f"Vendor {vendor_name} Performance:")
                        print(f"  Total Requests: {performance.total_requests}")
                        print(f"  Success Rate: {success_rate:.2f}%")
                        print(f"  Failure Rate: {failure_rate:.2f}%")
                        print(f"  Avg Latency: {performance.avg_latency_ms:.2f}ms")
                        if performance.last_failure:
                            print(f"  Last Failure: {performance.last_failure}")
                        print()
                    else:
                        print(f"Vendor {vendor_name}: No requests recorded")
                        
                except Exception as e:
                    print(f"Error logging performance for {vendor_name}: {e}")
                    
        except Exception as e:
            print(f"Performance logging job failed: {e}")


# Global background job service instance
background_job_service = BackgroundJobService()