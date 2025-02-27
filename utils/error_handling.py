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
    """Async context manager for error boundaries.
    
    This context manager provides a way to handle errors in asynchronous code blocks without
    cluttering the code with multiple try/except blocks. It logs the error with information
    about which operation was being performed when the error occurred.
    
    Unlike the handle_async_errors decorator, this doesn't return a default value or swallow
    the exception - it just logs the error and then re-raises it. This is useful when you 
    want to log errors but still need them to propagate up the call stack.
    
    Args:
        operation: A string describing the operation being performed. This appears in the
                 error log to help identify where the error occurred.
        error_types: A tuple of exception types to catch. By default, it catches all exceptions,
                    but you can narrow it to specific error types.
    
    Yields:
        Control to the context body.
    
    Raises:
        Any exceptions caught that match error_types will be logged and then re-raised.
    
    Example:
        ```python
        async def process_data(data):
            async with AsyncErrorBoundary("data processing", error_types=(ValueError, TypeError)):
                # If any ValueError or TypeError occurs in this block:
                # 1. It will be logged with the operation name "data processing"
                # 2. The exception will still be raised after logging
                result = await validate_data(data)
                processed = await transform_data(result)
                return processed
        ```
    """
    try:
        yield
    except error_types as e:
        from utils.logger import log
        log(f"Error in {operation}: {str(e)}", level="error")
        raise

def handle_async_errors(error_types=Exception, default_return=None):
    """Decorator for handling async function errors.
    
    This decorator wraps asynchronous functions to provide consistent error handling.
    When an exception matching the specified error_types occurs in the decorated function,
    the error is logged and the function returns the default_return value instead of
    propagating the exception.
    
    This is particularly useful for database operations where you want to gracefully
    handle failures without crashing the application, while still logging the error
    for debugging purposes.
    
    Args:
        error_types: Exception type or tuple of exception types to catch.
                    Any other exception types will be propagated normally.
        default_return: Value to return on error (default: None).
                       This will be the return value of the function when an error occurs.
    
    Returns:
        A decorator function that wraps the target async function.
    
    Example:
        ```python
        @handle_async_errors(error_types=DatabaseError, default_return=False)
        async def fetch_data(id: int) -> Optional[Dict]:
            # If this raises a DatabaseError, the function will:
            # 1. Log the error
            # 2. Return False instead of propagating the exception
            result = await database.query(f"SELECT * FROM table WHERE id = {id}")
            return result
            
        # Usage:
        data = await fetch_data(123)
        if data is False:  # Error occurred
            # Handle the error case
            pass
        else:
            # Process the data
            process_data(data)
        ```
    """
    import inspect
    from typing import List, Dict, Optional, Awaitable, get_type_hints

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except error_types as e:
                from utils.logger import log
                log(f"Error in {func.__name__}: {e}", level="error")
                
                # If default_return is explicitly provided, use that
                if default_return is not None:
                    return default_return
                
                # Otherwise, try to determine appropriate return type based on function annotation
                try:
                    return_type_hints = get_type_hints(func)
                    if 'return' in return_type_hints:
                        return_hint = return_type_hints['return']
                        # Handle various common return types
                        origin = getattr(return_hint, '__origin__', None)
                        if origin is list or (hasattr(return_hint, '_name') and return_hint._name == 'List'):
                            return []
                        elif origin is dict or (hasattr(return_hint, '_name') and return_hint._name == 'Dict'):
                            return {}
                        elif return_hint is bool or return_hint == bool:
                            return False
                        elif inspect.isclass(return_hint) and issubclass(return_hint, (list, List)):
                            return []
                        elif inspect.isclass(return_hint) and issubclass(return_hint, (dict, Dict)):
                            return {}
                except Exception as type_error:
                    log(f"Error determining return type for {func.__name__}: {type_error}", level="debug")
                
                # Default fallback
                return None
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