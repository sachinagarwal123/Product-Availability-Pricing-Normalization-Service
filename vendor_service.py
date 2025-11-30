"""
Vendor integration service with normalization, retries, and circuit breaker support.
Handles all three vendor APIs with different response formats.
"""

import asyncio
import httpx
import time
from datetime import datetime, timedelta
from typing import List, Optional
from models import (
    Vendor1Response, Vendor2Response, Vendor3Response, 
    NormalizedProduct, VendorStatus
)
from circuit_breaker import CircuitBreaker
from cache_service import cache_service
from config import settings


class VendorService:
    """Service for integrating with multiple vendor APIs"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=settings.VENDOR_TIMEOUT_SECONDS)
        self.circuit_breakers = {
            "vendor1": CircuitBreaker("vendor1"),
            "vendor2": CircuitBreaker("vendor2"), 
            "vendor3": CircuitBreaker("vendor3")
        }
        
    async def get_all_vendor_data(self, sku: str) -> List[NormalizedProduct]:
        """
        Fetch product data from all vendors concurrently.
        Uses asyncio.gather for parallel execution as required.
        """
        tasks = [
            self._get_vendor1_data(sku),
            self._get_vendor2_data(sku),
            self._get_vendor3_data(sku)
        ]
        
        # Execute all vendor calls in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        normalized_products = []
        for result in results:
            if isinstance(result, NormalizedProduct):
                normalized_products.append(result)
                
        return normalized_products
        
    async def _get_vendor1_data(self, sku: str) -> Optional[NormalizedProduct]:
        """Get data from Vendor 1 (E-commerce style API)"""
        return await self.circuit_breakers["vendor1"].call(
            self._fetch_vendor1_with_retry, sku
        )
        
    async def _fetch_vendor1_with_retry(self, sku: str) -> Optional[NormalizedProduct]:
        """Fetch from Vendor 1 with retry logic"""
        for attempt in range(settings.MAX_RETRIES + 1):
            try:
                start_time = time.time()
                
                # Simulate vendor 1 API call
                # In production, this would be: response = await self.client.get(f"{settings.VENDOR1_BASE_URL}/products/{sku}")
                # For demo purposes, creating mock response
                mock_response = Vendor1Response(
                    product_id=sku,
                    availability="IN_STOCK" if sku != "OUT123" else "OUT_OF_STOCK",
                    inventory_count=None if sku == "NULL123" else 10,
                    unit_price=19.99,
                    last_updated=datetime.now().isoformat()
                )
                
                latency_ms = (time.time() - start_time) * 1000
                await cache_service.update_vendor_performance("vendor1", True, latency_ms)
                
                return self._normalize_vendor1_response(mock_response)
                
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                await cache_service.update_vendor_performance("vendor1", False, latency_ms)
                
                if attempt == settings.MAX_RETRIES:
                    raise e
                await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                
        return None
        
    async def _get_vendor2_data(self, sku: str) -> Optional[NormalizedProduct]:
        """Get data from Vendor 2 (Warehouse style API)"""
        return await self.circuit_breakers["vendor2"].call(
            self._fetch_vendor2_with_retry, sku
        )
        
    async def _fetch_vendor2_with_retry(self, sku: str) -> Optional[NormalizedProduct]:
        """Fetch from Vendor 2 with retry logic"""
        for attempt in range(settings.MAX_RETRIES + 1):
            try:
                start_time = time.time()
                
                # Mock vendor 2 response (different structure)
                mock_response = Vendor2Response(
                    sku=sku,
                    stock_status="AVAILABLE" if sku != "OUT123" else "UNAVAILABLE",
                    quantity_on_hand=15 if sku != "OUT123" else 0,
                    cost_per_unit="$18.50",
                    timestamp=int(datetime.now().timestamp())
                )
                
                latency_ms = (time.time() - start_time) * 1000
                await cache_service.update_vendor_performance("vendor2", True, latency_ms)
                
                return self._normalize_vendor2_response(mock_response)
                
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                await cache_service.update_vendor_performance("vendor2", False, latency_ms)
                
                if attempt == settings.MAX_RETRIES:
                    raise e
                await asyncio.sleep(0.1 * (attempt + 1))
                
        return None
        
    async def _get_vendor3_data(self, sku: str) -> Optional[NormalizedProduct]:
        """Get data from Vendor 3 (Legacy system with slow responses and failures)"""
        return await self.circuit_breakers["vendor3"].call(
            self._fetch_vendor3_with_retry, sku
        )
        
    async def _fetch_vendor3_with_retry(self, sku: str) -> Optional[NormalizedProduct]:
        """Fetch from Vendor 3 with retry logic (simulates slow/failing vendor)"""
        for attempt in range(settings.MAX_RETRIES + 1):
            try:
                start_time = time.time()
                
                # Simulate slow response (as required for vendor 3)
                await asyncio.sleep(0.5)
                
                # Simulate intermittent failures (as required for vendor 3)
                if sku == "FAIL123" or (attempt == 0 and sku.endswith("456")):
                    raise Exception("Vendor 3 simulated failure")
                
                # Mock vendor 3 response (legacy system structure)
                mock_response = Vendor3Response(
                    item_code=sku,
                    status="ACTIVE" if sku != "OUT123" else "INACTIVE",
                    stock_level="20" if sku != "OUT123" else None,
                    price_amount=17.75,
                    data_timestamp=(datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
                )
                
                latency_ms = (time.time() - start_time) * 1000
                await cache_service.update_vendor_performance("vendor3", True, latency_ms)
                
                return self._normalize_vendor3_response(mock_response)
                
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                await cache_service.update_vendor_performance("vendor3", False, latency_ms)
                
                if attempt == settings.MAX_RETRIES:
                    raise e
                await asyncio.sleep(0.1 * (attempt + 1))
                
        return None
        
    def _normalize_vendor1_response(self, response: Vendor1Response) -> NormalizedProduct:
        """Normalize Vendor 1 response to internal format"""
        # Apply stock normalization rules
        if response.inventory_count is None and response.availability == "IN_STOCK":
            stock = 5  # Assume stock = 5 as per business rules
        elif response.availability == "IN_STOCK":
            stock = response.inventory_count or 0
        else:
            stock = 0
            
        # Parse timestamp and check freshness
        timestamp = datetime.fromisoformat(response.last_updated.replace('Z', '+00:00'))
        is_fresh = datetime.now() - timestamp.replace(tzinfo=None) <= timedelta(minutes=settings.DATA_FRESHNESS_MINUTES)
        
        return NormalizedProduct(
            sku=response.product_id,
            vendor_name="vendor1",
            stock=stock,
            price=response.unit_price,
            timestamp=timestamp.replace(tzinfo=None),
            is_valid=response.unit_price > 0 and is_fresh
        )
        
    def _normalize_vendor2_response(self, response: Vendor2Response) -> NormalizedProduct:
        """Normalize Vendor 2 response to internal format"""
        # Parse price from string format
        try:
            price = float(response.cost_per_unit.replace('$', ''))
        except (ValueError, AttributeError):
            price = 0.0
            
        # Determine stock
        stock = response.quantity_on_hand if response.stock_status == "AVAILABLE" else 0
        
        # Parse timestamp and check freshness
        timestamp = datetime.fromtimestamp(response.timestamp)
        is_fresh = datetime.now() - timestamp <= timedelta(minutes=settings.DATA_FRESHNESS_MINUTES)
        
        return NormalizedProduct(
            sku=response.sku,
            vendor_name="vendor2", 
            stock=stock,
            price=price,
            timestamp=timestamp,
            is_valid=price > 0 and is_fresh
        )
        
    def _normalize_vendor3_response(self, response: Vendor3Response) -> NormalizedProduct:
        """Normalize Vendor 3 response to internal format"""
        # Parse stock level (can be None, "LOW", "HIGH", or numeric string)
        stock = 0
        if response.status == "ACTIVE":
            if response.stock_level:
                try:
                    stock = int(response.stock_level)
                except ValueError:
                    # Handle "LOW"/"HIGH" cases
                    stock = 3 if response.stock_level == "LOW" else 25 if response.stock_level == "HIGH" else 0
                    
        # Parse timestamp and check freshness
        timestamp = datetime.strptime(response.data_timestamp, "%Y-%m-%d %H:%M:%S")
        is_fresh = datetime.now() - timestamp <= timedelta(minutes=settings.DATA_FRESHNESS_MINUTES)
        
        return NormalizedProduct(
            sku=response.item_code,
            vendor_name="vendor3",
            stock=stock,
            price=response.price_amount or 0.0,
            timestamp=timestamp,
            is_valid=(response.price_amount or 0) > 0 and is_fresh
        )


# Global vendor service instance
vendor_service = VendorService()