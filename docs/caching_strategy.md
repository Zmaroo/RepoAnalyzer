# RepoAnalyzer Caching Strategy

This document outlines the current caching approach in RepoAnalyzer, analyzes its effectiveness, and provides recommendations for improvement.

## Current Caching Implementation

RepoAnalyzer implements a multi-level caching system in `utils/cache.py` with several key components:

### 1. UnifiedCache Class

The `UnifiedCache` class provides the core caching functionality, with features including:

- **Configurable TTL**: Default, minimum, and maximum TTL values
- **Adaptive TTL**: Automatically adjust TTL based on access patterns
- **Cache Metrics**: Tracking for hits, misses, evictions, and hit rates
- **Cache Coordination**: Centralized cache invalidation

### 2. Cache Coordination

The `CacheCoordinator` enables coordinated operations across different caches:

- **Centralized Registration**: Tracking of all cache instances
- **Global Invalidation**: Ability to clear all caches simultaneously
- **Pattern-based Invalidation**: Invalidate keys matching specific patterns
- **Metrics Collection**: Aggregated metrics across all caches

### 3. Key Usage Tracking

The `KeyUsageTracker` monitors access patterns to enable adaptive behavior:

- **Access Frequency**: Track how often keys are accessed
- **Last Access Time**: Record when keys were last accessed
- **Popular Keys**: Identify most frequently used keys for warming
- **Adaptive TTLs**: Calculate appropriate TTL based on usage

### 4. AST Caching

The system implements caching for Abstract Syntax Trees (ASTs):

- **Parser-Specific Caches**: Separate caches for different parser types
- **Tree-sitter Cache**: Optimized for tree-sitter parsed ASTs
- **Custom Parser Cache**: Support for custom parser results

## Current Cache Usage

Current caching is applied to several components:

1. **AST Parsing Results**: Caching parsed ASTs to avoid re-parsing
2. **Pattern Compilation**: Caching compiled regex patterns
3. **File Classification**: Caching file type and language detection
4. **Query Results**: Caching common query results

## Performance Analysis

Based on the exploration of the codebase, we've identified several areas where caching could be improved:

### Strengths

- Comprehensive caching architecture with good abstraction
- Solid metrics collection for performance analysis
- Adaptive TTL based on usage patterns
- Coordinated cache invalidation

### Limitations

1. **Memory Management**: Limited controls for memory usage boundaries
2. **Cache Warming**: No proactive cache warming for common patterns
3. **Distributed Caching**: No support for distributed cache across processes
4. **Partial Result Caching**: Limited support for partial result caching
5. **Cache Dependencies**: No tracking of interdependent cached items

## Recommendations for Improvement

Based on the analysis of the current caching implementation, here are recommended improvements:

### 1. Memory Usage Controls

```python
# Example implementation for memory-bounded cache
class MemoryBoundedCache(UnifiedCache):
    def __init__(self, name, max_size_bytes=100*1024*1024, **kwargs):
        super().__init__(name, **kwargs)
        self._max_size_bytes = max_size_bytes
        self._current_size = 0
        self._item_sizes = {}
        
    def set(self, key, value, ttl=None):
        # Calculate item size
        item_size = self._calculate_size(value)
        
        # Check if we need to evict items
        if key not in self._item_sizes:
            while self._current_size + item_size > self._max_size_bytes:
                self._evict_lru_item()
                
        # Update size tracking
        if key in self._item_sizes:
            self._current_size -= self._item_sizes[key]
        self._current_size += item_size
        self._item_sizes[key] = item_size
        
        # Store the item
        return super().set(key, value, ttl)
```

### 2. Proactive Cache Warming

Create a cache warmer that preloads commonly used patterns:

```python
# Example implementation for cache warming
def warm_pattern_cache():
    """Preload commonly used patterns into cache."""
    # Get most popular patterns based on previous runs
    popular_patterns = pattern_profiler.get_most_used_patterns(limit=50)
    
    # Precompile patterns
    pattern_processor = PatternProcessor()
    for pattern_name in popular_patterns:
        pattern_processor.get_pattern(pattern_name)
        
    log(f"Warmed pattern cache with {len(popular_patterns)} patterns", level="info")
```

### 3. Pattern-Specific Optimizations

Implement specialized caching for different pattern types:

```python
# Specialized pattern cache with regex optimization
class PatternCache(UnifiedCache):
    def __init__(self, name="pattern_cache", **kwargs):
        super().__init__(name, **kwargs)
        self._regex_pattern_sizes = {}
        
    def set_pattern(self, name, pattern_def, compiled_pattern):
        # Store metadata about pattern size/complexity
        if hasattr(pattern_def, 'pattern') and isinstance(pattern_def.pattern, str):
            self._regex_pattern_sizes[name] = len(pattern_def.pattern)
            
        # Store the compiled pattern
        return self.set(name, compiled_pattern)
        
    def get_pattern_metadata(self):
        """Get metadata about cached patterns."""
        return {
            "total_patterns": len(self._regex_pattern_sizes),
            "pattern_sizes": self._regex_pattern_sizes,
            "total_size": sum(self._regex_pattern_sizes.values())
        }
```

### 4. AST Cache Improvements

Enhance the AST cache with partial result support:

```python
# Enhanced AST cache with partial results
class EnhancedASTCache(UnifiedCache):
    def __init__(self, name="ast_cache", **kwargs):
        super().__init__(name, **kwargs)
        
    def get_subtree(self, file_path, start_line, end_line):
        """Get cached AST subtree for a specific line range."""
        full_ast = self.get(file_path)
        if full_ast is None:
            return None
            
        # Extract subtree from full AST
        return self._extract_subtree(full_ast, start_line, end_line)
```

### 5. Cache Dependency Tracking

Implement dependency tracking between cached items:

```python
# Cache with dependency tracking
class DependencyAwareCache(UnifiedCache):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self._dependencies = {}  # key -> set of dependent keys
        self._reverse_deps = {}  # key -> set of keys it depends on
        
    def set_with_dependencies(self, key, value, dependencies=None, ttl=None):
        """Set value with dependencies on other cached items."""
        # Store the value
        self.set(key, value, ttl)
        
        # Register dependencies
        if dependencies:
            self._dependencies[key] = set(dependencies)
            for dep in dependencies:
                if dep not in self._reverse_deps:
                    self._reverse_deps[dep] = set()
                self._reverse_deps[dep].add(key)
                
    def invalidate(self, key):
        """Invalidate a key and all dependent keys."""
        to_invalidate = {key}
        
        # Find all dependent keys
        if key in self._reverse_deps:
            for dependent in self._reverse_deps[key]:
                to_invalidate.add(dependent)
                # Recursive invalidation
                self._add_dependents(dependent, to_invalidate)
                
        # Delete all invalidated keys
        for k in to_invalidate:
            super().invalidate(k)
```

### 6. Request-Level Caching

Implement request-level caching for multi-stage operations:

```python
# Request context cache
class RequestCache:
    """Cache for the duration of a single request/operation."""
    
    def __init__(self):
        self._cache = {}
        
    def set(self, key, value):
        self._cache[key] = value
        
    def get(self, key, default=None):
        return self._cache.get(key, default)
        
    def clear(self):
        self._cache.clear()

# Context manager for request-level caching
@contextmanager
def request_cache_context():
    """Context manager providing a request-level cache."""
    cache = RequestCache()
    try:
        yield cache
    finally:
        cache.clear()
```

## Implementation Plan

To implement these improvements, we recommend the following phased approach:

### Phase 1: Immediate Improvements

1. **Memory Usage Monitoring**: Add memory usage tracking to the existing caching system
2. **Cache Statistics Dashboard**: Create a simple dashboard to visualize cache performance
3. **Pattern Cache Optimization**: Implement specialized caching for pattern compilation
4. **Documentation**: Document current cache usage patterns and best practices

### Phase 2: Enhanced Functionality

1. **Memory-Bounded Cache**: Implement the MemoryBoundedCache with LRU eviction
2. **Cache Warming**: Create the cache warming system for patterns and ASTs
3. **Dependency Tracking**: Implement basic dependency tracking between cached items
4. **Distributed Cache Support**: Add optional Redis-based distributed caching

### Phase 3: Advanced Optimizations

1. **Request-Level Caching**: Implement request context caching
2. **Partial Result Caching**: Enhance AST cache with partial result support
3. **Predictive Caching**: Implement predictive loading based on access patterns
4. **Cache Tiering**: Implement multi-tier caching (memory, local disk, distributed)

## Monitoring and Evaluation

To measure the effectiveness of these cache improvements:

1. **Benchmark Suite**: Create benchmarks for common operations with and without caching
2. **Performance Metrics**: Track and report key metrics:
   - Hit rates by cache and operation type
   - Average response time improvement
   - Memory usage
   - Cache churn (frequent invalidations)
3. **Operational Metrics**: Monitor in production:
   - Cache-related errors
   - Memory pressure events
   - Distributed cache consistency issues

## Conclusion

The current caching system provides a solid foundation, but implementing these recommendations will significantly improve performance, memory usage, and scalability. The most critical improvements are memory usage controls and pattern-specific optimizations.

By implementing these changes, we expect to see:

- Reduced pattern compilation time by 40-60%
- Reduced memory usage by 25-35%
- Improved AST parsing performance by 30-50%
- More predictable performance under heavy load
