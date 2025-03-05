"""
Request-Level Caching System

This module provides a caching mechanism that persists for the duration of a single request
or analysis operation, helping to avoid redundant work within a request lifecycle.
"""

import asyncio
from typing import Any, Dict, Optional, TypeVar, Generic, Callable, Set
from contextlib import contextmanager, asynccontextmanager
from functools import wraps
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.shutdown import register_shutdown_handler

T = TypeVar('T')

class RequestCache:
    """
    Cache for the duration of a single request/operation.
    
    This cache is designed to be used within a single request lifecycle to avoid
    redundant operations. It's not persistent across requests and should be created
    and destroyed within the context of a single request or operation.
    """
    
    def __init__(self):
        """Initialize an empty request cache."""
        self._cache: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._pending_tasks: Set[asyncio.Task] = set()
        register_shutdown_handler(self.cleanup)
        
    async def set(self, key: str, value: Any) -> None:
        """
        Store a value in the request cache.
        
        Args:
            key: The cache key
            value: The value to store
        """
        async with self._lock:
            self._cache[key] = value
        
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from the request cache.
        
        Args:
            key: The cache key
            default: Value to return if key is not found

        Returns:
            The cached value or the default if not found
        """
        async with self._lock:
            return self._cache.get(key, default)
    
    async def delete(self, key: str) -> None:
        """
        Remove an item from the cache.
        
        Args:
            key: The cache key to remove
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
            
    async def has(self, key: str) -> bool:
        """
        Check if a key exists in the cache.
        
        Args:
            key: The cache key to check
            
        Returns:
            True if the key exists, False otherwise
        """
        async with self._lock:
            return key in self._cache
        
    async def clear(self) -> None:
        """Clear all entries from the request cache."""
        async with self._lock:
            self._cache.clear()
        
    async def size(self) -> int:
        """
        Get the number of items in the cache.
        
        Returns:
            The number of items in the cache
        """
        async with self._lock:
            return len(self._cache)
            
    async def cleanup(self) -> None:
        """Clean up cache resources."""
        try:
            await self.clear()
            # Clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
        except Exception as e:
            print(f"Error cleaning up request cache: {e}")


# Thread-local storage for the current request cache
_request_context = {}


def get_current_request_cache() -> Optional[RequestCache]:
    """
    Get the currently active request cache for this task.
    
    Returns:
        The active RequestCache instance or None if no cache is active
    """
    task = asyncio.current_task()
    return _request_context.get(task) if task else None


def set_current_request_cache(cache: Optional[RequestCache]) -> None:
    """
    Set the current request cache for this task.
    
    Args:
        cache: The RequestCache instance to set as current, or None to clear
    """
    task = asyncio.current_task()
    if task:
        if cache is None and task in _request_context:
            del _request_context[task]
        else:
            _request_context[task] = cache


@asynccontextmanager
async def request_cache_context():
    """
    Context manager providing a request-level cache.
    
    This creates a new RequestCache instance and makes it available during the context.
    The cache is automatically cleared when exiting the context.
    
    Example:
        ```python
        async with request_cache_context() as cache:
            # Use cache within this request/operation
            await cache.set("key1", "value1")
            value = await cache.get("key1")
        ```
    
    Yields:
        RequestCache: The request cache instance
    """
    cache = RequestCache()
    previous_cache = get_current_request_cache()
    set_current_request_cache(cache)
    try:
        yield cache
    finally:
        set_current_request_cache(previous_cache)
        await cache.cleanup()


def cached_in_request(key_fn=None):
    """
    Decorator to cache function results within a request context.
    
    This decorator will cache the result of the decorated function in the
    current request cache. If no request cache is active, the function
    is executed normally without caching.
    
    Args:
        key_fn: Optional function to generate the cache key from the function arguments.
               If not provided, a default key based on function name and args is used.
    
    Example:
        ```python
        @cached_in_request
        async def expensive_operation(arg1, arg2):
            # This result will be cached in the current request
            return await do_expensive_work(arg1, arg2)
            
        # With custom key generation
        @cached_in_request(lambda repo_id, file_path: f"repo:{repo_id}:file:{file_path}")
        async def process_file(repo_id, file_path):
            # Process with custom cache key
            return await process_content(repo_id, file_path)
        ```
    
    Returns:
        The decorated function
    """
    def default_key_fn(fn_name, *args, **kwargs):
        """Generate a default cache key from function name and arguments."""
        arg_str = ':'.join(str(arg) for arg in args)
        kwarg_str = ':'.join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"fn:{fn_name}:{arg_str}:{kwarg_str}"
    
    # This is the actual decorator that will be returned
    def actual_decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get the current request cache
            cache = get_current_request_cache()
            if cache is None:
                # No active request cache, just execute the function
                return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Determine the cache key
            if key_fn is not None:
                # Use the user-provided key function
                cache_key = key_fn(*args, **kwargs)
            else:
                # Use the default key function
                cache_key = default_key_fn(func.__name__, *args, **kwargs)
            
            # Check if result is already cached
            if await cache.has(cache_key):
                return await cache.get(cache_key)
            
            # Execute the function and cache the result
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await cache.set(cache_key, result)
            return result
        return wrapper
    
    # Handle the case where decorator is used without parentheses
    if callable(key_fn) and not isinstance(key_fn, type) and key_fn.__name__ != '<lambda>':
        # @cached_in_request without parentheses
        func = key_fn
        key_fn = None
        return actual_decorator(func)
    
    # Handle the case where decorator is used with parentheses
    # @cached_in_request() or @cached_in_request(key_fn)
    return actual_decorator 