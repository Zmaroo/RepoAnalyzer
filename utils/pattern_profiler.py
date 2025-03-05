"""Pattern compilation profiling tools.

This module provides tools to profile and analyze pattern compilation performance.
It helps identify bottlenecks in pattern processing and compilation to improve
overall system performance.
"""

import time
import functools
import statistics
from typing import Dict, List, Callable, Any, Optional, Set, Tuple
import threading
import json
import os
from contextlib import contextmanager
from datetime import datetime
from utils.logger import log

# Singleton to store profiling data
class PatternProfiler:
    """Singleton class to track pattern compilation metrics."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(PatternProfiler, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize the profiler state."""
        self.compilation_times: Dict[str, List[float]] = {}
        self.pattern_sizes: Dict[str, int] = {}
        self.pattern_complexity: Dict[str, int] = {}
        self.compilation_count: Dict[str, int] = {}
        self.total_compilation_time = 0.0
        self.sampling_rate = 1.0  # Sample all by default
        self.enabled = True
        self.reports_dir = os.path.join("reports", "pattern_profiling")
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def configure(self, sampling_rate: float = 1.0, enabled: bool = True):
        """Configure the profiler."""
        self.sampling_rate = max(0.0, min(1.0, sampling_rate))
        self.enabled = enabled
    
    def record_compilation(self, 
                          pattern_name: str, 
                          compilation_time: float, 
                          pattern_size: int = 0,
                          complexity_score: int = 0):
        """Record a pattern compilation event."""
        if not self.enabled:
            return
            
        import random
        if random.random() > self.sampling_rate:
            return
            
        with self._lock:
            if pattern_name not in self.compilation_times:
                self.compilation_times[pattern_name] = []
                self.compilation_count[pattern_name] = 0
                
            self.compilation_times[pattern_name].append(compilation_time)
            self.compilation_count[pattern_name] += 1
            self.total_compilation_time += compilation_time
            
            if pattern_size > 0:
                self.pattern_sizes[pattern_name] = pattern_size
                
            if complexity_score > 0:
                self.pattern_complexity[pattern_name] = complexity_score
    
    def get_pattern_stats(self, pattern_name: str) -> Dict[str, Any]:
        """Get statistics for a specific pattern."""
        if pattern_name not in self.compilation_times or not self.compilation_times[pattern_name]:
            return {}
            
        times = self.compilation_times[pattern_name]
        return {
            "count": self.compilation_count[pattern_name],
            "avg_time": statistics.mean(times) if times else 0,
            "max_time": max(times) if times else 0,
            "min_time": min(times) if times else 0,
            "median_time": statistics.median(times) if times else 0,
            "stdev_time": statistics.stdev(times) if len(times) > 1 else 0,
            "pattern_size": self.pattern_sizes.get(pattern_name, 0),
            "complexity_score": self.pattern_complexity.get(pattern_name, 0),
            "total_time": sum(times)
        }
    
    def get_slowest_patterns(self, limit: int = 10) -> List[Tuple[str, float]]:
        """Get the slowest patterns by average compilation time."""
        pattern_avgs = []
        for pattern_name, times in self.compilation_times.items():
            if times:
                pattern_avgs.append((pattern_name, statistics.mean(times)))
        
        return sorted(pattern_avgs, key=lambda x: x[1], reverse=True)[:limit]
    
    def get_most_compiled_patterns(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get the most frequently compiled patterns."""
        return sorted(
            self.compilation_count.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:limit]
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive profiling report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_compilation_time": self.total_compilation_time,
            "total_patterns": len(self.compilation_times),
            "total_compilations": sum(self.compilation_count.values()),
            "slowest_patterns": self.get_slowest_patterns(20),
            "most_compiled": self.get_most_compiled_patterns(20),
            "pattern_details": {}
        }
        
        # Add detailed stats for each pattern
        for pattern_name in self.compilation_times:
            report["pattern_details"][pattern_name] = self.get_pattern_stats(pattern_name)
        
        return report
    
    def save_report(self, filename: Optional[str] = None) -> str:
        """Save the current profiling report to a file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pattern_profile_{timestamp}.json"
            
        report = self.generate_report()
        filepath = os.path.join(self.reports_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
            
        log(f"Pattern profiling report saved to {filepath}", level="info")
        return filepath
    
    def reset(self):
        """Reset all profiling data."""
        with self._lock:
            self.compilation_times = {}
            self.pattern_sizes = {}
            self.pattern_complexity = {}
            self.compilation_count = {}
            self.total_compilation_time = 0.0

    def cleanup(self):
        """Clean up and save final report."""
        try:
            if self.enabled:
                self.save_report()
                self.reset()
        except Exception as e:
            log(f"Error cleaning up pattern profiler: {e}", level="error")

# Global instance
pattern_profiler = PatternProfiler()

@contextmanager
def profile_pattern_compilation(pattern_name: str, pattern_size: int = 0, complexity_score: int = 0):
    """Context manager for profiling pattern compilation.
    
    Args:
        pattern_name: Name or identifier for the pattern
        pattern_size: Size of the pattern in characters
        complexity_score: Estimated complexity score (higher = more complex)
    
    Example:
        ```python
        with profile_pattern_compilation("my_pattern", pattern_size=len(pattern_str)):
            compiled_pattern = compile_pattern(pattern_str)
        ```
    """
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        compilation_time = end_time - start_time
        pattern_profiler.record_compilation(
            pattern_name, 
            compilation_time, 
            pattern_size, 
            complexity_score
        )

def profile_compilation(func: Callable) -> Callable:
    """Decorator to profile pattern compilation functions.
    
    This decorator automatically profiles compilation time for the decorated function.
    The pattern name is derived from the function arguments.
    
    Args:
        func: The function to profile
        
    Returns:
        Wrapped function with profiling
        
    Example:
        ```python
        @profile_compilation
        def compile_pattern(pattern_name, pattern_str):
            # Compilation logic
            return compiled_pattern
        ```
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Try to extract pattern name from args or kwargs
        pattern_name = None
        pattern_size = 0
        
        # If first arg is a string, use it as pattern name
        if args and isinstance(args[0], str):
            pattern_name = args[0]
            
        # Check if pattern_name or name is in kwargs
        if not pattern_name:
            pattern_name = kwargs.get('pattern_name', 
                          kwargs.get('name', f"{func.__name__}_unknown"))
        
        # Try to get pattern size
        pattern_str = None
        if len(args) > 1 and isinstance(args[1], str):
            pattern_str = args[1]
        elif 'pattern' in kwargs and isinstance(kwargs['pattern'], str):
            pattern_str = kwargs['pattern']
            
        if pattern_str:
            pattern_size = len(pattern_str)
            
        with profile_pattern_compilation(pattern_name, pattern_size):
            return func(*args, **kwargs)
            
    return wrapper

def estimate_pattern_complexity(pattern: str) -> int:
    """Estimate the computational complexity of a pattern.
    
    This is a heuristic function that analyzes a pattern string
    and estimates its computational complexity based on features
    known to make regex or tree-sitter patterns more expensive.
    
    Args:
        pattern: The pattern string to analyze
        
    Returns:
        Complexity score (higher = more complex)
    """
    complexity = 0
    
    # Count potentially expensive operations
    if not pattern:
        return 0
        
    # Check for nested quantifiers (expensive in regex)
    nested_quantifier_count = pattern.count('*') + pattern.count('+') + pattern.count('?')
    nested_quantifier_count += pattern.count('{')
    complexity += nested_quantifier_count * 5
    
    # Check for backreferences
    backreference_count = sum(1 for i in range(10) if f'\\{i}' in pattern)
    complexity += backreference_count * 10
    
    # Check for lookahead/lookbehind assertions
    lookaround_count = pattern.count('(?=') + pattern.count('(?!') + \
                       pattern.count('(?<=') + pattern.count('(?<!')
    complexity += lookaround_count * 15
    
    # Check for capture groups
    capture_group_count = pattern.count('(')
    complexity += capture_group_count * 3
    
    # Check for alternation
    alternation_count = pattern.count('|')
    complexity += alternation_count * 7
    
    # Check for character classes
    char_class_count = pattern.count('[')
    complexity += char_class_count * 2
    
    # Check for recursion
    recursion_count = pattern.count('@')  # Tree-sitter recursion
    complexity += recursion_count * 8
    
    # Tree-sitter specific: check for predicates
    predicate_count = pattern.count('#')
    complexity += predicate_count * 5
    
    # Tree-sitter specific: check for wildcards
    wildcard_count = pattern.count('_') + pattern.count('.')
    complexity += wildcard_count * 3
    
    return complexity

def analyze_pattern_bottlenecks() -> List[Dict[str, Any]]:
    """Analyze current profiling data to identify bottlenecks.
    
    Returns:
        List of bottleneck patterns with analysis
    """
    bottlenecks = []
    report = pattern_profiler.generate_report()
    
    for pattern_name, stats in report["pattern_details"].items():
        if not stats:
            continue
            
        # Identify bottlenecks based on compilation time and frequency
        is_bottleneck = False
        bottleneck_reason = []
        
        # Check if average compilation time is high
        if stats.get("avg_time", 0) > 0.1:  # More than 100ms
            is_bottleneck = True
            bottleneck_reason.append("high average compilation time")
            
        # Check if pattern is compiled frequently
        if stats.get("count", 0) > 100:  # Compiled more than 100 times
            if stats.get("avg_time", 0) > 0.01:  # More than 10ms
                is_bottleneck = True
                bottleneck_reason.append("frequently compiled with significant time")
                
        # Check if pattern has high complexity
        if stats.get("complexity_score", 0) > 50:
            is_bottleneck = True
            bottleneck_reason.append("high pattern complexity")
                
        if is_bottleneck:
            bottlenecks.append({
                "pattern_name": pattern_name,
                "reasons": bottleneck_reason,
                "stats": stats,
                "optimization_suggestions": suggest_optimizations(pattern_name, stats)
            })
    
    return sorted(bottlenecks, key=lambda x: x["stats"].get("total_time", 0), reverse=True)

def suggest_optimizations(pattern_name: str, stats: Dict[str, Any]) -> List[str]:
    """Suggest optimization strategies for a pattern.
    
    Args:
        pattern_name: Name of the pattern
        stats: Statistics for the pattern
        
    Returns:
        List of optimization suggestions
    """
    suggestions = []
    
    # Check compilation frequency
    if stats.get("count", 0) > 100:
        suggestions.append("Consider caching the compiled pattern")
        
    # Check pattern complexity
    if stats.get("complexity_score", 0) > 50:
        suggestions.append("Simplify pattern complexity by breaking into smaller patterns")
        
    # Check pattern size
    if stats.get("pattern_size", 0) > 500:
        suggestions.append("Pattern is very large, consider refactoring into smaller patterns")
        
    # Check compilation time variability
    if stats.get("stdev_time", 0) > stats.get("avg_time", 0) * 0.5:
        suggestions.append("High variability in compilation time, investigate inconsistent behavior")
        
    # Generic suggestions
    suggestions.append("Review pattern for optimization opportunities (nested quantifiers, lookarounds, etc.)")
    
    return suggestions 