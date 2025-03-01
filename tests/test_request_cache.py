#!/usr/bin/env python3
"""
Unit tests for the request-level caching system
"""

import unittest
import sys
import os
import threading
import time
from unittest.mock import patch, MagicMock

# Add the parent directory to the Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.request_cache import (
    RequestCache,
    request_cache_context,
    get_current_request_cache,
    set_current_request_cache,
    cached_in_request
)

class TestRequestCache(unittest.TestCase):
    """Tests for the request-level cache system."""
    
    def test_cache_basics(self):
        """Test basic cache operations."""
        cache = RequestCache()
        
        # Test set and get
        cache.set("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")
        
        # Test default value for missing keys
        self.assertIsNone(cache.get("missing_key"))
        self.assertEqual(cache.get("missing_key", "default"), "default")
        
        # Test delete
        cache.delete("key1")
        self.assertIsNone(cache.get("key1"))
        
        # Test has
        cache.set("key2", "value2")
        self.assertTrue(cache.has("key2"))
        self.assertFalse(cache.has("missing_key"))
        
        # Test clear
        cache.clear()
        self.assertFalse(cache.has("key2"))
        
        # Test size
        cache.set("key3", "value3")
        cache.set("key4", "value4")
        self.assertEqual(cache.size(), 2)
    
    def test_context_manager(self):
        """Test the request_cache_context context manager."""
        # Verify no cache exists initially
        self.assertIsNone(get_current_request_cache())
        
        # Use the context manager
        with request_cache_context() as cache:
            # Check that the cache is accessible within the context
            self.assertIsNotNone(get_current_request_cache())
            self.assertEqual(get_current_request_cache(), cache)
            
            # Use the cache
            cache.set("test_key", "test_value")
            self.assertEqual(cache.get("test_key"), "test_value")
        
        # Verify the cache is cleared after the context exits
        self.assertIsNone(get_current_request_cache())
    
    def test_nested_contexts(self):
        """Test nested request cache contexts."""
        with request_cache_context() as outer_cache:
            outer_cache.set("outer_key", "outer_value")
            
            # Create a nested context
            with request_cache_context() as inner_cache:
                # Inner cache should be different from outer cache
                self.assertNotEqual(outer_cache, inner_cache)
                self.assertEqual(get_current_request_cache(), inner_cache)
                
                inner_cache.set("inner_key", "inner_value")
                self.assertEqual(inner_cache.get("inner_key"), "inner_value")
                self.assertIsNone(inner_cache.get("outer_key"))  # Should not have outer values
            
            # After inner context, outer should be active again
            self.assertEqual(get_current_request_cache(), outer_cache)
            self.assertEqual(outer_cache.get("outer_key"), "outer_value")
    
    def test_cached_in_request_decorator(self):
        """Test the cached_in_request decorator."""
        
        # Mock function to track calls
        mock_fn = MagicMock(return_value="test_result")
        
        # Decorated function
        @cached_in_request
        def test_function(arg1, arg2=None):
            mock_fn(arg1, arg2)
            return f"result:{arg1}:{arg2}"
        
        # Test outside a request context (should not cache)
        result1 = test_function("a", "b")
        result2 = test_function("a", "b")
        self.assertEqual(result1, "result:a:b")
        self.assertEqual(result2, "result:a:b")
        self.assertEqual(mock_fn.call_count, 2)  # Should be called twice
        
        # Reset mock
        mock_fn.reset_mock()
        
        # Test with a request context
        with request_cache_context():
            # First call should execute the function
            result1 = test_function("c", "d")
            self.assertEqual(result1, "result:c:d")
            self.assertEqual(mock_fn.call_count, 1)
            
            # Second call with same args should use cached result
            result2 = test_function("c", "d")
            self.assertEqual(result2, "result:c:d")
            self.assertEqual(mock_fn.call_count, 1)  # No additional calls
            
            # Different args should execute the function again
            result3 = test_function("e", "f")
            self.assertEqual(result3, "result:e:f")
            self.assertEqual(mock_fn.call_count, 2)
    
    def test_cached_in_request_with_custom_key(self):
        """Test the cached_in_request decorator with a custom key function."""
        
        mock_fn = MagicMock(return_value="test_result")
        
        # Decorated function with custom key function
        @cached_in_request(lambda x, y: f"custom:{x}")  # Only use x for the key
        def test_function(x, y):
            mock_fn(x, y)
            return f"result:{x}:{y}"
        
        with request_cache_context():
            # Call with different y values but same x should use the cache
            result1 = test_function("a", "b1")
            self.assertEqual(result1, "result:a:b1")
            self.assertEqual(mock_fn.call_count, 1)
            
            result2 = test_function("a", "b2")  # Different y but same x
            self.assertEqual(result2, "result:a:b1")  # Should get cached value from first call
            self.assertEqual(mock_fn.call_count, 1)  # No additional call
            
            # Different x should execute the function again
            result3 = test_function("c", "d")
            self.assertEqual(result3, "result:c:d")
            self.assertEqual(mock_fn.call_count, 2)
    
    def test_thread_isolation(self):
        """Test that request caches are isolated between threads."""
        
        results = {}
        
        def thread_func(thread_id):
            """Function to run in separate thread."""
            with request_cache_context() as cache:
                # Set a value in this thread's cache
                cache.set("thread_key", f"thread_{thread_id}_value")
                
                # Simulate some work
                time.sleep(0.1)
                
                # Get the value again
                value = cache.get("thread_key")
                results[thread_id] = value
        
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_func, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Each thread should have its own isolated value
        self.assertEqual(results[0], "thread_0_value")
        self.assertEqual(results[1], "thread_1_value")
        self.assertEqual(results[2], "thread_2_value")

if __name__ == "__main__":
    unittest.main() 