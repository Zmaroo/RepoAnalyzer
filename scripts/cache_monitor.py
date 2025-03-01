#!/usr/bin/env python3
"""
RepoAnalyzer Cache Monitoring Tool

This script provides a command-line interface to monitor and manage the
caching system, view cache statistics, and configure cache settings.
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.cache import cache_coordinator, UnifiedCache
from utils.memory_bounded_cache import MemoryBoundedCache, PatternCache, pattern_cache
from utils.logger import log

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="RepoAnalyzer Cache Monitoring Tool")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List caches command
    subparsers.add_parser("list", help="List all registered caches")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show cache statistics")
    stats_parser.add_argument(
        "--cache", 
        type=str,
        help="Specific cache to show statistics for"
    )
    stats_parser.add_argument(
        "--watch", 
        action="store_true",
        help="Watch cache statistics continuously"
    )
    stats_parser.add_argument(
        "--interval", 
        type=int, 
        default=5,
        help="Update interval for watch mode in seconds (default: 5)"
    )
    
    # Memory usage command
    memory_parser = subparsers.add_parser("memory", help="Show memory usage statistics")
    memory_parser.add_argument(
        "--cache", 
        type=str,
        help="Specific cache to show memory usage for"
    )
    memory_parser.add_argument(
        "--top", 
        type=int, 
        default=10,
        help="Number of largest items to show (default: 10)"
    )
    
    # Clear cache command
    clear_parser = subparsers.add_parser("clear", help="Clear cache contents")
    clear_parser.add_argument(
        "--cache", 
        type=str,
        help="Specific cache to clear (omit to clear all)"
    )
    clear_parser.add_argument(
        "--confirm", 
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    # Configure command
    config_parser = subparsers.add_parser("configure", help="Configure cache settings")
    config_parser.add_argument(
        "--cache", 
        type=str, 
        required=True,
        help="Name of cache to configure"
    )
    config_parser.add_argument(
        "--max-size", 
        type=str,
        help="Maximum cache size (e.g., '100MB', '1GB')"
    )
    config_parser.add_argument(
        "--ttl", 
        type=float,
        help="Default TTL in seconds"
    )
    
    # Export stats command
    export_parser = subparsers.add_parser("export", help="Export cache statistics to file")
    export_parser.add_argument(
        "--output", 
        type=str, 
        default="cache_stats.json",
        help="Output file path (default: cache_stats.json)"
    )
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze cache effectiveness")
    analyze_parser.add_argument(
        "--cache", 
        type=str,
        help="Specific cache to analyze"
    )
    analyze_parser.add_argument(
        "--output", 
        type=str,
        help="Output file for analysis report"
    )
    
    return parser.parse_args()

def parse_size_string(size_str: str) -> int:
    """Parse a human-readable size string (e.g., '100MB') to bytes.
    
    Args:
        size_str: Size string (e.g., '100MB', '1GB')
        
    Returns:
        Size in bytes
    """
    units = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 * 1024,
        'GB': 1024 * 1024 * 1024,
    }
    
    size_str = size_str.strip().upper()
    
    # Extract number and unit
    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            try:
                size = float(size_str[:-len(unit)])
                return int(size * multiplier)
            except ValueError:
                raise ValueError(f"Invalid size format: {size_str}")
    
    # If no unit specified, assume bytes
    try:
        return int(size_str)
    except ValueError:
        raise ValueError(f"Invalid size format: {size_str}")

def format_bytes(size_bytes: int) -> str:
    """Format bytes as human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable size string
    """
    if size_bytes < 0:
        return "0 B"
        
    units = ['B', 'KB', 'MB', 'GB']
    size = float(size_bytes)
    
    for unit in units:
        if size < 1024 or unit == 'GB':
            return f"{size:.2f} {unit}"
        size /= 1024

def list_caches(args):
    """List all registered caches.
    
    Args:
        args: Command-line arguments
    """
    caches = cache_coordinator.get_all_caches()
    
    print("\nRegistered Caches:")
    print("=" * 80)
    
    if not caches:
        print("No caches registered.")
        return
    
    for name in sorted(caches.keys()):
        cache = caches[name]
        cache_type = type(cache).__name__
        
        # Get additional details based on cache type
        details = []
        
        if isinstance(cache, MemoryBoundedCache):
            memory_info = cache.get_memory_usage()
            details.append(f"Memory: {memory_info['current_size_human']} / {memory_info['max_size_human']}")
            details.append(f"Items: {memory_info['item_count']}")
        else:
            # Regular cache
            details.append(f"Items: {len(cache._cache)}")
            details.append(f"Default TTL: {cache._default_ttl}s")
        
        metrics = cache.get_metrics()
        hit_rate = metrics.hit_rate * 100
        details.append(f"Hit rate: {hit_rate:.1f}%")
        
        print(f"{name} ({cache_type}):")
        print(f"  {', '.join(details)}")
    
    print("\nUse 'stats --cache <name>' for detailed cache statistics")

def show_cache_stats(cache_name: Optional[str] = None):
    """Show statistics for a specific cache or all caches.
    
    Args:
        cache_name: Name of cache to show stats for, or None for all
    """
    caches = cache_coordinator.get_all_caches()
    
    if cache_name and cache_name not in caches:
        print(f"Cache '{cache_name}' not found.")
        print(f"Available caches: {', '.join(sorted(caches.keys()))}")
        return
    
    if cache_name:
        # Show detailed stats for a specific cache
        cache = caches[cache_name]
        metrics = cache.get_metrics()
        
        print(f"\nCache Statistics for '{cache_name}':")
        print("=" * 80)
        print(f"Type: {type(cache).__name__}")
        print(f"Hits: {metrics.hits}")
        print(f"Misses: {metrics.misses}")
        print(f"Hit Rate: {metrics.hit_rate * 100:.1f}%")
        print(f"Evictions: {metrics.evictions}")
        print(f"Invalidations: {metrics.invalidations}")
        print(f"Total Operations: {metrics.hits + metrics.misses}")
        
        # Show memory usage for memory-bounded caches
        if isinstance(cache, MemoryBoundedCache):
            memory_info = cache.get_memory_usage()
            print(f"\nMemory Usage:")
            print(f"Current Size: {memory_info['current_size_human']}")
            print(f"Maximum Size: {memory_info['max_size_human']}")
            print(f"Memory Pressure: {memory_info['memory_pressure'] * 100:.1f}%")
            print(f"Average Item Size: {memory_info['avg_item_size']}")
            print(f"Item Count: {memory_info['item_count']}")
            
            # Show largest items
            largest_items = cache.get_largest_items(10)
            if largest_items:
                print("\nLargest Items:")
                for i, (key, size) in enumerate(largest_items, 1):
                    print(f"{i}. {key}: {format_bytes(size)}")
                    
        # Show pattern metadata for pattern caches
        if isinstance(cache, PatternCache):
            pattern_info = cache.get_pattern_metadata()
            print(f"\nPattern Information:")
            print(f"Total Patterns: {pattern_info['total_patterns']}")
            
            # Show most complex patterns
            complex_patterns = cache.get_patterns_by_complexity(5)
            if complex_patterns:
                print("\nMost Complex Patterns:")
                for i, (name, complexity) in enumerate(complex_patterns, 1):
                    print(f"{i}. {name}: Complexity {complexity}")
        
        # Show cache contents overview
        if hasattr(cache, '_cache'):
            print(f"\nCache Contents Overview:")
            print(f"Total Items: {len(cache._cache)}")
            
            # Show a sample of keys
            keys = list(cache._cache.keys())[:10]
            if keys:
                print("Sample Keys:")
                for key in keys:
                    value, expiry, _ = cache._cache[key]
                    expires = "never" if expiry is None else f"expires {datetime.fromtimestamp(expiry).isoformat()}"
                    value_type = type(value).__name__
                    print(f"- {key} ({value_type}, {expires})")
    else:
        # Show summary stats for all caches
        print("\nCache Statistics Summary:")
        print("=" * 80)
        
        for name in sorted(caches.keys()):
            cache = caches[name]
            metrics = cache.get_metrics()
            cache_type = type(cache).__name__
            
            hit_rate = metrics.hit_rate * 100
            total_ops = metrics.hits + metrics.misses
            
            # Get memory info if available
            memory_str = ""
            if isinstance(cache, MemoryBoundedCache):
                memory_info = cache.get_memory_usage()
                memory_str = f", Memory: {memory_info['current_size_human']} / {memory_info['max_size_human']}"
            
            print(f"{name} ({cache_type}):")
            print(f"  Hit Rate: {hit_rate:.1f}%, Hits: {metrics.hits}, Misses: {metrics.misses}")
            print(f"  Total Ops: {total_ops}, Evictions: {metrics.evictions}{memory_str}")

def watch_cache_stats(args):
    """Watch cache statistics in real-time.
    
    Args:
        args: Command-line arguments
    """
    try:
        while True:
            # Clear screen
            os.system('clear' if os.name == 'posix' else 'cls')
            
            # Show timestamp
            print(f"Cache Statistics - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("Press Ctrl+C to exit watch mode")
            
            # Show stats
            show_cache_stats(args.cache)
            
            # Wait for next update
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nExiting watch mode.")

def show_memory_usage(args):
    """Show memory usage statistics.
    
    Args:
        args: Command-line arguments
    """
    caches = cache_coordinator.get_all_caches()
    
    if args.cache and args.cache not in caches:
        print(f"Cache '{args.cache}' not found.")
        print(f"Available caches: {', '.join(sorted(caches.keys()))}")
        return
    
    print("\nMemory Usage Statistics:")
    print("=" * 80)
    
    memory_bounded_caches = {}
    regular_caches = {}
    
    # Separate memory-bounded caches from regular caches
    for name, cache in caches.items():
        if isinstance(cache, MemoryBoundedCache):
            memory_bounded_caches[name] = cache
        else:
            regular_caches[name] = cache
    
    # Show memory-bounded cache stats
    if memory_bounded_caches:
        print("\nMemory-Bounded Caches:")
        
        if args.cache and args.cache in memory_bounded_caches:
            # Show detailed stats for a specific cache
            cache = memory_bounded_caches[args.cache]
            memory_info = cache.get_memory_usage()
            
            print(f"Cache: {args.cache}")
            print(f"Current Size: {memory_info['current_size_human']} / {memory_info['max_size_human']}")
            print(f"Memory Pressure: {memory_info['memory_pressure'] * 100:.1f}%")
            print(f"Item Count: {memory_info['item_count']}")
            print(f"Average Item Size: {memory_info['avg_item_size']}")
            
            # Show largest items
            largest_items = cache.get_largest_items(args.top)
            if largest_items:
                print("\nLargest Items:")
                for i, (key, size) in enumerate(largest_items, 1):
                    print(f"{i}. {key}: {format_bytes(size)}")
        else:
            # Show summary for all memory-bounded caches
            for name, cache in memory_bounded_caches.items():
                memory_info = cache.get_memory_usage()
                
                print(f"{name}:")
                print(f"  Size: {memory_info['current_size_human']} / {memory_info['max_size_human']}")
                print(f"  Pressure: {memory_info['memory_pressure'] * 100:.1f}%")
                print(f"  Items: {memory_info['item_count']}")
    
    # Show regular cache stats
    if regular_caches and not (args.cache and args.cache in memory_bounded_caches):
        print("\nRegular Caches:")
        
        for name, cache in regular_caches.items():
            if args.cache and args.cache != name:
                continue
                
            item_count = len(cache._cache) if hasattr(cache, '_cache') else 0
            print(f"{name}:")
            print(f"  Items: {item_count}")
            print(f"  Note: Memory tracking not available for regular caches")

def clear_cache(args):
    """Clear cache contents.
    
    Args:
        args: Command-line arguments
    """
    caches = cache_coordinator.get_all_caches()
    
    if args.cache and args.cache not in caches:
        print(f"Cache '{args.cache}' not found.")
        print(f"Available caches: {', '.join(sorted(caches.keys()))}")
        return
    
    # Confirm unless --confirm flag is set
    if not args.confirm:
        target = f"cache '{args.cache}'" if args.cache else "ALL caches"
        confirm = input(f"Are you sure you want to clear {target}? (y/N): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            return
    
    if args.cache:
        # Clear specific cache
        caches[args.cache].clear()
        print(f"Cache '{args.cache}' cleared.")
    else:
        # Clear all caches
        for name, cache in caches.items():
            cache.clear()
        print("All caches cleared.")

def configure_cache(args):
    """Configure cache settings.
    
    Args:
        args: Command-line arguments
    """
    caches = cache_coordinator.get_all_caches()
    
    if args.cache not in caches:
        print(f"Cache '{args.cache}' not found.")
        print(f"Available caches: {', '.join(sorted(caches.keys()))}")
        return
    
    cache = caches[args.cache]
    
    # Configure TTL if specified
    if args.ttl is not None:
        if hasattr(cache, '_default_ttl'):
            old_ttl = cache._default_ttl
            cache._default_ttl = args.ttl
            print(f"Updated default TTL for cache '{args.cache}' from {old_ttl}s to {args.ttl}s")
        else:
            print(f"Cannot set TTL for cache '{args.cache}': TTL not supported")
    
    # Configure max size if specified
    if args.max_size is not None:
        if isinstance(cache, MemoryBoundedCache):
            try:
                new_size_bytes = parse_size_string(args.max_size)
                cache.resize(new_size_bytes)
                print(f"Resized cache '{args.cache}' to {args.max_size}")
            except ValueError as e:
                print(f"Error: {str(e)}")
        else:
            print(f"Cannot resize cache '{args.cache}': Not a memory-bounded cache")

def export_stats(args):
    """Export cache statistics to a file.
    
    Args:
        args: Command-line arguments
    """
    caches = cache_coordinator.get_all_caches()
    
    # Collect statistics for each cache
    stats = {
        "timestamp": datetime.now().isoformat(),
        "caches": {}
    }
    
    for name, cache in caches.items():
        cache_stats = {
            "type": type(cache).__name__,
            "metrics": cache.get_metrics().__dict__,
        }
        
        # Add memory info for memory-bounded caches
        if isinstance(cache, MemoryBoundedCache):
            cache_stats["memory"] = cache.get_memory_usage()
        
        # Add pattern info for pattern caches
        if isinstance(cache, PatternCache):
            cache_stats["patterns"] = cache.get_pattern_metadata()
        
        stats["caches"][name] = cache_stats
    
    # Export to file
    with open(args.output, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"Cache statistics exported to {args.output}")

def analyze_cache_effectiveness(args):
    """Analyze cache effectiveness and generate recommendations.
    
    Args:
        args: Command-line arguments
    """
    caches = cache_coordinator.get_all_caches()
    
    if args.cache and args.cache not in caches:
        print(f"Cache '{args.cache}' not found.")
        print(f"Available caches: {', '.join(sorted(caches.keys()))}")
        return
    
    print("\nCache Effectiveness Analysis:")
    print("=" * 80)
    
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "analyses": {}
    }
    
    # Analyze specific cache or all caches
    target_caches = {args.cache: caches[args.cache]} if args.cache else caches
    
    for name, cache in target_caches.items():
        metrics = cache.get_metrics()
        
        # Basic effectiveness metrics
        hit_rate = metrics.hit_rate
        total_ops = metrics.hits + metrics.misses
        eviction_rate = metrics.evictions / total_ops if total_ops > 0 else 0
        
        cache_analysis = {
            "hit_rate": hit_rate,
            "total_operations": total_ops,
            "eviction_rate": eviction_rate,
            "issues": [],
            "recommendations": []
        }
        
        # Identify potential issues
        if hit_rate < 0.5 and total_ops > 100:
            cache_analysis["issues"].append("Low hit rate")
            cache_analysis["recommendations"].append(
                "Consider adjusting cache TTL or reviewing what items are cached"
            )
        
        if eviction_rate > 0.2:
            cache_analysis["issues"].append("High eviction rate")
            cache_analysis["recommendations"].append(
                "Consider increasing cache size or being more selective about what to cache"
            )
        
        # Memory-specific analysis
        if isinstance(cache, MemoryBoundedCache):
            memory_info = cache.get_memory_usage()
            memory_pressure = memory_info["memory_pressure"]
            
            cache_analysis["memory_pressure"] = memory_pressure
            
            if memory_pressure > 0.9:
                cache_analysis["issues"].append("High memory pressure")
                cache_analysis["recommendations"].append(
                    "Increase cache size or reduce number of cached items"
                )
            elif memory_pressure < 0.3 and memory_info["max_size_bytes"] > 10*1024*1024:
                cache_analysis["issues"].append("Low memory utilization")
                cache_analysis["recommendations"].append(
                    "Consider reducing max cache size to free memory for other uses"
                )
        
        # Print analysis
        print(f"\nAnalysis for cache '{name}':")
        print(f"  Hit Rate: {hit_rate * 100:.1f}%")
        print(f"  Operations: {total_ops}")
        print(f"  Eviction Rate: {eviction_rate * 100:.1f}%")
        
        if isinstance(cache, MemoryBoundedCache):
            memory_info = cache.get_memory_usage()
            print(f"  Memory Usage: {memory_info['current_size_human']} / {memory_info['max_size_human']}")
            print(f"  Memory Pressure: {memory_info['memory_pressure'] * 100:.1f}%")
        
        if cache_analysis["issues"]:
            print("\n  Issues:")
            for issue in cache_analysis["issues"]:
                print(f"    - {issue}")
        
        if cache_analysis["recommendations"]:
            print("\n  Recommendations:")
            for recommendation in cache_analysis["recommendations"]:
                print(f"    - {recommendation}")
        
        # Add to analysis dict
        analysis["analyses"][name] = cache_analysis
    
    # Overall recommendations
    print("\nOverall Recommendations:")
    overall_recommendations = []
    
    # Pattern cache specific recommendations
    pattern_caches = [c for c in target_caches.values() if isinstance(c, PatternCache)]
    if pattern_caches:
        has_pattern_cache_issues = any(
            a["analyses"].get(name, {}).get("hit_rate", 1) < 0.7
            for name, c in target_caches.items()
            if isinstance(c, PatternCache)
        )
        
        if has_pattern_cache_issues:
            rec = "Implement pattern cache warming for frequently used patterns"
            overall_recommendations.append(rec)
            print(f"  - {rec}")
    
    # Memory usage recommendations
    memory_bounded_caches = [c for c in target_caches.values() if isinstance(c, MemoryBoundedCache)]
    if memory_bounded_caches:
        high_pressure_caches = [
            name for name, c in target_caches.items()
            if isinstance(c, MemoryBoundedCache) and c.get_memory_usage()["memory_pressure"] > 0.9
        ]
        
        if high_pressure_caches:
            rec = "Monitor memory usage and consider increasing cache limits"
            overall_recommendations.append(rec)
            print(f"  - {rec}")
    
    analysis["overall_recommendations"] = overall_recommendations
    
    # Export analysis if output specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"\nAnalysis exported to {args.output}")

def main():
    """Main function."""
    args = parse_args()
    
    if not args.command:
        # No command specified, show help
        print("Error: Command is required")
        print("Use --help for usage information")
        return 1
    
    commands = {
        "list": lambda a: list_caches(a),
        "stats": lambda a: watch_cache_stats(a) if a.watch else show_cache_stats(a.cache),
        "memory": lambda a: show_memory_usage(a),
        "clear": lambda a: clear_cache(a),
        "configure": lambda a: configure_cache(a),
        "export": lambda a: export_stats(a),
        "analyze": lambda a: analyze_cache_effectiveness(a)
    }
    
    if args.command in commands:
        commands[args.command](args)
        return 0
    else:
        print(f"Unknown command: {args.command}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 