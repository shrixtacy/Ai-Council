"""Custom exceptions for the AI Council system."""

class AICouncilError(Exception):
    """Base exception for all AI Council errors."""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error

class ConfigurationError(AICouncilError):
    """Raised when there is a configuration issue."""
    pass

class ModelTimeoutError(AICouncilError):
    """Raised when a model request times out."""
    pass

class AuthenticationError(AICouncilError):
    """Raised when authentication fails."""
    pass

class RateLimitError(AICouncilError):
    """Raised when rate limits are exceeded."""
    pass

class ProviderError(AICouncilError):
    """Raised when an external model provider fails."""
    pass

class ValidationError(AICouncilError):
    """Raised when input validation fails."""
    pass

class OrchestrationError(AICouncilError):
    """Raised when an error occurs during orchestration."""
    pass
