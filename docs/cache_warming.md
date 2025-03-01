# Cache Warming System

This document describes the RepoAnalyzer cache warming system, which proactively loads frequently used data into the cache to improve performance.

## Overview

The cache warming system extends the RepoAnalyzer caching architecture with specialized warming capabilities that focus on:

1. **Proactive cache population** - Loading frequently used items before they're needed
2. **Pattern-specific optimizations** - Precompiling complex patterns to avoid runtime delays
3. **Background warming** - Automatically refreshing cache contents based on usage patterns

By warming the cache, the system reduces latency for common operations and improves overall performance, especially after cache invalidation or system restart.

## Architecture

The cache warming system consists of:

- **CacheWarmer** - Core warming utility that manages warming strategies
- **Warming Strategies** - Specialized functions for warming different cache types
- **CLI Interface** - Command-line tool for managing cache warming operations

The system integrates with the existing caching architecture and analytics systems to determine which items should be prioritized for warming.

## Available Warming Strategies

### Pattern Cache Strategies

- **common_patterns**: Warms the cache with the most frequently used patterns
- **language_specific**: Warms patterns specific to a particular programming language
- **complex_patterns**: Prioritizes patterns with high complexity for precompilation

### Repository Cache Strategies

- **recent**: Warms the cache with recently accessed repositories

### AST Cache Strategies

- **common_files**: Warms the AST cache with parsing results for commonly accessed files

## Using the CLI Tool

The `warm_cache.py` script provides a command-line interface for managing cache warming operations.

### List Available Strategies

```bash
./scripts/warm_cache.py list
```

This command displays all registered warming strategies with descriptions and parameters.

### Execute a Warming Strategy

```bash
./scripts/warm_cache.py warm --cache patterns --strategy common_patterns --limit 50
```

Parameters:

- `--cache`: Name of the cache to warm (e.g., "patterns", "repositories")
- `--strategy`: Name of the warming strategy to use
- `--limit`: Maximum number of items to warm (optional)
- `--language`: Programming language for language-specific warming (optional)
- `--complexity`: Minimum complexity threshold for complexity-based warming (optional)

### Start Proactive Background Warming

```bash
./scripts/warm_cache.py start --interval 3600
```

This starts a background process that automatically warms caches at specified intervals.

Parameters:

- `--interval`: Time between warming cycles in seconds (default: 3600)

### Stop Proactive Background Warming

```bash
./scripts/warm_cache.py stop
```

### Check Warming Status

```bash
./scripts/warm_cache.py status
```

This command displays the status of warming operations, including:

- Whether proactive warming is running
- Last run time for each strategy
- Success/failure status
- Any errors encountered

## Programmatic Usage

You can also use the cache warming system programmatically in your code:

```python
from utils.cache_warmer import cache_warmer

# Execute a specific warming strategy
await cache_warmer.warm_cache("patterns", "common_patterns", limit=50)

# Start proactive warming
await cache_warmer.start_proactive_warming(interval=3600)

# Stop proactive warming
await cache_warmer.stop_proactive_warming()

# Get warming status
status = cache_warmer.get_warming_status()
```

## Adding Custom Warming Strategies

You can register custom warming strategies for specific caches:

```python
from utils.cache_warmer import cache_warmer

async def my_custom_warming_strategy(**kwargs):
    # Warming logic here
    return True  # Return success/failure

# Register the strategy
cache_warmer.register_warmup_strategy(
    "my_cache", 
    "my_strategy", 
    my_custom_warming_strategy
)
```

## Best Practices

1. **Warm selectively** - Focus on warming only the most valuable items to avoid unnecessary memory usage
2. **Consider timing** - Run warming operations during periods of low system load
3. **Monitor impact** - Use the cache monitoring tool to assess whether warming strategies are improving hit rates
4. **Target bottlenecks** - Prioritize warming for caches with the lowest hit rates or highest latency

## Integration with Health Monitoring

The cache warming system integrates with the health monitoring system. You can check the status of the cache warming system using:

```bash
./scripts/monitor_health.py --component cache_warmer
```
