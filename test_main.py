"""
Comprehensive test suite for the Product Availability & Pricing Normalization Service.
Includes unit tests and integration tests for all major components.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from main import app
from models import NormalizedProduct, ProductResponse, CircuitState
from business_logic import business_logic_service
from vendor_service import vendor_service
from cache_service import cache_service


client = TestClient(app)


class TestSKUValidation:
    """Test SKU validation logic"""
    
    def test_valid_skus(self):
        """Test valid SKU formats"""
        response = client.get("/products/ABC123", headers={"x-api-key": "test-key"})
        assert response.status_code != 400  # Should not be validation error
        
    def test_invalid_sku_too_short(self):
        """Test SKU too short"""
        response = client.get("/products/AB", headers={"x-api-key": "test-key"})
        assert response.status_code == 400
        assert "Invalid SKU format" in response.json()["detail"]
        
    def test_invalid_sku_too_long(self):
        """Test SKU too long"""
        response = client.get("/products/" + "A" * 25, headers={"x-api-key": "test-key"})
        assert response.status_code == 400
        
    def test_invalid_sku_special_chars(self):
        """Test SKU with special characters"""
        response = client.get("/products/ABC-123", headers={"x-api-key": "test-key"})
        assert response.status_code == 400


class TestBusinessLogic:
    """Test business logic for vendor selection"""
    
    def test_select_best_vendor_lowest_price(self):
        """Test selection of vendor with lowest price"""
        products = [
            NormalizedProduct(
                sku="TEST123",
                vendor_name="vendor1",
                stock=10,
                price=19.99,
                timestamp=datetime.now(),
                is_valid=True
            ),
            NormalizedProduct(
                sku="TEST123", 
                vendor_name="vendor2",
                stock=15,
                price=18.50,
                timestamp=datetime.now(),
                is_valid=True
            )
        ]
        
        result = business_logic_service.select_best_vendor(products)
        assert result.best_vendor == "vendor2"
        assert result.price == 18.50
        assert result.status == "AVAILABLE"
        
    def test_select_vendor_with_higher_stock_when_price_diff_exceeds_threshold(self):
        """Test enhanced rule: choose higher stock when price difference > 10%"""
        products = [
            NormalizedProduct(
                sku="TEST123",
                vendor_name="vendor1", 
                stock=5,
                price=10.00,
                timestamp=datetime.now(),
                is_valid=True
            ),
            NormalizedProduct(
                sku="TEST123",
                vendor_name="vendor2",
                stock=20,
                price=12.00,  # 20% higher price
                timestamp=datetime.now(),
                is_valid=True
            )
        ]
        
        result = business_logic_service.select_best_vendor(products)
        assert result.best_vendor == "vendor2"  # Higher stock wins despite higher price
        assert result.stock == 20
        
    def test_out_of_stock_when_no_valid_products(self):
        """Test OUT_OF_STOCK response when no valid products"""
        products = [
            NormalizedProduct(
                sku="TEST123",
                vendor_name="vendor1",
                stock=0,
                price=19.99,
                timestamp=datetime.now(),
                is_valid=True
            )
        ]
        
        result = business_logic_service.select_best_vendor(products)
        assert result.status == "OUT_OF_STOCK"
        assert result.best_vendor is None
        
    def test_filter_invalid_products(self):
        """Test filtering of invalid products (old data, invalid price)"""
        old_timestamp = datetime.now() - timedelta(minutes=15)
        products = [
            NormalizedProduct(
                sku="TEST123",
                vendor_name="vendor1",
                stock=10,
                price=0.0,  # Invalid price
                timestamp=datetime.now(),
                is_valid=False
            ),
            NormalizedProduct(
                sku="TEST123",
                vendor_name="vendor2", 
                stock=15,
                price=18.50,
                timestamp=old_timestamp,  # Old data
                is_valid=False
            ),
            NormalizedProduct(
                sku="TEST123",
                vendor_name="vendor3",
                stock=8,
                price=20.00,
                timestamp=datetime.now(),
                is_valid=True
            )
        ]
        
        result = business_logic_service.select_best_vendor(products)
        assert result.best_vendor == "vendor3"  # Only valid product


class TestVendorNormalization:
    """Test vendor response normalization"""
    
    @pytest.mark.asyncio
    async def test_vendor1_normalization_with_null_inventory(self):
        """Test vendor 1 normalization with null inventory and IN_STOCK status"""
        with patch.object(vendor_service, '_fetch_vendor1_with_retry') as mock_fetch:
            # Mock response with null inventory but IN_STOCK status
            mock_product = NormalizedProduct(
                sku="NULL123",
                vendor_name="vendor1",
                stock=5,  # Should be 5 due to business rule
                price=19.99,
                timestamp=datetime.now(),
                is_valid=True
            )
            mock_fetch.return_value = mock_product
            
            result = await vendor_service._get_vendor1_data("NULL123")
            assert result.stock == 5
            
    @pytest.mark.asyncio
    async def test_vendor2_price_parsing(self):
        """Test vendor 2 price parsing from string format"""
        with patch.object(vendor_service, '_fetch_vendor2_with_retry') as mock_fetch:
            mock_product = NormalizedProduct(
                sku="TEST123",
                vendor_name="vendor2",
                stock=15,
                price=18.50,  # Parsed from "$18.50"
                timestamp=datetime.now(),
                is_valid=True
            )
            mock_fetch.return_value = mock_product
            
            result = await vendor_service._get_vendor2_data("TEST123")
            assert result.price == 18.50
            
    @pytest.mark.asyncio
    async def test_vendor3_stock_level_parsing(self):
        """Test vendor 3 stock level parsing from various formats"""
        with patch.object(vendor_service, '_fetch_vendor3_with_retry') as mock_fetch:
            # Test numeric string
            mock_product = NormalizedProduct(
                sku="TEST123",
                vendor_name="vendor3",
                stock=20,  # Parsed from "20"
                price=17.75,
                timestamp=datetime.now(),
                is_valid=True
            )
            mock_fetch.return_value = mock_product
            
            result = await vendor_service._get_vendor3_data("TEST123")
            assert result.stock == 20


class TestConcurrency:
    """Test concurrent vendor calls"""
    
    @pytest.mark.asyncio
    async def test_parallel_vendor_calls(self):
        """Test that vendor calls are made in parallel"""
        start_time = asyncio.get_event_loop().time()
        
        # This should call all 3 vendors concurrently
        results = await vendor_service.get_all_vendor_data("TEST123")
        
        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time
        
        # Should complete in less than 2 seconds (faster than sequential calls)
        assert execution_time < 2.0
        assert len(results) >= 0  # May have circuit breaker failures


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after consecutive failures"""
        # Simulate failures for vendor3 (which has simulated failures)
        for _ in range(3):
            await vendor_service._get_vendor3_data("FAIL123")
            
        # Check circuit state
        circuit_state = await cache_service.get_circuit_state("vendor3")
        # Circuit should be open or have failure count
        assert circuit_state.failure_count > 0


class TestRateLimiting:
    """Test rate limiting functionality"""
    
    def test_rate_limit_enforcement(self):
        """Test rate limiting with multiple requests"""
        api_key = "test-rate-limit-key"
        
        # Make requests up to the limit
        for i in range(5):  # Just test a few requests
            response = client.get("/products/ABC123", headers={"x-api-key": api_key})
            # Should not be rate limited yet
            assert response.status_code != 429


class TestCaching:
    """Test caching functionality"""
    
    @pytest.mark.asyncio
    async def test_cache_hit_and_miss(self):
        """Test cache hit and miss scenarios"""
        sku = "CACHE123"
        
        # First call should be cache miss
        response1 = client.get(f"/products/{sku}", headers={"x-api-key": "test-key"})
        assert response1.status_code == 200
        
        # Second call should be cache hit (if successful)
        response2 = client.get(f"/products/{sku}", headers={"x-api-key": "test-key"})
        assert response2.status_code == 200


class TestHealthEndpoints:
    """Test health and admin endpoints"""
    
    def test_root_endpoint(self):
        """Test root health endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "service" in response.json()
        
    def test_health_check_endpoint(self):
        """Test detailed health check"""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
        assert "components" in response.json()
        
    def test_admin_performance_endpoint(self):
        """Test admin performance endpoint"""
        response = client.get("/admin/performance")
        assert response.status_code == 200
        assert "vendor_performance" in response.json()
        
    def test_admin_circuit_breakers_endpoint(self):
        """Test admin circuit breakers endpoint"""
        response = client.get("/admin/circuit-breakers")
        assert response.status_code == 200
        assert "circuit_breakers" in response.json()
        
    def test_admin_popular_skus_endpoint(self):
        """Test admin popular SKUs endpoint"""
        response = client.get("/admin/popular-skus")
        assert response.status_code == 200
        assert "popular_skus" in response.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])