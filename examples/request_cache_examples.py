#!/usr/bin/env python3
"""
Examples demonstrating how to use the request-level caching system in various scenarios.
"""

import sys
import os
import time
from typing import Dict, List, Any

# Add the parent directory to the Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.request_cache import request_cache_context, cached_in_request

########################
# Basic Usage Examples #
########################

def basic_example():
    """Demonstrate basic usage of request cache context manager."""
    print("\n=== Basic Request Cache Example ===")
    
    with request_cache_context() as cache:
        # Set some values in the cache
        cache.set("user_id", "12345")
        cache.set("user_preferences", {"theme": "dark", "language": "en"})
        
        # Retrieve values from the cache
        user_id = cache.get("user_id")
        preferences = cache.get("user_preferences")
        
        print(f"User ID: {user_id}")
        print(f"Preferences: {preferences}")
        
        # Check if a key exists
        if cache.has("user_id"):
            print("User ID exists in cache")
        
        # Cache size
        print(f"Cache size: {cache.size()} items")
        
        # Delete an item
        cache.delete("user_id")
        print(f"After deletion, cache size: {cache.size()} items")
    
    # The cache is automatically cleared when exiting the context
    print("Context exited, cache has been cleared")


#############################
# Decorator Usage Examples #
#############################

def slow_operation(user_id: str) -> Dict[str, Any]:
    """Simulate a slow database operation."""
    print(f"Performing slow database query for user {user_id}...")
    time.sleep(1)  # Simulate a slow operation
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com"
    }

@cached_in_request
def get_user_data(user_id: str) -> Dict[str, Any]:
    """Get user data with caching."""
    return slow_operation(user_id)

def decorator_example():
    """Demonstrate using the cached_in_request decorator."""
    print("\n=== Decorator Example ===")
    
    with request_cache_context():
        # First call will execute the slow operation
        start_time = time.time()
        user_data = get_user_data("12345")
        first_call_time = time.time() - start_time
        print(f"First call result: {user_data}")
        print(f"First call took: {first_call_time:.4f} seconds")
        
        # Second call with the same arguments will use the cached value
        start_time = time.time()
        user_data = get_user_data("12345")
        second_call_time = time.time() - start_time
        print(f"Second call result: {user_data}")
        print(f"Second call took: {second_call_time:.4f} seconds")
        
        # Different arguments will execute the slow operation again
        start_time = time.time()
        user_data = get_user_data("67890")
        third_call_time = time.time() - start_time
        print(f"Third call result (different user ID): {user_data}")
        print(f"Third call took: {third_call_time:.4f} seconds")


###############################
# Custom Key Function Example #
###############################

# Complex function arguments example
def process_items(items: List[Dict[str, Any]], options: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Simulate processing a list of items with options."""
    print(f"Processing {len(items)} items with options: {options}")
    time.sleep(1)  # Simulate a slow operation
    
    processed = []
    for item in items:
        processed.append({
            **item,
            "processed": True,
            "timestamp": time.time()
        })
    return processed

# Function to generate a stable hash of a list or dictionary
def stable_hash(obj):
    """Create a stable hash for complex objects like lists and dictionaries."""
    if isinstance(obj, dict):
        return hash(frozenset((k, stable_hash(v)) for k, v in sorted(obj.items())))
    elif isinstance(obj, (list, tuple)):
        return hash(tuple(stable_hash(x) for x in obj))
    else:
        return hash(obj)

# Custom key function that creates a stable cache key based on the content of
# the items list and selected options
def items_cache_key(items, options):
    """Generate a cache key based on item IDs and important options."""
    item_ids = [item["id"] for item in items]
    relevant_options = {k: v for k, v in options.items() if k in ["format", "filter"]}
    return f"process:{stable_hash(item_ids)}:{stable_hash(relevant_options)}"

@cached_in_request(key_fn=items_cache_key)
def cached_process_items(items: List[Dict[str, Any]], options: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process items with request-level caching using a custom key function."""
    return process_items(items, options)

def custom_key_example():
    """Demonstrate using a custom key function with the cache decorator."""
    print("\n=== Custom Key Function Example ===")
    
    items1 = [{"id": "item1", "value": 10}, {"id": "item2", "value": 20}]
    items2 = [{"id": "item1", "value": 11}, {"id": "item2", "value": 21}]  # Different values
    options1 = {"format": "json", "filter": "active", "debug": True}
    options2 = {"format": "json", "filter": "active", "debug": False}  # Different debug
    
    with request_cache_context():
        # First call with items1 and options1
        start_time = time.time()
        result1 = cached_process_items(items1, options1)
        print(f"First call took: {time.time() - start_time:.4f} seconds")
        
        # Second call with items that have same IDs but different values
        # Since our key function only uses IDs, this should be a cache hit
        start_time = time.time()
        result2 = cached_process_items(items2, options1)
        print(f"Second call (same item IDs) took: {time.time() - start_time:.4f} seconds")
        
        # Third call with options that differ only in debug flag
        # Since our key function ignores debug, this should be a cache hit
        start_time = time.time()
        result3 = cached_process_items(items2, options2)
        print(f"Third call (different debug option) took: {time.time() - start_time:.4f} seconds")
        
        # Fourth call with completely different items
        items3 = [{"id": "item3", "value": 30}, {"id": "item4", "value": 40}]
        start_time = time.time()
        result4 = cached_process_items(items3, options1)
        print(f"Fourth call (different items) took: {time.time() - start_time:.4f} seconds")
        
        # Note that result1 and result2 are the same object because of caching
        print(f"result1 is result2: {result1 is result2}")
        print(f"result2 is result3: {result2 is result3}")
        print(f"result3 is result4: {result3 is result4}")


########################
# Real-world Examples #
########################

def simulate_fetch_repository_data(repo_id: str) -> Dict[str, Any]:
    """Simulate fetching repository data from a database."""
    print(f"Fetching repository data for {repo_id}...")
    time.sleep(1.5)  # Simulate a slow database query
    return {
        "id": repo_id,
        "name": f"Repository {repo_id}",
        "files": 150,
        "branches": ["main", "develop"]
    }

def simulate_fetch_file_content(repo_id: str, file_path: str) -> str:
    """Simulate fetching file content from storage."""
    print(f"Fetching file content for {repo_id}/{file_path}...")
    time.sleep(0.8)  # Simulate slow file I/O
    return f"Content of {file_path} in repository {repo_id}"

def simulate_parse_file(content: str):
    """Simulate parsing file content."""
    print(f"Parsing file content: {content[:20]}...")
    time.sleep(0.5)  # Simulate parsing operation
    return {"parsed": True, "content": content}

@cached_in_request
def get_repository_data(repo_id: str) -> Dict[str, Any]:
    """Get repository data with caching."""
    return simulate_fetch_repository_data(repo_id)

@cached_in_request(lambda repo_id, file_path: f"file:{repo_id}:{file_path}")
def get_file_content(repo_id: str, file_path: str) -> str:
    """Get file content with caching."""
    return simulate_fetch_file_content(repo_id, file_path)

@cached_in_request
def parse_file_content(content: str):
    """Parse file content with caching."""
    return simulate_parse_file(content)

def analyze_repository_file(repo_id: str, file_path: str) -> Dict[str, Any]:
    """Analyze a file in a repository using cached operations."""
    # Get repository data
    repo_data = get_repository_data(repo_id)
    
    # Get file content
    content = get_file_content(repo_id, file_path)
    
    # Parse file content
    parsed = parse_file_content(content)
    
    # Return combined result
    return {
        "repository": repo_data,
        "file_path": file_path,
        "parsed_content": parsed
    }

def real_world_example():
    """Demonstrate a real-world scenario with multiple cached operations."""
    print("\n=== Real-world Example: Repository Analysis ===")
    
    with request_cache_context():
        # First file analysis
        print("\n[Analyzing first file]")
        start_time = time.time()
        result1 = analyze_repository_file("repo123", "file1.py")
        print(f"First analysis took: {time.time() - start_time:.4f} seconds")
        
        # Second file in same repository - should reuse repository data
        print("\n[Analyzing second file in same repository]")
        start_time = time.time()
        result2 = analyze_repository_file("repo123", "file2.py")
        print(f"Second analysis took: {time.time() - start_time:.4f} seconds")
        
        # Analyze first file again - should reuse all cached data
        print("\n[Analyzing first file again]")
        start_time = time.time()
        result3 = analyze_repository_file("repo123", "file1.py")
        print(f"Repeat analysis took: {time.time() - start_time:.4f} seconds")


if __name__ == "__main__":
    basic_example()
    decorator_example()
    custom_key_example()
    real_world_example() 