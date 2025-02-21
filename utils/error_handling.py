"""Unified error handling and logging system."""

import functools
import asyncio
import traceback
from typing import Optional, Callable, Any, Type, Union
from utils.logger import log

class ProcessingError(Exception):
    """Base exception for processing errors."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error
        self.traceback = traceback.format_exc() if original_error else None

class ParsingError(ProcessingError):
    """Raised when parsing fails."""
    pass

class DatabaseError(ProcessingError):
    """Raised when database operations fail."""
    pass

class CacheError(ProcessingError):
    """Raised when cache operations fail."""
    pass

def handle_errors(
    error_types: Union[Type[Exception], tuple] = Exception,
    default_return: Any = None,
    log_level: str = "error"
) -> Callable:
    """
    Decorator for handling synchronous function errors.
    
    Usage:
    @handle_errors(error_types=(ValueError, TypeError), default_return=None)
    def my_function():
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except error_types as e:
                log(
                    f"Error in {func.__name__}: {str(e)}",
                    level=log_level
                )
                if isinstance(e, ProcessingError) and e.traceback:
                    log(f"Traceback:\n{e.traceback}", level="debug")
                return default_return
        return wrapper
    return decorator

def handle_async_errors(
    error_types: Union[Type[Exception], tuple] = Exception,
    default_return: Any = None,
    log_level: str = "error"
) -> Callable:
    """
    Decorator for handling asynchronous function errors.
    
    Usage:
    @handle_async_errors(error_types=DatabaseError, default_return={})
    async def my_async_function():
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except error_types as e:
                log(
                    f"Error in async {func.__name__}: {str(e)}",
                    level=log_level
                )
                if isinstance(e, ProcessingError) and e.traceback:
                    log(f"Traceback:\n{e.traceback}", level="debug")
                return default_return
        return wrapper
    return decorator

class ErrorBoundary:
    """
    Context manager for error handling.
    
    Usage:
    with ErrorBoundary("Operation description", default_return=None):
        ...
    """
    def __init__(
        self,
        operation: str,
        error_types: Union[Type[Exception], tuple] = Exception,
        default_return: Any = None,
        log_level: str = "error"
    ):
        self.operation = operation
        self.error_types = error_types
        self.default_return = default_return
        self.log_level = log_level
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and issubclass(exc_type, self.error_types):
            log(
                f"Error in {self.operation}: {str(exc_val)}",
                level=self.log_level
            )
            if isinstance(exc_val, ProcessingError) and exc_val.traceback:
                log(f"Traceback:\n{exc_val.traceback}", level="debug")
            return True
        return False

class AsyncErrorBoundary:
    """
    Async context manager for error handling.
    
    Usage:
    async with AsyncErrorBoundary("Operation description"):
        ...
    """
    def __init__(
        self,
        operation: str,
        error_types: Union[Type[Exception], tuple] = Exception,
        default_return: Any = None,
        log_level: str = "error"
    ):
        self.operation = operation
        self.error_types = error_types
        self.default_return = default_return
        self.log_level = log_level
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and issubclass(exc_type, self.error_types):
            log(
                f"Error in {self.operation}: {str(exc_val)}",
                level=self.log_level
            )
            if isinstance(exc_val, ProcessingError) and exc_val.traceback:
                log(f"Traceback:\n{exc_val.traceback}", level="debug")
            return True
        return False 