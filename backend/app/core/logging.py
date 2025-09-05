"""
Logging configuration for the application
"""
import logging
import sys
from typing import Dict, Any


def setup_logging(log_level: str = "INFO") -> None:
    """
    Setup application logging with structured format.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create custom formatter
    class StructuredFormatter(logging.Formatter):
        """Custom formatter for structured logging."""
        
        def format(self, record: logging.LogRecord) -> str:
            # Add common fields
            record.service = "clausecompass-api"
            record.version = "0.1.0"
            
            # Format the message
            formatted = super().format(record)
            return formatted
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Set formatter
    formatter = StructuredFormatter(
        fmt="%(asctime)s - %(service)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding structured logging context."""
    
    def __init__(self, logger: logging.Logger, **context: Any):
        self.logger = logger
        self.context = context
        self.old_factory = None
    
    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)


def log_function_call(logger: logging.Logger, func_name: str, **kwargs: Any) -> None:
    """
    Log function call with parameters (excluding sensitive data).
    
    Args:
        logger: Logger instance
        func_name: Function name
        **kwargs: Function parameters to log
    """
    # Filter out sensitive parameters
    sensitive_keys = {"password", "token", "key", "secret", "credential"}
    safe_kwargs = {
        k: v for k, v in kwargs.items()
        if not any(sensitive in k.lower() for sensitive in sensitive_keys)
    }
    
    logger.debug(f"Calling {func_name}", extra={"params": safe_kwargs})


def log_execution_time(logger: logging.Logger, operation: str, duration_ms: float) -> None:
    """
    Log execution time for operations.
    
    Args:
        logger: Logger instance
        operation: Operation description
        duration_ms: Duration in milliseconds
    """
    logger.info(
        f"Operation completed: {operation}",
        extra={"duration_ms": duration_ms, "operation": operation}
    )