"""Timeout handling utilities for AI Council operations."""

import asyncio
import functools
import logging
import signal
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Optional, TypeVar, Union
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from .failure_handling import FailureEvent, FailureType, RiskLevel, resilience_manager


logger = logging.getLogger(__name__)

T = TypeVar('T')


class TimeoutError(Exception):
    """Custom timeout exception with additional context."""
    
    def __init__(self, message: str, timeout_duration: float, operation: str = ""):
        self.timeout_duration = timeout_duration
        self.operation = operation
        super().__init__(message)


class TimeoutHandler:
    """Handles various types of timeouts in the system."""
    
    def __init__(self):
        self.active_operations: dict[str, float] = {}
        self.timeout_counts: dict[str, int] = {}
        self._lock = threading.Lock()
    
    def with_timeout(
        self,
        timeout_seconds: float,
        operation_name: str = "",
        component: str = "",
        subtask_id: Optional[str] = None,
        model_id: Optional[str] = None
    ):
        """Decorator to add timeout handling to functions."""
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> T:
                return self.execute_with_timeout(
                    func, timeout_seconds, operation_name, component,
                    subtask_id, model_id, *args, **kwargs
                )
            return wrapper
        return decorator
    
    def execute_with_timeout(
        self,
        func: Callable[..., T],
        timeout_seconds: float,
        operation_name: str = "",
        component: str = "",
        subtask_id: Optional[str] = None,
        model_id: Optional[str] = None,
        *args,
        **kwargs
    ) -> T:
        """Execute a function with timeout handling."""
        operation_id = f"{component}:{operation_name}:{int(time.time())}"
        
        with self._lock:
            self.active_operations[operation_id] = time.time()
        
        try:
            if asyncio.iscoroutinefunction(func):
                # Handle async functions
                return self._execute_async_with_timeout(
                    func, timeout_seconds, operation_name, component,
                    subtask_id, model_id, *args, **kwargs
                )
            else:
                # Handle sync functions
                return self._execute_sync_with_timeout(
                    func, timeout_seconds, operation_name, component,
                    subtask_id, model_id, *args, **kwargs
                )
        
        finally:
            with self._lock:
                self.active_operations.pop(operation_id, None)
    
    def _execute_sync_with_timeout(
        self,
        func: Callable[..., T],
        timeout_seconds: float,
        operation_name: str,
        component: str,
        subtask_id: Optional[str],
        model_id: Optional[str],
        *args,
        **kwargs
    ) -> T:
        """Execute synchronous function with timeout."""
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            
            try:
                result = future.result(timeout=timeout_seconds)
                return result
                
            except FutureTimeoutError:
                # Cancel the future if possible
                future.cancel()
                
                # Record timeout failure
                self._record_timeout_failure(
                    operation_name, component, timeout_seconds,
                    subtask_id, model_id
                )
                
                raise TimeoutError(
                    f"Operation '{operation_name}' timed out after {timeout_seconds}s",
                    timeout_seconds,
                    operation_name
                )
    
    async def _execute_async_with_timeout(
        self,
        func: Callable[..., T],
        timeout_seconds: float,
        operation_name: str,
        component: str,
        subtask_id: Optional[str],
        model_id: Optional[str],
        *args,
        **kwargs
    ) -> T:
        """Execute asynchronous function with timeout."""
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout_seconds
            )
            return result
            
        except asyncio.TimeoutError:
            # Record timeout failure
            self._record_timeout_failure(
                operation_name, component, timeout_seconds,
                subtask_id, model_id
            )
            
            raise TimeoutError(
                f"Async operation '{operation_name}' timed out after {timeout_seconds}s",
                timeout_seconds,
                operation_name
            )
    
    def _record_timeout_failure(
        self,
        operation_name: str,
        component: str,
        timeout_duration: float,
        subtask_id: Optional[str],
        model_id: Optional[str]
    ):
        """Record a timeout failure event."""
        with self._lock:
            key = f"{component}:{operation_name}"
            self.timeout_counts[key] = self.timeout_counts.get(key, 0) + 1
        
        failure_event = FailureEvent(
            failure_type=FailureType.TIMEOUT,
            component=component,
            error_message=f"Operation '{operation_name}' timed out after {timeout_duration}s",
            subtask_id=subtask_id,
            model_id=model_id,
            severity=RiskLevel.MEDIUM,
            context={
                "timeout_duration": timeout_duration,
                "operation_name": operation_name,
                "timeout_count": self.timeout_counts[key]
            }
        )
        
        resilience_manager.handle_failure(failure_event)
        
        logger.warning(
            f"Timeout in {component}:{operation_name} after {timeout_duration}s "
            f"(count: {self.timeout_counts[key]})"
        )
    
    def get_active_operations(self) -> dict[str, float]:
        """Get currently active operations and their start times."""
        with self._lock:
            return self.active_operations.copy()
    
    def get_timeout_statistics(self) -> dict[str, int]:
        """Get timeout statistics by operation."""
        with self._lock:
            return self.timeout_counts.copy()


class AdaptiveTimeoutManager:
    """Manages adaptive timeouts based on historical performance."""
    
    def __init__(self):
        self.performance_history: dict[str, list[float]] = {}
        self.default_timeouts: dict[str, float] = {
            "model_execution": 30.0,
            "analysis": 10.0,
            "decomposition": 15.0,
            "arbitration": 20.0,
            "synthesis": 15.0
        }
        self.max_history_size = 100
        self._lock = threading.Lock()
    
    def record_execution_time(self, operation: str, execution_time: float):
        """Record execution time for an operation."""
        with self._lock:
            if operation not in self.performance_history:
                self.performance_history[operation] = []
            
            self.performance_history[operation].append(execution_time)
            
            # Keep only recent history
            if len(self.performance_history[operation]) > self.max_history_size:
                self.performance_history[operation].pop(0)
    
    def get_adaptive_timeout(self, operation: str, percentile: float = 95.0) -> float:
        """Get adaptive timeout based on historical performance."""
        with self._lock:
            history = self.performance_history.get(operation, [])
            
            if not history:
                # No history, use default
                return self.default_timeouts.get(operation, 30.0)
            
            # Calculate percentile-based timeout
            sorted_times = sorted(history)
            index = int((percentile / 100.0) * len(sorted_times))
            index = min(index, len(sorted_times) - 1)
            
            adaptive_timeout = sorted_times[index]
            
            # Apply safety margin (50% buffer)
            adaptive_timeout *= 1.5
            
            # Ensure minimum timeout
            min_timeout = self.default_timeouts.get(operation, 30.0) * 0.5
            adaptive_timeout = max(adaptive_timeout, min_timeout)
            
            # Ensure maximum timeout (prevent runaway timeouts)
            max_timeout = self.default_timeouts.get(operation, 30.0) * 5.0
            adaptive_timeout = min(adaptive_timeout, max_timeout)
            
            return adaptive_timeout
    
    def get_performance_stats(self, operation: str) -> dict[str, float]:
        """Get performance statistics for an operation."""
        with self._lock:
            history = self.performance_history.get(operation, [])
            
            if not history:
                return {"count": 0}
            
            sorted_times = sorted(history)
            count = len(sorted_times)
            
            return {
                "count": count,
                "min": sorted_times[0],
                "max": sorted_times[-1],
                "mean": sum(sorted_times) / count,
                "median": sorted_times[count // 2],
                "p95": sorted_times[int(0.95 * count)],
                "p99": sorted_times[int(0.99 * count)]
            }


@contextmanager
def timeout_context(
    timeout_seconds: float,
    operation_name: str = "",
    component: str = "",
    subtask_id: Optional[str] = None,
    model_id: Optional[str] = None
):
    """Context manager for timeout handling."""
    timeout_handler = TimeoutHandler()
    
    def timeout_alarm_handler(signum, frame):
        raise TimeoutError(
            f"Operation '{operation_name}' timed out after {timeout_seconds}s",
            timeout_seconds,
            operation_name
        )
    
    # Set up signal-based timeout (Unix only)
    old_handler = None
    try:
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, timeout_alarm_handler)
            signal.alarm(int(timeout_seconds))
        
        start_time = time.time()
        yield
        
    except TimeoutError:
        # Record timeout failure
        timeout_handler._record_timeout_failure(
            operation_name, component, timeout_seconds,
            subtask_id, model_id
        )
        raise
        
    finally:
        # Clean up signal handler
        if hasattr(signal, 'SIGALRM') and old_handler is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


class RateLimitManager:
    """Manages rate limiting and backoff strategies."""
    
    def __init__(self):
        self.rate_limits: dict[str, dict[str, Any]] = {}
        self.request_history: dict[str, list[float]] = {}
        self._lock = threading.Lock()
    
    def set_rate_limit(
        self,
        resource: str,
        requests_per_minute: int,
        burst_limit: Optional[int] = None
    ):
        """Set rate limit for a resource."""
        with self._lock:
            self.rate_limits[resource] = {
                "requests_per_minute": requests_per_minute,
                "burst_limit": burst_limit or requests_per_minute,
                "window_start": time.time(),
                "request_count": 0
            }
    
    def check_rate_limit(self, resource: str) -> tuple[bool, float]:
        """Check if request is within rate limit.
        
        Returns:
            tuple: (is_allowed, wait_time_seconds)
        """
        with self._lock:
            if resource not in self.rate_limits:
                return True, 0.0
            
            limit_info = self.rate_limits[resource]
            current_time = time.time()
            
            # Reset window if needed (sliding window)
            window_duration = 60.0  # 1 minute
            if current_time - limit_info["window_start"] >= window_duration:
                limit_info["window_start"] = current_time
                limit_info["request_count"] = 0
            
            # Check if within limit
            if limit_info["request_count"] < limit_info["requests_per_minute"]:
                limit_info["request_count"] += 1
                return True, 0.0
            
            # Calculate wait time
            time_until_reset = window_duration - (current_time - limit_info["window_start"])
            return False, max(0.0, time_until_reset)
    
    def record_rate_limit_hit(
        self,
        resource: str,
        reset_time: Optional[float] = None,
        component: str = "",
        subtask_id: Optional[str] = None,
        model_id: Optional[str] = None
    ):
        """Record a rate limit hit from external service."""
        failure_event = FailureEvent(
            failure_type=FailureType.RATE_LIMIT,
            component=component,
            error_message=f"Rate limit exceeded for resource: {resource}",
            subtask_id=subtask_id,
            model_id=model_id,
            severity=RiskLevel.LOW,
            context={
                "resource": resource,
                "reset_time": reset_time
            }
        )
        
        resilience_manager.handle_failure(failure_event)
    
    def get_rate_limit_status(self, resource: str) -> dict[str, Any]:
        """Get current rate limit status for a resource."""
        with self._lock:
            if resource not in self.rate_limits:
                return {"configured": False}
            
            limit_info = self.rate_limits[resource]
            current_time = time.time()
            
            return {
                "configured": True,
                "requests_per_minute": limit_info["requests_per_minute"],
                "current_count": limit_info["request_count"],
                "window_start": limit_info["window_start"],
                "time_until_reset": max(0.0, 60.0 - (current_time - limit_info["window_start"]))
            }


# Global instances
timeout_handler = TimeoutHandler()
adaptive_timeout_manager = AdaptiveTimeoutManager()
rate_limit_manager = RateLimitManager()


def with_adaptive_timeout(operation: str, component: str = ""):
    """Decorator for adaptive timeout based on historical performance."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                timeout_seconds = adaptive_timeout_manager.get_adaptive_timeout(operation)
                start_time = time.time()
                try:
                    result = await timeout_handler.execute_with_timeout(
                        func, timeout_seconds, operation, component,
                        None, None, *args, **kwargs
                    )
                    execution_time = time.time() - start_time
                    adaptive_timeout_manager.record_execution_time(operation, execution_time)
                    return result
                except TimeoutError:
                    adaptive_timeout_manager.record_execution_time(operation, timeout_seconds)
                    raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                # Get adaptive timeout
                timeout_seconds = adaptive_timeout_manager.get_adaptive_timeout(operation)
                
                start_time = time.time()
                try:
                    result = timeout_handler.execute_with_timeout(
                        func, timeout_seconds, operation, component,
                        None, None, *args, **kwargs
                    )
                    
                    # Record successful execution time
                    execution_time = time.time() - start_time
                    adaptive_timeout_manager.record_execution_time(operation, execution_time)
                    
                    return result
                    
                except TimeoutError:
                    # Record timeout (use timeout duration as execution time)
                    adaptive_timeout_manager.record_execution_time(operation, timeout_seconds)
                    raise
            
            return sync_wrapper
    return decorator


def with_rate_limit(resource: str, component: str = ""):
    """Decorator for rate limit checking."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Check rate limit
            allowed, wait_time = rate_limit_manager.check_rate_limit(resource)
            
            if not allowed:
                logger.warning(f"Rate limit exceeded for {resource}, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator