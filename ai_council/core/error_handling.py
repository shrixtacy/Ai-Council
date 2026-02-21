"""Error handling infrastructure for AI Council.

This module provides centralized error handling utilities including:
- ErrorResponseFactory: Creates standardized error responses
- with_error_handling: Decorator for consistent error handling
- Pipeline stage abstractions for cleaner code organization
"""

import functools
import logging
from typing import Callable, Dict, Optional, Any, Type, List

from .exceptions import (
    AICouncilError, ConfigurationError, ModelTimeoutError,
    AuthenticationError, RateLimitError, ProviderError,
    ValidationError, OrchestrationError
)
from .models import FinalResponse, CostBreakdown


logger = logging.getLogger(__name__)


# Default mapping of exception types to error type strings
DEFAULT_ERROR_TYPE_MAPPING: Dict[Type[Exception], str] = {
    ConfigurationError: "ConfigurationError",
    ValidationError: "ValidationError",
    AuthenticationError: "AuthenticationError",
    ModelTimeoutError: "ModelTimeoutError",
    RateLimitError: "RateLimitError",
    ProviderError: "ProviderError",
    OrchestrationError: "OrchestrationError",
    AICouncilError: "AICouncilError",
}


class ErrorResponseFactory:
    """
    Factory for creating standardized error responses.
    
    This class centralizes error response creation, ensuring consistent
    error handling across the application.
    """
    
    def __init__(
        self,
        error_type_mapping: Optional[Dict[Type[Exception], str]] = None
    ):
        """
        Initialize the error response factory.
        
        Args:
            error_type_mapping: Optional custom mapping of exception types to error type strings.
                               If not provided, uses DEFAULT_ERROR_TYPE_MAPPING.
        """
        self._error_type_mapping = error_type_mapping or DEFAULT_ERROR_TYPE_MAPPING.copy()
        self._custom_handlers: Dict[Type[Exception], Callable[[Exception], FinalResponse]] = {}
    
    def register_handler(
        self,
        exception_type: Type[Exception],
        handler: Callable[[Exception], FinalResponse]
    ) -> None:
        """
        Register a custom handler for a specific exception type.
        
        Args:
            exception_type: The exception type to handle
            handler: Custom handler function that takes an exception and returns a FinalResponse
        """
        self._custom_handlers[exception_type] = handler
    
    def create_error_response(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> FinalResponse:
        """
        Create a standardized error response from an exception.
        
        Args:
            exception: The exception that occurred
            context: Optional additional context for the error response
            
        Returns:
            FinalResponse: A standardized error response
        """
        context = context or {}
        
        # Check for custom handler first
        for exc_type, handler in self._custom_handlers.items():
            if isinstance(exception, exc_type):
                return handler(exception)
        
        # Determine error type from mapping
        error_type = self._get_error_type(exception)
        
        # Determine log level based on exception severity
        log_level = self._get_log_level(exception)
        
        # Log the error
        log_message = f"{error_type}: {str(exception)}"
        if context.get('component'):
            log_message = f"{context['component']} - {log_message}"
        
        getattr(logger, log_level)(log_message)
        
        # Create and return the error response
        # Fix: Explicitly check for execution_time presence using 'is not None'
        exec_time = context.get('execution_time')
        cost_breakdown = CostBreakdown(execution_time=exec_time) if exec_time is not None else None
        
        return FinalResponse(
            content="",
            overall_confidence=0.0,
            success=False,
            error_message=str(exception),
            error_type=error_type,
            models_used=context.get('models_used', []),
            cost_breakdown=cost_breakdown
        )
    
    def _get_error_type(self, exception: Exception) -> str:
        """
        Get the error type string for an exception.
        
        Args:
            exception: The exception to get the error type for
            
        Returns:
            str: The error type string
        """
        for exc_type, error_type in self._error_type_mapping.items():
            if isinstance(exception, exc_type):
                return error_type
        
        # Default to SystemError for unknown exceptions
        return "SystemError"
    
    def _get_log_level(self, exception: Exception) -> str:
        """
        Determine the appropriate log level for an exception.
        
        Args:
            exception: The exception to log
            
        Returns:
            str: The log level string
        """
        if isinstance(exception, (ValidationError, RateLimitError)):
            return "warning"
        elif isinstance(exception, ConfigurationError):
            return "error"
        elif isinstance(exception, AICouncilError):
            return "error"
        else:
            return "error"
    
    def get_error_type_mapping(self) -> Dict[str, str]:
        """
        Get the current error type mapping.
        
        Returns:
            Dict mapping exception class names to error type strings
        """
        return {
            exc_type.__name__: error_type
            for exc_type, error_type in self._error_type_mapping.items()
        }


# Global default factory instance
_default_factory = ErrorResponseFactory()


def create_error_response(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None
) -> FinalResponse:
    """
    Convenience function to create an error response using the default factory.
    
    Args:
        exception: The exception that occurred
        context: Optional additional context for the error response
        
    Returns:
        FinalResponse: A standardized error response
    """
    return _default_factory.create_error_response(exception, context)


def with_error_handling(
    stage_name: str,
    error_handlers: Optional[Dict[Type[Exception], Callable[[Exception], FinalResponse]]] = None,
    log_errors: bool = True
):
    """
    Decorator for consistent error handling in pipeline stages.
    
    This decorator wraps a function with comprehensive error handling,
    creating standardized error responses and optionally logging errors.
    
    Args:
        stage_name: Name of the pipeline stage being decorated
        error_handlers: Optional dict of custom exception handlers
        log_errors: Whether to log errors (default: True)
        
    Returns:
        Decorated function with error handling
        
    Example:
        @with_error_handling("task_creation")
        def create_task(self, user_input):
            # ... task creation logic
            pass
    """
    def decorator(func: Callable[..., FinalResponse]) -> Callable[..., FinalResponse]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> FinalResponse:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {stage_name}: {str(e)}")
                
                # Check for custom handlers
                if error_handlers:
                    for exc_type, handler in error_handlers.items():
                        if isinstance(e, exc_type):
                            return handler(e)
                
                # Use default factory for error response
                return create_error_response(
                    e,
                    context={'component': stage_name}
                )
        
        return wrapper
    return decorator


def with_ai_council_error_handling(
    stage_name: str,
    reraise_ai_council_errors: bool = True
):
    """
    Decorator that handles AICouncilError exceptions with standardized responses,
    while optionally re-raising them for critical errors.
    
    Args:
        stage_name: Name of the pipeline stage
        reraise_ai_council_errors: Whether to re-raise AICouncilError exceptions
        
    Returns:
        Decorated function with AICouncilError handling
    """
    def decorator(func: Callable[..., FinalResponse]) -> Callable[..., FinalResponse]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> FinalResponse:
            try:
                return func(*args, **kwargs)
            except AICouncilError as e:
                if reraise_ai_council_errors:
                    logger.error(f"Critical error in {stage_name}: {str(e)}")
                    raise
                else:
                    logger.warning(f"Handled error in {stage_name}: {str(e)}")
                    return create_error_response(
                        e,
                        context={'component': stage_name}
                    )
            except Exception as e:
                logger.error(f"Unexpected error in {stage_name}: {str(e)}")
                return create_error_response(
                    e,
                    context={'component': stage_name}
                )
        
        return wrapper
    return decorator


class PipelineStage:
    """
    Base class for pipeline stages with built-in error handling.
    
    This class provides a foundation for implementing pipeline stages
    with consistent error handling and logging.
    """
    
    def __init__(self, name: str):
        """
        Initialize the pipeline stage.
        
        Args:
            name: The name of the stage
        """
        self.name = name
        self._logger = logging.getLogger(f"{__name__}.{name}")
    
    def execute(self, *args, **kwargs) -> FinalResponse:
        """
        Execute the pipeline stage.
        
        This method should be overridden by subclasses to implement
        the actual stage logic.
        
        Returns:
            FinalResponse: The result of the stage execution
        """
        raise NotImplementedError("Subclasses must implement execute()")
    
    def _handle_error(self, error: Exception) -> FinalResponse:
        """
        Handle an error that occurred during stage execution.
        
        Args:
            error: The exception that occurred
            
        Returns:
            FinalResponse: A standardized error response
        """
        self._logger.error(f"Error in {self.name}: {str(error)}")
        return create_error_response(
            error,
            context={'component': self.name}
        )


class Result:
    """
    A Result type for representing success/failure states.
    
    This class provides a cleaner alternative to exceptions for
    handling errors in pipeline stages.
    """
    
    def __init__(
        self,
        value: Any = None,
        error: Optional[Exception] = None,
        is_success: bool = True
    ):
        """
        Initialize a Result.
        
        Args:
            value: The success value (if any)
            error: The error (if any)
            is_success: Whether this result represents a success
        """
        self.value = value
        self.error = error
        self.is_success = is_success
    
    @classmethod
    def success(cls, value: Any) -> 'Result':
        """Create a success result."""
        return cls(value=value, is_success=True)
    
    @classmethod
    def failure(cls, error: Exception) -> 'Result':
        """Create a failure result."""
        return cls(error=error, is_success=False)
    
    def get_or_else(self, default: Any) -> Any:
        """
        Get the value or a default if this is a failure.
        
        Args:
            default: The default value to return on failure
            
        Returns:
            The value if success, otherwise the default
        """
        return self.value if self.is_success else default
    
    def map(self, func: Callable[[Any], Any]) -> 'Result':
        """
        Map the value if this is a success.
        
        Args:
            func: Function to apply to the value
            
        Returns:
            A new Result with the mapped value (if success)
        """
        if self.is_success:
            try:
                return Result.success(func(self.value))
            except Exception as e:
                return Result.failure(e)
        return self
