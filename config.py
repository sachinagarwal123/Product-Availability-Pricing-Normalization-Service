"""
Configuration settings for the Product Availability & Pricing Normalization Service.
"""

import os
from typing import List


class Settings:
    """Application configuration settings"""
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    CACHE_TTL_SECONDS: int = 120  # 2 minutes as per senior requirements
    
    # Vendor Configuration
    VENDOR_TIMEOUT_SECONDS: int = 2
    MAX_RETRIES: int = 2
    DATA_FRESHNESS_MINUTES: int = 10
    PRICE_DIFFERENCE_THRESHOLD: float = 0.10  # 10% price difference threshold
    
    # Circuit Breaker Configuration
    CIRCUIT_FAILURE_THRESHOLD: int = 3
    CIRCUIT_COOLDOWN_SECONDS: int = 30
    
    # Rate Limiting Configuration
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    
    # Background Job Configuration
    CACHE_PREWARM_INTERVAL_MINUTES: int = 5
    POPULAR_SKUS: List[str] = ["ABC123", "XYZ789", "DEF456", "GHI012", "JKL345"]
    
    # Vendor URLs (Mock endpoints - in production these would be real vendor APIs)
    VENDOR1_BASE_URL: str = "http://localhost:8002"  # Mock vendor 1
    VENDOR2_BASE_URL: str = "http://localhost:8003"  # Mock vendor 2  
    VENDOR3_BASE_URL: str = "http://localhost:8004"  # Mock vendor 3 (slow/failing)
    
    # SKU Validation
    SKU_MIN_LENGTH: int = 3
    SKU_MAX_LENGTH: int = 20


settings = Settings()