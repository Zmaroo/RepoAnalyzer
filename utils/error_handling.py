"""Error handling utilities."""

from typing import Type, Tuple, Callable, Any
from functools import wraps
from contextlib import contextmanager, asynccontextmanager

class ProcessingError(Exception):
    """Base class for processing errors."""
    pass

class ParsingError(ProcessingError):
    """Error during parsing operations."""
    pass

class DatabaseError(Exception):
    """Base class for database errors."""
    pass

class PostgresError(DatabaseError):
    """PostgreSQL specific errors."""
    pass

class Neo4jError(DatabaseError):
    """Neo4j specific errors."""
    pass

class TransactionError(DatabaseError):
    """Transaction coordination errors."""
    pass

class CacheError(DatabaseError):
    """Cache operation errors."""
    pass

def handle_errors(error_types: Tuple[Type[Exception], ...] = (Exception,)):
    """Decorator for handling errors."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except error_types as e:
                from utils.logger import log
                log(f"Error in {func.__name__}: {str(e)}", level="error")
                return None
        return wrapper
    return decorator

@asynccontextmanager
async def AsyncErrorBoundary(operation: str, error_types: Tuple[Type[Exception], ...] = (Exception,)):
    """Async context manager for error boundaries."""
    try:
        yield
    except error_types as e:
        from utils.logger import log
        log(f"Error in {operation}: {str(e)}", level="error")
        raise

def handle_async_errors(error_types=Exception, default_return=None):
    """Decorator for handling async function errors.
    
    Args:
        error_types: Exception type or tuple of types to catch
        default_return: Value to return on error (default: None)
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except error_types as e:
                from utils.logger import log
                log(f"Error in {func.__name__}: {e}", level="error")
                return default_return if default_return is not None else None
        return wrapper
    return decorator

@contextmanager
def ErrorBoundary(operation_name: str, error_types: Tuple[Type[Exception], ...] = (Exception,)):
    """Context manager for error handling."""
    try:
        yield
    except error_types as e:
        from utils.logger import log
        log(f"Error in {operation_name}: {str(e)}", level="error")
        raise 