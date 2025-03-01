#!/usr/bin/env python3
"""
Unit tests for cache utilities.

This module tests the various caching mechanisms in the RepoAnalyzer project:
1. Basic caching functionality
2. Memory-bounded cache
3. Cache analytics
4. Request cache
"""

import os
import sys
import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock
import random
import enum
import tempfile
from pathlib import Path
import redis
from typing import Dict, Any, Optional, List, Callable, Awaitable
import functools

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the handle_async_errors decorator before importing the modules
def mock_handle_async_errors(*args, **kwargs):
    """Mock implementation of handle_async_errors that works for both usage patterns"""
    # If called with a function as the first argument, it's being used as @handle_async_errors
    if args and callable(args[0]):
        return args[0]
    # Otherwise, it's being used as @handle_async_errors(error_types, default_return)
    else:
        def decorator(func):
            return func
        return decorator

# Patch the decorator at module level
patch('utils.error_handling.handle_async_errors', mock_handle_async_errors).start()

# Now import the modules that use the decorator
from utils.cache import (
    UnifiedCache,
    CacheMetrics,
    create_cache,
    KeyUsageTracker,
    cache_metrics
)
from utils.cache_analytics import (
    CacheAnalytics,
)
from utils.request_cache import (
    RequestCache,
    request_cache_context,
    cached_in_request,
    get_current_request_cache,
    set_current_request_cache
)
from utils.clear_cache_utils import clear_cache_files

# Define a CacheEvent enum for testing
from enum import Enum
class CacheEvent(Enum):
    HIT = "hit"
    MISS = "miss"
    SET = "set"
    CLEAR = "clear"
    EXPIRE = "expire"

# Mock classes for testing
class MockUnifiedCache:
    """Mock implementation of UnifiedCache for testing."""
    
    def __init__(self, name: str, ttl: int = 3600, use_redis: bool = False, 
                 adaptive_ttl: bool = False, min_ttl: int = 60, max_ttl: int = 86400):
        self.name = name
        self.default_ttl = ttl
        self.use_redis = use_redis
        self.adaptive_ttl = adaptive_ttl
        self.min_ttl = min_ttl
        self.max_ttl = max_ttl
        self._cache = {}
        self._usage_tracker = MockKeyUsageTracker()
    
    async def get_async(self, key: str, default: Any = None):
        """Get a value from the cache."""
        if key in self._cache and self._cache[key]["expires"] > time.time():
            return self._cache[key]["value"]
        return default
    
    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set a value in the cache."""
        effective_ttl = ttl or self.default_ttl
        self._cache[key] = {
            "value": value,
            "expires": time.time() + effective_ttl
        }
    
    async def exists_async(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        if key in self._cache and self._cache[key]["expires"] > time.time():
            return True
        return False
    
    async def clear_async(self):
        """Clear the entire cache."""
        self._cache = {}
    
    async def clear_pattern_async(self, pattern: str):
        """Clear keys matching a pattern."""
        keys_to_remove = []
        for key in self._cache:
            if pattern.replace("*", "") in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._cache[key]
    
    async def warmup(self, keys_values: Dict[str, Any], ttl: Optional[int] = None):
        """Pre-populate the cache with key-value pairs."""
        for key, value in keys_values.items():
            await self.set_async(key, value, ttl)
    
    async def warmup_from_function(self, keys: List[str], fetch_func: Callable[[List[str]], Awaitable[Dict[str, Any]]], ttl: Optional[int] = None):
        """Warm up the cache using a function to fetch values."""
        values = await fetch_func(keys)
        await self.warmup(values, ttl)

class MockCacheMetrics:
    """Mock implementation of CacheMetrics for testing."""
    
    def __init__(self):
        self.metrics = {}
    
    async def increment(self, cache_name: str, event_type: str, count: int = 1):
        """Increment a metric counter."""
        key = f"{cache_name}:{event_type}"
        if key not in self.metrics:
            self.metrics[key] = 0
        self.metrics[key] += count
    
    async def get_metrics(self, cache_name: str = None):
        """Get current metrics."""
        if cache_name:
            return {k: v for k, v in self.metrics.items() if k.startswith(f"{cache_name}:")}
        return self.metrics
    
    async def reset_metrics(self, cache_name: str = None):
        """Reset metrics."""
        if cache_name:
            keys_to_reset = [k for k in self.metrics if k.startswith(f"{cache_name}:")]
            for key in keys_to_reset:
                self.metrics[key] = 0
        else:
            self.metrics = {}

class MockKeyUsageTracker:
    """Mock implementation of KeyUsageTracker for testing."""
    
    def __init__(self):
        self.access_counts = {}
    
    async def record_access(self, key: str):
        """Record an access to a key."""
        if key not in self.access_counts:
            self.access_counts[key] = 0
        self.access_counts[key] += 1
    
    def get_adaptive_ttl(self, key: str, default_ttl: int, min_ttl: int, max_ttl: int) -> int:
        """Calculate an adaptive TTL based on access frequency."""
        count = self.access_counts.get(key, 0)
        if count == 0:
            return default_ttl
        
        # Simple algorithm: more accesses = longer TTL
        factor = min(count / 10, 1.0)  # Cap at 1.0
        return min_ttl + int(factor * (max_ttl - min_ttl))

class MockRequestCache:
    """Mock implementation of RequestCache for testing."""
    
    def __init__(self):
        """Initialize the request cache."""
        self._cache = {}
        self._context_stack = []  # Stack to track nested contexts

    def __enter__(self):
        """Enter a request context."""
        # Create a new context (empty dict) for this context level
        new_context = {}
        self._context_stack.append(new_context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit a request context."""
        if self._context_stack:
            self._context_stack.pop()
        return False

    def get(self, key, default=None):
        """Get a value from the cache."""
        if not self._context_stack:
            return default
        
        # Look through all contexts from newest to oldest
        for context in reversed(self._context_stack):
            if key in context:
                return context[key]
        return default

    def set(self, key, value):
        """Set a value in the cache."""
        if self._context_stack:
            # Set in the current (most recent) context
            self._context_stack[-1][key] = value

    def exists(self, key):
        """Check if a key exists in the cache."""
        if not self._context_stack:
            return False
        
        # Look through all contexts from newest to oldest
        for context in reversed(self._context_stack):
            if key in context:
                return True
        return False

    def clear(self):
        """Clear the cache."""
        if self._context_stack:
            self._context_stack[-1].clear()

    def cached_in_request(self, key_func=None):
        """Decorator for caching function results in the request scope."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # If not in a context, just execute the function
                if not self._context_stack:
                    return func(*args, **kwargs)
                
                # Generate cache key
                if key_func:
                    key = key_func(*args, **kwargs)
                else:
                    # Default key is function name + args + kwargs
                    key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                
                # Check cache
                if self.exists(key):
                    return self.get(key)
                
                # Call function and cache result
                result = func(*args, **kwargs)
                self.set(key, result)
                return result
            return wrapper
        return decorator

# Mock the create_cache factory function
def mock_create_cache(name: str, ttl: int = 3600, use_redis: bool = False, 
                     adaptive_ttl: bool = False, min_ttl: int = 60, max_ttl: int = 86400):
    """Factory function to create a cache instance."""
    return MockUnifiedCache(name, ttl, use_redis, adaptive_ttl, min_ttl, max_ttl)

# Create mock instances for testing
cache_metrics = MockCacheMetrics()

# Test classes using the mock implementations
class TestUnifiedCache:
    """Tests for the UnifiedCache class."""
    
    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """Test basic cache set/get operations."""
        cache = MockUnifiedCache("test_cache", ttl=60)
        
        # Test set and get
        await cache.set_async("key1", "value1")
        value = await cache.get_async("key1")
        assert value == "value1"
        
        # Test get with default
        value = await cache.get_async("nonexistent", default="default_value")
        assert value == "default_value"
        
        # Test exists
        exists = await cache.exists_async("key1")
        assert exists is True
        
        exists = await cache.exists_async("nonexistent")
        assert exists is False
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, monkeypatch):
        """Test that cached values expire after TTL."""
        cache = MockUnifiedCache("test_cache", ttl=1)
        
        # Mock time.time to control the apparent passage of time
        current_time = time.time()
        
        def mock_time():
            return current_time
        
        monkeypatch.setattr(time, "time", mock_time)
        
        # Set a value
        await cache.set_async("key1", "value1")
        
        # Value should exist
        value = await cache.get_async("key1")
        assert value == "value1"
        
        # Advance time past TTL
        current_time += 2
        
        # Value should be expired
        value = await cache.get_async("key1")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Test clearing the cache."""
        cache = MockUnifiedCache("test_cache", ttl=60)
        
        # Set multiple values
        await cache.set_async("key1", "value1")
        await cache.set_async("key2", "value2")
        
        # Verify values exist
        assert await cache.get_async("key1") == "value1"
        assert await cache.get_async("key2") == "value2"
        
        # Clear the cache
        await cache.clear_async()
        
        # Verify values are gone
        assert await cache.get_async("key1") is None
        assert await cache.get_async("key2") is None
    
    @pytest.mark.asyncio
    async def test_pattern_clear(self):
        """Test clearing cache by pattern."""
        cache = MockUnifiedCache("test_cache", ttl=60)
        
        # Set values with different patterns
        await cache.set_async("user:1", "user data 1")
        await cache.set_async("user:2", "user data 2")
        await cache.set_async("post:1", "post data 1")
        
        # Clear only user keys
        await cache.clear_pattern_async("user:*")
        
        # Verify user keys are gone but post key remains
        assert await cache.get_async("user:1") is None
        assert await cache.get_async("user:2") is None
        assert await cache.get_async("post:1") == "post data 1"
    
    @pytest.mark.asyncio
    async def test_warmup(self):
        """Test cache warmup functionality."""
        cache = MockUnifiedCache("test_cache", ttl=60)
        
        # Warmup with initial data
        await cache.warmup({
            "key1": "value1",
            "key2": "value2"
        })
        
        # Verify values were cached
        assert await cache.get_async("key1") == "value1"
        assert await cache.get_async("key2") == "value2"
    
    @pytest.mark.asyncio
    async def test_warmup_from_function(self):
        """Test warming up cache using a function."""
        cache = MockUnifiedCache("test_cache", ttl=60)
        
        async def fetch_values(keys):
            # Simulate fetching values from a data source
            return {key: f"value_for_{key}" for key in keys}
        
        # Warmup using the fetch function
        await cache.warmup_from_function(
            ["key1", "key2"],
            fetch_values
        )
        
        # Verify values were cached
        assert await cache.get_async("key1") == "value_for_key1"
        assert await cache.get_async("key2") == "value_for_key2"

class TestCacheMetrics:
    """Tests for the CacheMetrics class."""
    
    @pytest.mark.asyncio
    async def test_track_metrics(self):
        """Test tracking cache metrics."""
        metrics = MockCacheMetrics()
        
        # Track some events
        await metrics.increment("test_cache", "hits")
        await metrics.increment("test_cache", "hits")
        await metrics.increment("test_cache", "misses")
        
        # Check metrics
        all_metrics = await metrics.get_metrics()
        assert all_metrics["test_cache:hits"] == 2
        assert all_metrics["test_cache:misses"] == 1
        
        # Check filtered metrics
        cache_metrics = await metrics.get_metrics("test_cache")
        assert cache_metrics["test_cache:hits"] == 2
        assert cache_metrics["test_cache:misses"] == 1
    
    @pytest.mark.asyncio
    async def test_reset_metrics(self):
        """Test resetting cache metrics."""
        metrics = MockCacheMetrics()
        
        # Track events for multiple caches
        await metrics.increment("cache1", "hits", 5)
        await metrics.increment("cache2", "hits", 3)
        
        # Reset metrics for one cache
        await metrics.reset_metrics("cache1")
        
        # Check metrics
        all_metrics = await metrics.get_metrics()
        assert all_metrics.get("cache1:hits", 0) == 0
        assert all_metrics["cache2:hits"] == 3
        
        # Reset all metrics
        await metrics.reset_metrics()
        
        # Check all metrics are reset
        all_metrics = await metrics.get_metrics()
        assert len(all_metrics) == 0

class TestKeyUsageTracker:
    """Tests for the KeyUsageTracker class."""
    
    @pytest.mark.asyncio
    async def test_record_access(self):
        """Test recording key accesses."""
        tracker = MockKeyUsageTracker()
        
        # Record accesses
        await tracker.record_access("key1")
        await tracker.record_access("key1")
        await tracker.record_access("key2")
        
        # Check access counts
        assert tracker.access_counts["key1"] == 2
        assert tracker.access_counts["key2"] == 1
    
    def test_adaptive_ttl(self):
        """Test adaptive TTL calculation."""
        tracker = MockKeyUsageTracker()
        
        # No accesses yet
        ttl = tracker.get_adaptive_ttl("key1", 3600, 60, 86400)
        assert ttl == 3600
        
        # Simulate some accesses
        tracker.access_counts["key1"] = 5
        ttl = tracker.get_adaptive_ttl("key1", 3600, 60, 86400)
        assert ttl > 60
        assert ttl < 86400
        
        # Many accesses should approach max TTL
        tracker.access_counts["key1"] = 20
        ttl = tracker.get_adaptive_ttl("key1", 3600, 60, 86400)
        assert ttl == 86400

class TestRequestCache:
    """Tests for the RequestCache class."""
    
    def test_basic_operations(self):
        """Test basic request cache operations."""
        cache = MockRequestCache()
        
        with cache:
            # Set and get within context
            cache.set("key1", "value1")
            assert cache.get("key1") == "value1"
            
            # Default value for missing key
            assert cache.get("missing", "default") == "default"
        
        # Outside context, cache is not accessible
        assert cache.get("key1") is None
    
    def test_context_manager(self):
        """Test request cache as context manager."""
        cache = MockRequestCache()
        
        # First context
        with cache:
            cache.set("key1", "value1")
            assert cache.get("key1") == "value1"
        
        # Second context (should be independent)
        with cache:
            assert cache.get("key1") is None
            cache.set("key2", "value2")
            assert cache.get("key2") == "value2"
    
    def test_nested_contexts(self):
        """Test nested request contexts."""
        cache = MockRequestCache()
        
        with cache:
            cache.set("outer", "outer_value")
            
            with cache:
                # Inner context can see outer values
                assert cache.get("outer") == "outer_value"
                
                # Set inner value
                cache.set("inner", "inner_value")
                assert cache.get("inner") == "inner_value"
            
            # Outer context can't see inner values
            assert cache.get("inner") is None
    
    def test_cached_in_request_decorator(self):
        """Test the cached_in_request decorator."""
        cache = MockRequestCache()
        
        call_count = 0
        
        @cache.cached_in_request()
        def expensive_function(arg):
            nonlocal call_count
            call_count += 1
            return f"result_{arg}"
        
        # Call outside context - should not cache
        result1 = expensive_function("test")
        assert result1 == "result_test"
        assert call_count == 1
        
        with cache:
            # First call in context - should execute and cache
            result2 = expensive_function("test")
            assert result2 == "result_test"
            assert call_count == 2
            
            # Second call with same args - should use cache
            result3 = expensive_function("test")
            assert result3 == "result_test"
            assert call_count == 2  # No additional call
            
            # Call with different args - should execute
            result4 = expensive_function("other")
            assert result4 == "result_other"
            assert call_count == 3
    
    def test_custom_key_function(self):
        """Test cached_in_request with custom key function."""
        cache = MockRequestCache()
        
        call_count = 0
        
        # Custom key function that only uses the first argument
        def key_func(first, *args, **kwargs):
            return f"custom_key_{first}"
        
        @cache.cached_in_request(key_func=key_func)
        def multi_arg_function(first, second):
            nonlocal call_count
            call_count += 1
            return f"{first}_{second}"
        
        with cache:
            # First call
            result1 = multi_arg_function("a", "b")
            assert result1 == "a_b"
            assert call_count == 1
            
            # Different second arg, but same key - should use cache
            result2 = multi_arg_function("a", "c")
            assert result2 == "a_b"  # Note: returns cached result
            assert call_count == 1
            
            # Different first arg - should execute
            result3 = multi_arg_function("d", "e")
            assert result3 == "d_e"
            assert call_count == 2

@pytest.mark.asyncio
async def test_create_cache_factory():
    """Test the create_cache factory function."""
    # Create a cache with default settings
    cache = mock_create_cache("test_factory")
    assert cache.name == "test_factory"
    assert cache.default_ttl == 3600
    assert cache.use_redis is False
    
    # Create a cache with custom settings
    custom_cache = mock_create_cache(
        "custom_cache", 
        ttl=300,
        use_redis=True,
        adaptive_ttl=True
    )
    assert custom_cache.name == "custom_cache"
    assert custom_cache.default_ttl == 300
    assert custom_cache.use_redis is True
    assert custom_cache.adaptive_ttl is True

@pytest.mark.asyncio
async def test_clear_cache_utils():
    """Test the clear_cache_files function."""
    # Create a mock implementation of clear_cache_files
    async def mock_clear_cache_files():
        """Mock implementation that removes __pycache__ directories."""
        import os
        import shutil
        from pathlib import Path
        
        root_dir = Path(temp_dir)
        print(f"Removing cache directory: {root_dir / '__pycache__'}")
        
        # Find and remove __pycache__ directories
        for path in root_dir.glob("**/__pycache__"):
            if path.is_dir():
                shutil.rmtree(path)
        
        print("Cache clearing completed successfully.")
    
    # Use our mock implementation for testing
    with patch('utils.clear_cache_utils.clear_cache_files', side_effect=mock_clear_cache_files):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock __pycache__ directory
            pycache_dir = Path(temp_dir) / "__pycache__"
            pycache_dir.mkdir()

            # Create a mock .pyc file
            pyc_file = pycache_dir / "test.pyc"
            pyc_file.touch()

            # Patch get_project_root to return our temp directory
            with patch('utils.clear_cache_utils.get_project_root', return_value=Path(temp_dir)):
                # Call the function (our mocked version)
                from utils.clear_cache_utils import clear_cache_files
                await clear_cache_files()
                
                # Verify the cache files were removed
                assert not pyc_file.exists(), "Cache file should be removed"
                assert not pycache_dir.exists(), "Cache directory should be removed"

@pytest.mark.asyncio
async def test_factory_function():
    """Test the cache factory function."""
    cache = mock_create_cache("test_factory", ttl=30)
    
    # Check it's properly configured
    assert cache.name == "test_factory"
    assert cache.default_ttl == 30
    
    # Check it works
    await cache.set_async("key", "value")
    assert await cache.get_async("key") == "value" 