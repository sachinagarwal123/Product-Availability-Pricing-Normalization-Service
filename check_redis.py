#!/usr/bin/env python3
"""Simple Redis connection checker"""

import redis

def check_redis():
    try:
        # Connect to Redis on external port
        client = redis.from_url("redis://localhost:6380", decode_responses=True)
        
        # Test basic operations
        client.ping()
        print("✅ Redis PING: SUCCESS")
        
        # Test set/get
        client.set("test_key", "test_value", ex=10)
        value = client.get("test_key")
        print(f"✅ Redis SET/GET: SUCCESS (value: {value})")
        
        # Test info
        info = client.info("server")
        print(f"✅ Redis Version: {info['redis_version']}")
        print(f"✅ Redis Port: {info['tcp_port']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Checking Redis Connection...")
    check_redis()