#!/usr/bin/env python3
"""
Script to profile pattern compilation performance and identify bottlenecks.

This script:
1. Instruments pattern compilation in the codebase
2. Executes a sample workload of pattern compilations
3. Analyzes the performance data
4. Generates a detailed report with optimization recommendations
"""

import os
import sys
import time
import argparse
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pattern_profiler import (
    pattern_profiler, 
    profile_compilation,
    estimate_pattern_complexity, 
    analyze_pattern_bottlenecks
)
from utils.logger import log
from parsers.pattern_processor import PatternProcessor, compile_patterns
from parsers.file_classification import classify_file

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Profile pattern compilation performance")
    parser.add_argument(
        "--sampling-rate", 
        type=float, 
        default=1.0,
        help="Sampling rate for profiling (0.0-1.0)"
    )
    parser.add_argument(
        "--pattern-dirs", 
        type=str, 
        nargs="+", 
        default=["parsers/query_patterns"],
        help="Directories containing pattern definitions"
    )
    parser.add_argument(
        "--test-files", 
        type=str, 
        nargs="+", 
        default=[],
        help="Files to use for testing pattern compilation"
    )
    parser.add_argument(
        "--generate-report", 
        action="store_true",
        help="Generate a detailed report"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default=None,
        help="Output file for the report (JSON format)"
    )
    return parser.parse_args()

def instrument_pattern_processor():
    """Instrument the PatternProcessor class with profiling decorators."""
    log("Instrumenting PatternProcessor for profiling", level="info")
    
    # Instrument the compile_patterns function
    orig_compile_patterns = compile_patterns
    
    @profile_compilation
    def profiled_compile_patterns(*args, **kwargs):
        return orig_compile_patterns(*args, **kwargs)
    
    # Monkey patch the function
    import parsers.pattern_processor
    parsers.pattern_processor.compile_patterns = profiled_compile_patterns
    
    # Instrument relevant PatternProcessor methods
    PatternProcessor._process_regex_pattern = profile_compilation(PatternProcessor._process_regex_pattern)
    
    log("Instrumentation complete", level="info")

def load_sample_patterns(pattern_dirs):
    """Load sample patterns from the given directories."""
    log(f"Loading patterns from: {', '.join(pattern_dirs)}", level="info")
    
    patterns = {}
    pattern_count = 0
    
    for pattern_dir in pattern_dirs:
        if not os.path.exists(pattern_dir):
            log(f"Pattern directory does not exist: {pattern_dir}", level="warning")
            continue
            
        for file in os.listdir(pattern_dir):
            if file.endswith(".py") and not file.startswith("__"):
                file_path = os.path.join(pattern_dir, file)
                language = file.split(".")[0]
                
                # Import the module
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"pattern_{language}", file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find pattern definitions
                for attr_name in dir(module):
                    if attr_name.endswith("_PATTERNS") and not attr_name.startswith("__"):
                        pattern_dict = getattr(module, attr_name)
                        if isinstance(pattern_dict, dict):
                            patterns[f"{language}_{attr_name}"] = pattern_dict
                            pattern_count += len(pattern_dict)
    
    log(f"Loaded {pattern_count} patterns from {len(patterns)} pattern collections", level="info")
    return patterns

def profile_pattern_compilations(patterns):
    """Profile compilation of the loaded patterns."""
    log("Profiling pattern compilations...", level="info")
    
    pattern_processor = PatternProcessor()
    
    # Force pattern processor to load and compile patterns
    start_time = time.time()
    total_patterns = 0
    
    for collection_name, pattern_dict in patterns.items():
        log(f"Compiling {len(pattern_dict)} patterns from {collection_name}", level="info")
        
        for pattern_name, pattern_def in pattern_dict.items():
            # Calculate pattern complexity
            pattern_string = getattr(pattern_def, 'pattern', '')
            if pattern_string and isinstance(pattern_string, str):
                complexity = estimate_pattern_complexity(pattern_string)
                pattern_profiler.pattern_complexity[f"{collection_name}.{pattern_name}"] = complexity
            
            # Compile the pattern (will be profiled by our instrumentation)
            pattern_processor.register_pattern(f"{collection_name}.{pattern_name}", pattern_def)
            total_patterns += 1
    
    end_time = time.time()
    log(f"Compiled {total_patterns} patterns in {end_time - start_time:.2f} seconds", level="info")

def process_test_files(test_files, pattern_processor):
    """Process test files using the pattern processor to exercise pattern matching."""
    if not test_files:
        log("No test files specified, skipping file processing test", level="info")
        return
        
    log(f"Processing {len(test_files)} test files", level="info")
    
    for file_path in test_files:
        if not os.path.exists(file_path):
            log(f"Test file not found: {file_path}", level="warning")
            continue
            
        try:
            # Classify the file
            classification = classify_file(file_path)
            
            # Read the file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Process patterns
            log(f"Processing file: {file_path} (language: {classification.language_id})", level="info")
            matches = pattern_processor.process_content(content, classification.language_id)
            log(f"Found {len(matches)} pattern matches", level="info")
            
        except Exception as e:
            log(f"Error processing test file {file_path}: {str(e)}", level="error")

def generate_profiling_report(output_file=None):
    """Generate a comprehensive profiling report."""
    log("Generating profiling report...", level="info")
    
    # Get profiling data
    report = pattern_profiler.generate_report()
    
    # Find bottlenecks
    bottlenecks = analyze_pattern_bottlenecks()
    report["bottlenecks"] = bottlenecks
    
    # Save report
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        log(f"Report saved to: {output_file}", level="info")
    else:
        # Save to default location
        report_file = pattern_profiler.save_report()
        log(f"Report saved to: {report_file}", level="info")
    
    # Print summary to console
    print("\n=== Pattern Compilation Profiling Summary ===")
    print(f"Total compilation time: {report['total_compilation_time']:.2f} seconds")
    print(f"Total patterns: {report['total_patterns']}")
    print(f"Total compilations: {report['total_compilations']}")
    
    print("\nTop 5 slowest patterns:")
    for name, time in report["slowest_patterns"][:5]:
        print(f"  - {name}: {time:.4f} seconds average")
    
    print("\nTop 5 most compiled patterns:")
    for name, count in report["most_compiled"][:5]:
        print(f"  - {name}: {count} compilations")
    
    print("\nIdentified bottlenecks:")
    for bottleneck in bottlenecks[:5]:
        print(f"  - {bottleneck['pattern_name']}")
        print(f"    Reasons: {', '.join(bottleneck['reasons'])}")
        print(f"    Suggestions: {', '.join(bottleneck['optimization_suggestions'][:2])}")
    
    return report

def print_optimization_recommendations(bottlenecks):
    """Print optimization recommendations based on profiling results."""
    print("\n=== Optimization Recommendations ===")
    
    if not bottlenecks:
        print("No significant bottlenecks identified.")
        return
    
    # Group by optimization type
    recommendations = {
        "caching": [],
        "simplification": [],
        "refactoring": [],
        "other": []
    }
    
    for bottleneck in bottlenecks:
        for suggestion in bottleneck["optimization_suggestions"]:
            if "caching" in suggestion.lower():
                recommendations["caching"].append((bottleneck["pattern_name"], suggestion))
            elif "simplify" in suggestion.lower():
                recommendations["simplification"].append((bottleneck["pattern_name"], suggestion))
            elif "refactor" in suggestion.lower():
                recommendations["refactoring"].append((bottleneck["pattern_name"], suggestion))
            else:
                recommendations["other"].append((bottleneck["pattern_name"], suggestion))
    
    # Print recommendations by category
    if recommendations["caching"]:
        print("\n1. Caching Recommendations:")
        for name, suggestion in recommendations["caching"][:3]:
            print(f"  - {name}: {suggestion}")
    
    if recommendations["simplification"]:
        print("\n2. Pattern Simplification Recommendations:")
        for name, suggestion in recommendations["simplification"][:3]:
            print(f"  - {name}: {suggestion}")
    
    if recommendations["refactoring"]:
        print("\n3. Pattern Refactoring Recommendations:")
        for name, suggestion in recommendations["refactoring"][:3]:
            print(f"  - {name}: {suggestion}")
    
    if recommendations["other"]:
        print("\n4. Other Recommendations:")
        for name, suggestion in recommendations["other"][:3]:
            print(f"  - {name}: {suggestion}")
    
    # Overall recommendations
    print("\nOverall Strategy Recommendations:")
    print("  1. Implement pattern caching for frequently used patterns")
    print("  2. Break down complex patterns into simpler components")
    print("  3. Consider lazy loading of patterns by language")
    print("  4. Re-run profiling after implementing changes to measure impact")

def main():
    """Main function to run pattern profiling."""
    args = parse_args()
    
    # Configure profiler
    pattern_profiler.configure(sampling_rate=args.sampling_rate)
    pattern_profiler.reset()  # Start with clean slate
    
    # Instrument code
    instrument_pattern_processor()
    
    # Load and profile patterns
    patterns = load_sample_patterns(args.pattern_dirs)
    profile_pattern_compilations(patterns)
    
    # Create pattern processor for test processing
    pattern_processor = PatternProcessor()
    
    # Process test files if provided
    process_test_files(args.test_files, pattern_processor)
    
    # Generate report if requested
    if args.generate_report:
        report = generate_profiling_report(args.output)
        print_optimization_recommendations(report.get("bottlenecks", []))
    
    log("Pattern profiling completed", level="info")

if __name__ == "__main__":
    main() 