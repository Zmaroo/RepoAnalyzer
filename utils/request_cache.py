"""
Request-Level Caching System

This module provides a caching mechanism that persists for the duration of a single request
or analysis operation, helping to avoid redundant work within a request lifecycle.
"""

import threading
from typing import Any, Dict, Optional, TypeVar, Generic, Callable
from contextlib import contextmanager
from functools import wraps

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
        
    def set(self, key: str, value: Any) -> None:
        """
        Store a value in the request cache.
        
        Args:
            key: The cache key
            value: The value to store
        """
        self._cache[key] = value
        
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from the request cache.
        
        Args:
            key: The cache key
            default: Value to return if key is not found

        Returns:
            The cached value or the default if not found
        """
        return self._cache.get(key, default)
    
    def delete(self, key: str) -> None:
        """
        Remove an item from the cache.
        
        Args:
            key: The cache key to remove
        """
        if key in self._cache:
            del self._cache[key]
            
    def has(self, key: str) -> bool:
        """
        Check if a key exists in the cache.
        
        Args:
            key: The cache key to check
            
        Returns:
            True if the key exists, False otherwise
        """
        return key in self._cache
        
    def clear(self) -> None:
        """Clear all entries from the request cache."""
        self._cache.clear()
        
    def size(self) -> int:
        """
        Get the number of items in the cache.
        
        Returns:
            The number of items in the cache
        """
        return len(self._cache)


# Thread-local storage for the current request cache
_thread_local = threading.local()


def get_current_request_cache() -> Optional[RequestCache]:
    """
    Get the currently active request cache for this thread.
    
    Returns:
        The active RequestCache instance or None if no cache is active
    """
    return getattr(_thread_local, 'current_cache', None)


def set_current_request_cache(cache: Optional[RequestCache]) -> None:
    """
    Set the current request cache for this thread.
    
    Args:
        cache: The RequestCache instance to set as current, or None to clear
    """
    if cache is None and hasattr(_thread_local, 'current_cache'):
        delattr(_thread_local, 'current_cache')
    else:
        _thread_local.current_cache = cache


@contextmanager
def request_cache_context():
    """
    Context manager providing a request-level cache.
    
    This creates a new RequestCache instance and makes it available during the context.
    The cache is automatically cleared when exiting the context.
    
    Example:
        with request_cache_context() as cache:
            # Use cache within this request/operation
            cache.set("key1", "value1")
            value = cache.get("key1")
    
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
        cache.clear()


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
        @cached_in_request
        def expensive_operation(arg1, arg2):
            # This result will be cached in the current request
            return do_expensive_work(arg1, arg2)
            
        # With custom key generation
        @cached_in_request(lambda repo_id, file_path: f"repo:{repo_id}:file:{file_path}")
        def process_file(repo_id, file_path):
            # Process with custom cache key
            return process_content(repo_id, file_path)
    
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
        def wrapper(*args, **kwargs):
            # Get the current request cache
            cache = get_current_request_cache()
            if cache is None:
                # No active request cache, just execute the function
                return func(*args, **kwargs)
            
            # Determine the cache key
            if key_fn is not None:
                # Use the user-provided key function
                cache_key = key_fn(*args, **kwargs)
            else:
                # Use the default key function
                cache_key = default_key_fn(func.__name__, *args, **kwargs)
            
            # Check if result is already cached
            if cache.has(cache_key):
                return cache.get(cache_key)
            
            # Execute the function and cache the result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
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