"""Structured JSON logging configuration and utilities."""

import logging
import contextvars
from typing import Any, MutableMapping
from pythonjsonlogger import jsonlogger

# Context variables for distributed tracing
trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
span_id: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="")


class ContextAdapter(logging.LoggerAdapter):
    """Adapter that automatically injects trace_id and span_id into log records."""

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        # Get current context values
        current_trace_id = trace_id.get()
        current_span_id = span_id.get()

        # Ensure 'extra' dictionary exists
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        # Add context parameters to extra dictionary for structured log output
        if current_trace_id:
            kwargs["extra"]["trace_id"] = current_trace_id
        if current_span_id:
            kwargs["extra"]["span_id"] = current_span_id

        return msg, kwargs


def configure_json_logging(level: str = "INFO") -> None:
    """
    Configure the root logger with JSON formatting.
    This should be called as early as possible in system startup.
    """
    logger = logging.getLogger()
    
    # Set log level based on string or default to INFO
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Clear existing handlers to prevent duplicates
    if logger.handlers:
        logger.handlers.clear()

    # Create stream handler
    log_handler = logging.StreamHandler()

    # Configure the JSON formatter
    # Including common fields in output by default in 'fmt' string
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"levelname": "level", "asctime": "timestamp"}
    )
    
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)


def get_logger(name: str) -> ContextAdapter:
    """
    Get a context-aware logger adapter.
    
    Args:
        name: The name of the logger, typically __name__
        
    Returns:
        A ContextAdapter wrapping a standard logger
    """
    logger = logging.getLogger(name)
    return ContextAdapter(logger, {})
