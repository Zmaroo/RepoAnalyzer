# Request-Level Caching

## Overview

Request-level caching in RepoAnalyzer provides a way to cache data for the duration of a single request or operation. Unlike persistent caches that store data across multiple requests, this cache only exists during the lifecycle of a request, making it ideal for avoiding redundant work within a complex operation without consuming long-term memory resources.

## Key Benefits

- **Reduced Redundancy**: Eliminate duplicate computations within a single request
- **Improved Performance**: Speed up complex operations that access the same data multiple times
- **Resource Efficiency**: Cache data only for the duration it's needed, then automatically clean up
- **Thread Safety**: Each request has its own isolated cache, ensuring thread safety
- **Simple API**: Easy-to-use context manager and decorator patterns

## Implementation

The request-level caching system is implemented in `utils/request_cache.py` and consists of:

1. **RequestCache Class**: Core class that stores and manages cached data for a request
2. **Thread-Local Storage**: Ensures each thread has its own isolated cache
3. **Context Manager**: Provides a clean way to create and manage cache lifetimes
4. **Function Decorator**: Simplifies caching of function results

## Usage Examples

### Basic Context Manager

```python
from utils.request_cache import request_cache_context

with request_cache_context() as cache:
    # Store values in the cache
    cache.set("user_id", "12345")
    cache.set("user_preferences", {"theme": "dark"})
    
    # Retrieve values
    user_id = cache.get("user_id")  # "12345"
    
    # Check if a key exists
    if cache.has("user_id"):
        print("User ID exists in cache")
        
    # Get cache size
    size = cache.size()  # 2
    
    # Delete an item
    cache.delete("user_id")

# Cache is automatically cleared when exiting the context
```

### Function Decorator

```python
from utils.request_cache import request_cache_context, cached_in_request

# Cache function results during a request
@cached_in_request
def get_user_data(user_id):
    # Expensive operation that retrieves user data
    return fetch_user_from_database(user_id)

# Use the function inside a request context
with request_cache_context():
    # First call executes the function
    user = get_user_data("12345")
    
    # Second call with same arguments returns cached result
    same_user = get_user_data("12345")  # Fast, uses cached value
    
    # Different arguments execute the function again
    another_user = get_user_data("67890")
```

### Custom Cache Keys

For more control over caching behavior, you can provide a custom key function:

```python
from utils.request_cache import cached_in_request

# Custom key function that only considers the repository ID
@cached_in_request(lambda repo_id, file_path: f"repo:{repo_id}")
def get_repository_data(repo_id, file_path):
    # This will cache based only on repo_id, ignoring file_path
    return fetch_repository(repo_id)
```

## Integration with RepoAnalyzer

Request-level caching is particularly useful in the following areas of RepoAnalyzer:

### Pattern Processing

When processing files against multiple patterns, the same file might be accessed multiple times. Using request-level caching can significantly speed up these operations:

```python
@cached_in_request
def get_file_content(repo_id, file_path):
    return load_file_content(repo_id, file_path)

@cached_in_request
def parse_file(content, language):
    return parse_content_as_ast(content, language)
```

### Repository Analysis

During repository analysis, many components may need access to the same repository metadata:

```python
@cached_in_request
def get_repository_metadata(repo_id):
    return fetch_repository_metadata(repo_id)
```

### Multi-stage Operations

For operations that process data through multiple stages, caching intermediate results can be valuable:

```python
def analyze_repository(repo_id):
    with request_cache_context():
        metadata = get_repository_metadata(repo_id)
        files = list_repository_files(repo_id)
        
        results = []
        for file in files:
            content = get_file_content(repo_id, file)
            ast = parse_file_content(content, get_language(file))
            patterns = find_relevant_patterns(ast)
            results.append(analyze_with_patterns(ast, patterns))
        
        return aggregate_results(results)
```

## Performance Considerations

- Request-level caching is best for data that's used multiple times within a single operation
- It's not meant for long-lived data that should persist between requests
- For frequently accessed data across multiple requests, use the persistent cache (`utils/cache.py`)
- Consider using custom key functions for complex arguments to avoid unnecessary cache misses

## Testing the Cache

The caching system includes extensive unit tests in `tests/test_request_cache.py`. These tests verify:

- Basic cache operations (set, get, delete)
- Context manager functionality
- Decorator behavior
- Thread isolation
- Nested cache contexts

## Extended Examples

For detailed examples showing how to use request-level caching in various scenarios, see the example file at `examples/request_cache_examples.py`.

## Best Practices

1. **Use in Complex Operations**: Apply request caching to complex operations that involve multiple steps and repeated data access
2. **Thread Safety**: Remember that each thread has its own isolated cache
3. **Clear When Done**: The context manager automatically clears the cache, but if manually managing, remember to clear it
4. **Custom Key Functions**: Use custom key functions when standard argument-based keys aren't sufficient
5. **Cache the Right Level**: Cache at the appropriate granularity - usually at the data access level, not business logic
6. **Combine with Persistent Cache**: Use request cache for operation-scoped data and persistent cache for longer-term needs
