"""Comprehensive failure handling and resilience system for AI Council."""

import asyncio
import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Union
from uuid import uuid4

from .models import AgentResponse, Subtask, FinalResponse, RiskLevel
from .interfaces import AIModel, ModelError


logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of failures that can occur in the system."""
    API_FAILURE = "api_failure"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    NETWORK_ERROR = "network_error"
    MODEL_UNAVAILABLE = "model_unavailable"
    QUOTA_EXCEEDED = "quota_exceeded"
    VALIDATION_ERROR = "validation_error"
    PARTIAL_FAILURE = "partial_failure"
    SYSTEM_OVERLOAD = "system_overload"
    UNKNOWN = "unknown"


class RetryStrategy(Enum):
    """Retry strategies for different failure types."""
    IMMEDIATE = "immediate"
    LINEAR_BACKOFF = "linear_backoff"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


class CircuitBreakerState(Enum):
    """States for circuit breaker pattern."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class FailureEvent:
    """Represents a failure event in the system."""
    id: str = field(default_factory=lambda: str(uuid4()))
    failure_type: FailureType = FailureType.UNKNOWN
    component: str = ""
    error_message: str = ""
    subtask_id: Optional[str] = None
    model_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    severity: RiskLevel = RiskLevel.LOW
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    resolved: bool = False
    resolution_strategy: Optional[str] = None


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    timeout_per_attempt: float = 30.0


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    monitoring_window: float = 300.0  # 5 minutes


class FailureHandler(ABC):
    """Abstract base class for handling specific types of failures."""
    
    @abstractmethod
    def can_handle(self, failure: FailureEvent) -> bool:
        """Check if this handler can handle the given failure."""
        pass
    
    @abstractmethod
    def handle(self, failure: FailureEvent) -> 'RecoveryAction':
        """Handle the failure and return a recovery action."""
        pass


@dataclass
class RecoveryAction:
    """Represents an action to recover from a failure."""
    action_type: str
    should_retry: bool = False
    retry_delay: float = 0.0
    fallback_model: Optional[str] = None
    degraded_mode: bool = False
    skip_subtask: bool = False
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CircuitBreaker:
    """Circuit breaker implementation for preventing cascade failures."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.failure_times: List[datetime] = []
        self._lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function through the circuit breaker."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info(f"Circuit breaker {self.name} moved to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
            
    async def async_call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute an asynchronous function through the circuit breaker."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info(f"Circuit breaker {self.name} moved to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        
        time_since_failure = datetime.utcnow() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout
    
    def _on_success(self):
        """Handle successful execution."""
        with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    self.failure_times.clear()
                    logger.info(f"Circuit breaker {self.name} reset to CLOSED")
    
    def _on_failure(self):
        """Handle failed execution."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            self.failure_times.append(self.last_failure_time)
            
            # Clean old failure times outside monitoring window
            cutoff_time = self.last_failure_time - timedelta(seconds=self.config.monitoring_window)
            self.failure_times = [t for t in self.failure_times if t > cutoff_time]
            
            if (self.state == CircuitBreakerState.CLOSED and 
                len(self.failure_times) >= self.config.failure_threshold):
                self.state = CircuitBreakerState.OPEN
                self.success_count = 0
                logger.warning(f"Circuit breaker {self.name} opened due to {len(self.failure_times)} failures")
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                self.success_count = 0
                logger.warning(f"Circuit breaker {self.name} reopened after failure in HALF_OPEN state")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class APIFailureHandler(FailureHandler):
    """Handler for API-related failures."""
    
    def __init__(self, retry_config: RetryConfig):
        self.retry_config = retry_config
    
    def can_handle(self, failure: FailureEvent) -> bool:
        return failure.failure_type in [
            FailureType.API_FAILURE,
            FailureType.NETWORK_ERROR,
            FailureType.TIMEOUT
        ]
    
    def handle(self, failure: FailureEvent) -> RecoveryAction:
        if failure.retry_count >= self.retry_config.max_attempts:
            return RecoveryAction(
                action_type="max_retries_exceeded",
                should_retry=False,
                error_message=f"Max retries ({self.retry_config.max_attempts}) exceeded"
            )
        
        delay = self._calculate_retry_delay(failure.retry_count)
        
        return RecoveryAction(
            action_type="retry_with_backoff",
            should_retry=True,
            retry_delay=delay,
            metadata={
                "retry_attempt": failure.retry_count + 1,
                "strategy": self.retry_config.strategy.value
            }
        )
    
    def _calculate_retry_delay(self, retry_count: int) -> float:
        """Calculate delay for retry based on strategy."""
        if self.retry_config.strategy == RetryStrategy.IMMEDIATE:
            return 0.0
        elif self.retry_config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.retry_config.base_delay
        elif self.retry_config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.retry_config.base_delay * (retry_count + 1)
        elif self.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.retry_config.base_delay * (self.retry_config.backoff_multiplier ** retry_count)
        else:
            delay = self.retry_config.base_delay
        
        # Apply jitter if enabled
        if self.retry_config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # 50-100% of calculated delay
        
        return min(delay, self.retry_config.max_delay)


class RateLimitHandler(FailureHandler):
    """Handler for rate limiting failures."""
    
    def __init__(self):
        self.rate_limit_windows: Dict[str, datetime] = {}
    
    def can_handle(self, failure: FailureEvent) -> bool:
        return failure.failure_type == FailureType.RATE_LIMIT
    
    def handle(self, failure: FailureEvent) -> RecoveryAction:
        model_id = failure.model_id or "unknown"
        
        # Extract rate limit reset time from error context if available
        reset_time = failure.context.get('reset_time')
        if reset_time:
            delay = max(0, reset_time - time.time())
        else:
            # Default exponential backoff for rate limits
            delay = min(60.0, 5.0 * (2 ** failure.retry_count))
        
        self.rate_limit_windows[model_id] = datetime.utcnow() + timedelta(seconds=delay)
        
        return RecoveryAction(
            action_type="rate_limit_backoff",
            should_retry=True,
            retry_delay=delay,
            metadata={
                "rate_limited_until": self.rate_limit_windows[model_id].isoformat(),
                "model_id": model_id
            }
        )


class ModelUnavailableHandler(FailureHandler):
    """Handler for model unavailability failures."""
    
    def __init__(self, fallback_registry: Dict[str, List[str]]):
        self.fallback_registry = fallback_registry
    
    def can_handle(self, failure: FailureEvent) -> bool:
        return failure.failure_type in [
            FailureType.MODEL_UNAVAILABLE,
            FailureType.QUOTA_EXCEEDED
        ]
    
    def handle(self, failure: FailureEvent) -> RecoveryAction:
        model_id = failure.model_id
        if not model_id:
            return RecoveryAction(
                action_type="no_fallback_available",
                should_retry=False,
                error_message="No model ID provided for fallback selection"
            )
        
        fallback_models = self.fallback_registry.get(model_id, [])
        if not fallback_models:
            return RecoveryAction(
                action_type="no_fallback_configured",
                should_retry=False,
                error_message=f"No fallback models configured for {model_id}"
            )
        
        # Select first available fallback (could be enhanced with smarter selection)
        fallback_model = fallback_models[0]
        
        return RecoveryAction(
            action_type="fallback_model",
            should_retry=True,
            fallback_model=fallback_model,
            metadata={
                "original_model": model_id,
                "fallback_model": fallback_model,
                "available_fallbacks": fallback_models
            }
        )


class PartialFailureHandler(FailureHandler):
    """Handler for partial execution failures."""
    
    def can_handle(self, failure: FailureEvent) -> bool:
        return failure.failure_type == FailureType.PARTIAL_FAILURE
    
    def handle(self, failure: FailureEvent) -> RecoveryAction:
        # For partial failures, continue with degraded results
        return RecoveryAction(
            action_type="continue_degraded",
            should_retry=False,
            degraded_mode=True,
            metadata={
                "degradation_reason": "partial_execution_failure",
                "failed_subtasks": failure.context.get('failed_subtasks', [])
            }
        )


class SystemOverloadHandler(FailureHandler):
    """Handler for system overload situations."""
    
    def can_handle(self, failure: FailureEvent) -> bool:
        return failure.failure_type == FailureType.SYSTEM_OVERLOAD
    
    def handle(self, failure: FailureEvent) -> RecoveryAction:
        # Implement load shedding by skipping non-critical subtasks
        return RecoveryAction(
            action_type="load_shedding",
            should_retry=False,
            skip_subtask=True,
            metadata={
                "reason": "system_overload",
                "load_level": failure.context.get('load_level', 'unknown')
            }
        )


class FailureIsolator:
    """Isolates failures to prevent cascade effects."""
    
    def __init__(self):
        self.isolated_components: Dict[str, datetime] = {}
        self.isolation_duration = timedelta(minutes=5)
    
    def isolate_component(self, component: str, reason: str):
        """Isolate a component temporarily."""
        self.isolated_components[component] = datetime.utcnow()
        logger.warning(f"Isolated component {component}: {reason}")
    
    def is_isolated(self, component: str) -> bool:
        """Check if a component is currently isolated."""
        if component not in self.isolated_components:
            return False
        
        isolation_time = self.isolated_components[component]
        if datetime.utcnow() - isolation_time > self.isolation_duration:
            del self.isolated_components[component]
            logger.info(f"Component {component} isolation expired")
            return False
        
        return True
    
    def release_isolation(self, component: str):
        """Manually release component isolation."""
        if component in self.isolated_components:
            del self.isolated_components[component]
            logger.info(f"Component {component} isolation manually released")


class ResilienceManager:
    """Main manager for system resilience and failure handling."""
    
    def __init__(self):
        self.handlers: List[FailureHandler] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.failure_isolator = FailureIsolator()
        self.failure_history: List[FailureEvent] = []
        self.max_history_size = 1000
        
        # Initialize default handlers
        self._initialize_default_handlers()
    
    def _initialize_default_handlers(self):
        """Initialize default failure handlers."""
        # API failure handler with exponential backoff
        api_retry_config = RetryConfig(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=30.0
        )
        self.handlers.append(APIFailureHandler(api_retry_config))
        
        # Rate limit handler
        self.handlers.append(RateLimitHandler())
        
        # Model unavailable handler (needs to be configured with fallback registry)
        fallback_registry = {}  # Will be populated by configuration
        self.handlers.append(ModelUnavailableHandler(fallback_registry))
        
        # Partial failure handler
        self.handlers.append(PartialFailureHandler())
        
        # System overload handler
        self.handlers.append(SystemOverloadHandler())
    
    def register_handler(self, handler: FailureHandler):
        """Register a custom failure handler."""
        self.handlers.append(handler)
    
    def create_circuit_breaker(self, name: str, config: CircuitBreakerConfig) -> CircuitBreaker:
        """Create and register a circuit breaker."""
        circuit_breaker = CircuitBreaker(name, config)
        self.circuit_breakers[name] = circuit_breaker
        return circuit_breaker
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name."""
        return self.circuit_breakers.get(name)
    
    def handle_failure(self, failure: FailureEvent) -> RecoveryAction:
        """Handle a failure event using registered handlers."""
        # Record failure in history
        self.failure_history.append(failure)
        if len(self.failure_history) > self.max_history_size:
            self.failure_history.pop(0)
        
        logger.warning(
            f"Handling failure: {failure.failure_type.value} in {failure.component} - "
            f"{failure.error_message}"
        )
        
        # Find appropriate handler
        for handler in self.handlers:
            if handler.can_handle(failure):
                try:
                    recovery_action = handler.handle(failure)
                    
                    # Update failure event with resolution
                    failure.resolution_strategy = recovery_action.action_type
                    if not recovery_action.should_retry:
                        failure.resolved = True
                    
                    logger.info(f"Recovery action: {recovery_action.action_type}")
                    return recovery_action
                    
                except Exception as e:
                    logger.error(f"Handler {type(handler).__name__} failed: {str(e)}")
                    continue
        
        # No handler found, return default action
        logger.warning(f"No handler found for failure type {failure.failure_type.value}")
        return RecoveryAction(
            action_type="unhandled_failure",
            should_retry=False,
            error_message=f"No handler available for {failure.failure_type.value}"
        )
    
    def update_fallback_registry(self, fallback_registry: Dict[str, List[str]]):
        """Update fallback model registry for model unavailable handler."""
        for handler in self.handlers:
            if isinstance(handler, ModelUnavailableHandler):
                handler.fallback_registry.update(fallback_registry)
                break
    
    def get_failure_statistics(self) -> Dict[str, Any]:
        """Get statistics about recent failures."""
        if not self.failure_history:
            return {
                "total_failures": 0,
                "recent_failures": 0,
                "failure_counts": {},
                "resolution_rate": 0.0,
                "circuit_breaker_states": {
                    name: cb.state.value 
                    for name, cb in self.circuit_breakers.items()
                },
                "isolated_components": list(self.failure_isolator.isolated_components.keys())
            }
        
        # Count failures by type
        failure_counts = {}
        resolved_count = 0
        recent_failures = []
        
        # Look at failures in the last hour
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        for failure in self.failure_history:
            if failure.timestamp > cutoff_time:
                recent_failures.append(failure)
                
                failure_type = failure.failure_type.value
                failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1
                
                if failure.resolved:
                    resolved_count += 1
        
        # Calculate resolution rate
        resolution_rate = resolved_count / len(recent_failures) if recent_failures else 0.0
        
        # Get circuit breaker states
        circuit_breaker_states = {
            name: cb.state.value 
            for name, cb in self.circuit_breakers.items()
        }
        
        return {
            "total_failures": len(self.failure_history),
            "recent_failures": len(recent_failures),
            "failure_counts": failure_counts,
            "resolution_rate": resolution_rate,
            "circuit_breaker_states": circuit_breaker_states,
            "isolated_components": list(self.failure_isolator.isolated_components.keys())
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform system health check."""
        health_status = {
            "overall_health": "healthy",
            "components": {},
            "alerts": []
        }
        
        # Check circuit breaker states
        open_breakers = []
        for name, cb in self.circuit_breakers.items():
            if cb.state == CircuitBreakerState.OPEN:
                open_breakers.append(name)
                health_status["components"][name] = "unhealthy"
            elif cb.state == CircuitBreakerState.HALF_OPEN:
                health_status["components"][name] = "recovering"
            else:
                health_status["components"][name] = "healthy"
        
        # Check for isolated components
        isolated = list(self.failure_isolator.isolated_components.keys())
        
        # Determine overall health
        if open_breakers or isolated:
            health_status["overall_health"] = "degraded"
            
            if open_breakers:
                health_status["alerts"].append(f"Circuit breakers open: {', '.join(open_breakers)}")
            
            if isolated:
                health_status["alerts"].append(f"Components isolated: {', '.join(isolated)}")
        
        # Check recent failure rate
        stats = self.get_failure_statistics()
        recent_failures_count = stats.get("recent_failures", 0)
        if recent_failures_count > 10:  # Threshold for concern
            health_status["overall_health"] = "degraded"
            health_status["alerts"].append(f"High failure rate: {recent_failures_count} failures in last hour")
        
        # Add circuit breaker information
        health_status["circuit_breakers"] = stats.get("circuit_breaker_states", {})
        
        return health_status


# Global resilience manager instance
resilience_manager = ResilienceManager()


def create_failure_event(
    failure_type: FailureType,
    component: str,
    error_message: str,
    subtask_id: Optional[str] = None,
    model_id: Optional[str] = None,
    severity: RiskLevel = RiskLevel.LOW,
    context: Optional[Dict[str, Any]] = None
) -> FailureEvent:
    """Convenience function to create failure events."""
    return FailureEvent(
        failure_type=failure_type,
        component=component,
        error_message=error_message,
        subtask_id=subtask_id,
        model_id=model_id,
        severity=severity,
        context=context or {}
    )