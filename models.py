"""
Data models for the Product Availability & Pricing Normalization Service.
All models use Pydantic for validation and static typing.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class VendorStatus(str, Enum):
    """Vendor-specific status enumeration"""
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


# Vendor Response Models (Different structures as required)
class Vendor1Response(BaseModel):
    """Vendor 1 - E-commerce style response"""
    product_id: str
    availability: str  # "IN_STOCK" or "OUT_OF_STOCK"
    inventory_count: Optional[int] = None
    unit_price: float
    last_updated: str  # ISO timestamp
    
    
class Vendor2Response(BaseModel):
    """Vendor 2 - Warehouse style response"""
    sku: str
    stock_status: str  # "AVAILABLE" or "UNAVAILABLE"
    quantity_on_hand: int
    cost_per_unit: str  # String format: "$19.99"
    timestamp: int  # Unix timestamp
    

class Vendor3Response(BaseModel):
    """Vendor 3 - Legacy system style response"""
    item_code: str
    status: str  # "ACTIVE" or "INACTIVE"
    stock_level: Optional[str] = None  # Can be null, "LOW", "HIGH", or numeric string
    price_amount: Optional[float] = None
    data_timestamp: str  # Different date format
    

# Normalized Internal Models
class NormalizedProduct(BaseModel):
    """Normalized product data after vendor integration"""
    sku: str
    vendor_name: str
    stock: int
    price: float
    timestamp: datetime
    is_valid: bool = True
    

class ProductResponse(BaseModel):
    """Final API response model"""
    sku: str
    best_vendor: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    status: str  # "AVAILABLE" or "OUT_OF_STOCK"
    vendors_checked: int
    cache_hit: bool = False
    

class VendorPerformance(BaseModel):
    """Vendor performance tracking"""
    vendor_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    last_failure: Optional[datetime] = None
    

class CircuitBreakerState(BaseModel):
    """Circuit breaker state tracking"""
    vendor_name: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    next_attempt_time: Optional[datetime] = None