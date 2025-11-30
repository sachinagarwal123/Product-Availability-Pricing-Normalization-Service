"""
Main FastAPI application for Product Availability & Pricing Normalization Service.
Implements all senior requirements including rate limiting, caching, and circuit breakers.
"""

import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from models import ProductResponse
from vendor_service import vendor_service
from business_logic import business_logic_service
from cache_service import cache_service
from background_jobs import background_job_service
from config import settings


# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks"""
    # Startup
    print("Starting Product Availability & Pricing Normalization Service...")
    background_job_service.start()
    yield
    # Shutdown
    print("Shutting down service...")
    background_job_service.stop()


# FastAPI application with OpenAPI documentation
app = FastAPI(
    title="Product Availability & Pricing Normalization Service",
    description="""
    A comprehensive service that integrates with multiple vendor APIs to provide 
    normalized product availability and pricing information.
    
    ## Features
    - **Multi-vendor Integration**: Supports 3 different vendor APIs with varying response formats
    - **Intelligent Caching**: Redis-based caching with 2-minute TTL
    - **Circuit Breaker**: Automatic failure handling for unreliable vendors
    - **Rate Limiting**: 60 requests per minute per API key
    - **Enhanced Business Logic**: Smart vendor selection based on price and stock
    - **Background Jobs**: Automatic cache prewarming and performance monitoring
    - **Concurrent Processing**: Parallel vendor API calls for optimal performance
    
    ## Authentication
    Include `x-api-key` header with your API key for rate limiting.
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiting error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def validate_sku(sku: str) -> bool:
    """
    Validate SKU format:
    - Must be alphanumeric
    - Length between 3-20 characters
    """
    if not sku or len(sku) < settings.SKU_MIN_LENGTH or len(sku) > settings.SKU_MAX_LENGTH:
        return False
    return re.match(r'^[a-zA-Z0-9]+$', sku) is not None


async def check_rate_limit(api_key: str) -> bool:
    """Check if API key has exceeded rate limit"""
    if not api_key:
        return False
        
    current_requests = await cache_service.increment_rate_limit(api_key)
    return current_requests <= settings.RATE_LIMIT_REQUESTS


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "service": "Product Availability & Pricing Normalization Service",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check with service status"""
    try:
        # Test Redis connection
        await cache_service.redis_client.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"
        
    return {
        "status": "healthy",
        "components": {
            "redis": redis_status,
            "vendors": {
                "vendor1": "configured",
                "vendor2": "configured", 
                "vendor3": "configured"
            }
        }
    }


@app.get("/products/{sku}", response_model=ProductResponse, tags=["Products"])
@limiter.limit("60/minute")
async def get_product(
    request: Request,
    sku: str,
    x_api_key: str = Header(None, description="API key for rate limiting")
):
    """
    Get product availability and pricing information for a given SKU.
    
    This endpoint:
    1. Validates the SKU format
    2. Checks rate limiting based on API key
    3. Attempts to serve from cache first
    4. Queries all vendors concurrently if not cached
    5. Applies business logic to select the best vendor
    6. Returns normalized product information
    
    **Rate Limiting**: 60 requests per minute per API key
    **Caching**: Results cached for 2 minutes
    **Timeout**: Vendor calls timeout after 2 seconds
    **Retries**: Up to 2 retries per vendor with exponential backoff
    """
    
    # Validate SKU format
    if not validate_sku(sku):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid SKU format. Must be alphanumeric, {settings.SKU_MIN_LENGTH}-{settings.SKU_MAX_LENGTH} characters"
        )
    
    # Check rate limiting
    if x_api_key and not await check_rate_limit(x_api_key):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 60 requests per minute per API key"
        )
    
    try:
        # Increment SKU request counter for popularity tracking
        await cache_service.increment_sku_requests(sku)
        
        # Try to get from cache first
        cached_result = await cache_service.get_product(sku)
        if cached_result:
            return cached_result
            
        # Cache miss - fetch from vendors
        vendor_data = await vendor_service.get_all_vendor_data(sku)
        
        # Apply business logic to select best vendor
        result = business_logic_service.select_best_vendor(vendor_data)
        
        # Cache the result
        await cache_service.set_product(sku, result)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/admin/performance", tags=["Admin"])
async def get_vendor_performance():
    """
    Get vendor performance metrics (Admin endpoint).
    
    Returns performance statistics for all vendors including:
    - Total requests
    - Success/failure rates  
    - Average latency
    - Last failure timestamp
    """
    try:
        vendors = ["vendor1", "vendor2", "vendor3"]
        performance_data = {}
        
        for vendor_name in vendors:
            performance = await cache_service.get_vendor_performance(vendor_name)
            
            success_rate = 0.0
            if performance.total_requests > 0:
                success_rate = (performance.successful_requests / performance.total_requests) * 100
                
            performance_data[vendor_name] = {
                "total_requests": performance.total_requests,
                "successful_requests": performance.successful_requests,
                "failed_requests": performance.failed_requests,
                "success_rate_percent": round(success_rate, 2),
                "avg_latency_ms": round(performance.avg_latency_ms, 2),
                "last_failure": performance.last_failure.isoformat() if performance.last_failure else None
            }
            
        return {"vendor_performance": performance_data}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving performance data: {str(e)}"
        )


@app.get("/admin/circuit-breakers", tags=["Admin"])
async def get_circuit_breaker_status():
    """
    Get circuit breaker status for all vendors (Admin endpoint).
    
    Returns current circuit breaker states and failure counts.
    """
    try:
        vendors = ["vendor1", "vendor2", "vendor3"]
        circuit_data = {}
        
        for vendor_name in vendors:
            circuit_state = await cache_service.get_circuit_state(vendor_name)
            circuit_data[vendor_name] = {
                "state": circuit_state.state,
                "failure_count": circuit_state.failure_count,
                "last_failure_time": circuit_state.last_failure_time.isoformat() if circuit_state.last_failure_time else None,
                "next_attempt_time": circuit_state.next_attempt_time.isoformat() if circuit_state.next_attempt_time else None
            }
            
        return {"circuit_breakers": circuit_data}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving circuit breaker data: {str(e)}"
        )


@app.get("/admin/popular-skus", tags=["Admin"])
async def get_popular_skus():
    """
    Get popular SKUs statistics (Admin endpoint).
    
    Returns request counts for tracked SKUs.
    """
    try:
        stats = await cache_service.get_popular_skus_stats()
        return {"popular_skus": stats}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving popular SKUs data: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)