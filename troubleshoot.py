#!/usr/bin/env python3
"""
Troubleshooting script to verify Redis connection and service health.
"""

import redis
import asyncio
import httpx
from config import settings


async def test_redis_connection():
    """Test Redis connection"""
    try:
        # Test with Docker internal URL
        docker_client = redis.from_url("redis://redis:6379", decode_responses=True)
        docker_client.ping()
        print("✅ Redis connection (Docker internal): SUCCESS")
        return True
    except Exception as e:
        print(f"❌ Redis connection (Docker internal): FAILED - {e}")
        
    try:
        # Test with localhost URL
        local_client = redis.from_url("redis://localhost:6380", decode_responses=True)
        local_client.ping()
        print("✅ Redis connection (localhost:6380): SUCCESS")
        return True
    except Exception as e:
        print(f"❌ Redis connection (localhost:6380): FAILED - {e}")
        
    return False


async def test_api_health():
    """Test API health endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8001/health")
            if response.status_code == 200:
                print("✅ API Health Check: SUCCESS")
                print(f"   Response: {response.json()}")
                return True
            else:
                print(f"❌ API Health Check: FAILED - Status {response.status_code}")
    except Exception as e:
        print(f"❌ API Health Check: FAILED - {e}")
    return False


async def test_product_endpoint():
    """Test product endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8001/products/ABC123",
                headers={"x-api-key": "test-key"}
            )
            if response.status_code == 200:
                print("✅ Product Endpoint: SUCCESS")
                print(f"   Response: {response.json()}")
                return True
            else:
                print(f"❌ Product Endpoint: FAILED - Status {response.status_code}")
                print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Product Endpoint: FAILED - {e}")
    return False


async def main():
    """Run all tests"""
    print("🔍 Product Availability Service - Troubleshooting")
    print("=" * 50)
    
    print("\n1. Testing Redis Connection...")
    redis_ok = await test_redis_connection()
    
    print("\n2. Testing API Health...")
    api_ok = await test_api_health()
    
    print("\n3. Testing Product Endpoint...")
    product_ok = await test_product_endpoint()
    
    print("\n" + "=" * 50)
    if redis_ok and api_ok and product_ok:
        print("🎉 All tests PASSED! Service is working correctly.")
    else:
        print("⚠️  Some tests FAILED. Check the logs above.")
        
    print("\n💡 Quick Fixes:")
    print("   - Restart Docker: docker-compose down && docker-compose up --build")
    print("   - Check ports: docker ps")
    print("   - View logs: docker-compose logs")


if __name__ == "__main__":
    asyncio.run(main())