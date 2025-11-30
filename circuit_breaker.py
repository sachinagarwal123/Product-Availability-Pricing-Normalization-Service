"""
Circuit breaker implementation for vendor API calls.
Implements the circuit breaker pattern to handle failing vendors gracefully.
"""

from datetime import datetime, timedelta
from typing import Callable, Any, Optional
from models import CircuitBreakerState, CircuitState
from cache_service import cache_service
from config import settings


class CircuitBreaker:
    """Circuit breaker for vendor API calls"""
    
    def __init__(self, vendor_name: str):
        self.vendor_name = vendor_name
        
    async def call(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        """
        Execute function with circuit breaker protection.
        Returns None if circuit is open or function fails.
        """
        state = await cache_service.get_circuit_state(self.vendor_name)
        
        # Check if circuit is open and cooldown period has passed
        if state.state == CircuitState.OPEN:
            if state.next_attempt_time and datetime.now() >= state.next_attempt_time:
                # Move to half-open state
                state.state = CircuitState.HALF_OPEN
                await cache_service.update_circuit_state(state)
            else:
                # Circuit still open, skip call
                return None
                
        try:
            # Attempt the function call
            result = await func(*args, **kwargs)
            
            # Success - reset circuit if it was half-open or had failures
            if state.state == CircuitState.HALF_OPEN or state.failure_count > 0:
                state.state = CircuitState.CLOSED
                state.failure_count = 0
                state.last_failure_time = None
                state.next_attempt_time = None
                await cache_service.update_circuit_state(state)
                
            return result
            
        except Exception as e:
            # Failure - increment failure count
            state.failure_count += 1
            state.last_failure_time = datetime.now()
            
            # Open circuit if failure threshold reached
            if state.failure_count >= settings.CIRCUIT_FAILURE_THRESHOLD:
                state.state = CircuitState.OPEN
                state.next_attempt_time = datetime.now() + timedelta(seconds=settings.CIRCUIT_COOLDOWN_SECONDS)
                
            await cache_service.update_circuit_state(state)
            print(f"Circuit breaker failure for {self.vendor_name}: {e}")
            return None