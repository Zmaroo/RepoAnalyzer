#!/usr/bin/env python3
"""
Pattern Analysis Tool

This script provides a command-line interface for analyzing pattern statistics,
generating visualizations, and getting recommendations for pattern optimization.
"""

import sys
import os
import argparse
import json
import time
from pathlib import Path
from datetime import datetime

# Add the parent directory to the Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from analytics.pattern_statistics import pattern_statistics
    from parsers.models import PatternType
    from utils.logger import log
except ImportError as e:
    print(f"Error importing required modules: {str(e)}")
    print("Please run this script from the project root directory.")
    sys.exit(1)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Pattern Analysis Tool - Analyze pattern statistics and generate reports"
    )
    
    subparsers = parser.add_subparsers(
        dest="command", help="Commands", required=True
    )
    
    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze pattern statistics and generate insights"
    )
    analyze_parser.add_argument(
        "--output", "-o", 
        help="Path to save the analysis results (JSON format)",
        default="pattern_analysis.json"
    )
    analyze_parser.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Show detailed analysis output"
    )
    
    # Show command
    show_parser = subparsers.add_parser(
        "show", help="Show pattern statistics"
    )
    show_parser.add_argument(
        "--by", choices=["language", "type", "value", "bottleneck"],
        default="value",
        help="How to organize the statistics"
    )
    show_parser.add_argument(
        "--top", type=int, default=10,
        help="Number of top patterns to show"
    )
    
    # Recommendations command
    recommendations_parser = subparsers.add_parser(
        "recommendations", help="Get recommendations for pattern optimization"
    )
    recommendations_parser.add_argument(
        "--output", "-o",
        help="Path to save the recommendations (JSON format)",
        default=""
    )
    
    # Visualize command
    visualize_parser = subparsers.add_parser(
        "visualize", help="Generate visualizations of pattern statistics"
    )
    visualize_parser.add_argument(
        "--output", "-o",
        help="Path to save the visualization",
        default="pattern_analysis.png"
    )
    
    # Export command
    export_parser = subparsers.add_parser(
        "export", help="Export pattern statistics to a file"
    )
    export_parser.add_argument(
        "--output", "-o",
        help="Path to save the exported statistics (JSON format)",
        default="pattern_statistics.json"
    )
    
    # Cache warming command
    warm_parser = subparsers.add_parser(
        "warm", help="Generate cache warming recommendations"
    )
    warm_parser.add_argument(
        "--output", "-o",
        help="Path to save the cache warming recommendations (JSON format)",
        default=""
    )
    
    # Pattern command
    pattern_parser = subparsers.add_parser(
        "pattern", help="Get details for a specific pattern"
    )
    pattern_parser.add_argument(
        "pattern_id", help="Pattern identifier"
    )
    pattern_parser.add_argument(
        "--language", "-l", default="unknown",
        help="Language of the pattern"
    )
    pattern_parser.add_argument(
        "--type", "-t", default="code_structure",
        help="Type of the pattern (code_structure, code_naming, error_handling, etc.)"
    )
    
    return parser.parse_args()

def analyze_command(args):
    """Run the analyze command."""
    print("Analyzing pattern statistics...")
    
    analysis = pattern_statistics.analyze_patterns()
    
    if analysis.get("status") == "no_data":
        print("No pattern statistics available for analysis.")
        return
    
    # Save to file if specified
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(analysis, f, indent=2)
            print(f"Analysis results saved to {args.output}")
        except Exception as e:
            print(f"Error saving analysis results: {str(e)}")
    
    # Print summary
    print(f"\n{'='*50}")
    print("PATTERN ANALYSIS SUMMARY")
    print(f"{'='*50}")
    print(f"Total patterns analyzed: {analysis['total_patterns']}")
    print(f"Analysis time: {datetime.fromtimestamp(analysis['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\nBy Language:")
    for language, stats in analysis["by_language"].items():
        print(f"  {language}: {stats['pattern_count']} patterns, {stats['total_matches']} matches, "
              f"hit ratio: {stats['avg_hit_ratio']:.2f}")
    
    print("\nBy Pattern Type:")
    for pattern_type, stats in analysis["by_pattern_type"].items():
        print(f"  {pattern_type}: {stats['pattern_count']} patterns, {stats['total_matches']} matches, "
              f"hit ratio: {stats['avg_hit_ratio']:.2f}")
    
    print("\nTop 5 Most Valuable Patterns:")
    for i, pattern in enumerate(analysis["most_valuable_patterns"][:5], 1):
        print(f"  {i}. {pattern['pattern_id']} ({pattern['language']}/{pattern['type']}): "
              f"value: {pattern['value_score']:.2f}, hit ratio: {pattern['hit_ratio']:.2f}")
    
    print("\nTop 5 Performance Bottlenecks:")
    for i, pattern in enumerate(analysis["performance_bottlenecks"][:5], 1):
        print(f"  {i}. {pattern['pattern_id']} ({pattern['language']}/{pattern['type']}): "
              f"value: {pattern['value_score']:.2f}, avg execution: {pattern['avg_execution_time']:.2f}ms")
    
    print("\nRecommendations:")
    for i, rec in enumerate(analysis["recommendations"], 1):
        print(f"  {i}. {rec['type'].upper()}: {rec.get('pattern_id', rec.get('language', 'Unknown'))} - {rec['reason']}")
    
    # Print detailed analysis if requested
    if args.verbose:
        print(f"\n{'='*50}")
        print("DETAILED ANALYSIS")
        print(f"{'='*50}")
        
        print("\nAll Valuable Patterns:")
        for i, pattern in enumerate(analysis["most_valuable_patterns"], 1):
            print(f"  {i}. {pattern['pattern_id']} ({pattern['language']}/{pattern['type']}): "
                  f"value: {pattern['value_score']:.2f}, hit ratio: {pattern['hit_ratio']:.2f}, "
                  f"avg execution: {pattern['avg_execution_time']:.2f}ms")
        
        print("\nAll Performance Bottlenecks:")
        for i, pattern in enumerate(analysis["performance_bottlenecks"], 1):
            print(f"  {i}. {pattern['pattern_id']} ({pattern['language']}/{pattern['type']}): "
                  f"value: {pattern['value_score']:.2f}, avg execution: {pattern['avg_execution_time']:.2f}ms, "
                  f"executions: {pattern['executions']}, matches: {pattern['matches']}")

def show_command(args):
    """Run the show command."""
    if args.by == "language":
        language_stats = pattern_statistics.get_language_statistics()
        
        if not language_stats:
            print("No pattern statistics available.")
            return
        
        print(f"\n{'='*50}")
        print("PATTERN STATISTICS BY LANGUAGE")
        print(f"{'='*50}")
        
        # Sort languages by pattern count
        sorted_languages = sorted(
            language_stats.items(),
            key=lambda x: x[1]["pattern_count"],
            reverse=True
        )
        
        for language, stats in sorted_languages:
            print(f"\nLanguage: {language}")
            print(f"  Pattern count: {stats['pattern_count']}")
            print(f"  Total executions: {stats['total_executions']}")
            print(f"  Total matches: {stats['total_matches']}")
            print(f"  Average hit ratio: {stats['avg_hit_ratio']:.2f}")
            print(f"  Average execution time: {stats['avg_execution_time_ms']:.2f}ms")
            
            print("  Patterns by type:")
            for pattern_type, count in stats['patterns_by_type'].items():
                print(f"    {pattern_type}: {count}")
    
    elif args.by == "type":
        analysis = pattern_statistics.analyze_patterns()
        
        if analysis.get("status") == "no_data":
            print("No pattern statistics available.")
            return
        
        print(f"\n{'='*50}")
        print("PATTERN STATISTICS BY TYPE")
        print(f"{'='*50}")
        
        # Sort pattern types by pattern count
        sorted_types = sorted(
            analysis["by_pattern_type"].items(),
            key=lambda x: x[1]["pattern_count"],
            reverse=True
        )
        
        for pattern_type, stats in sorted_types:
            print(f"\nPattern type: {pattern_type}")
            print(f"  Pattern count: {stats['pattern_count']}")
            print(f"  Total executions: {stats['total_executions']}")
            print(f"  Total matches: {stats['total_matches']}")
            print(f"  Average hit ratio: {stats['avg_hit_ratio']:.2f}")
            print(f"  Average execution time: {stats['avg_execution_time']:.2f}ms")
    
    elif args.by == "value":
        patterns = pattern_statistics.get_pattern_value_ranking()
        
        if not patterns:
            print("No pattern statistics available.")
            return
        
        print(f"\n{'='*50}")
        print("PATTERNS BY VALUE SCORE")
        print(f"{'='*50}")
        
        for i, pattern in enumerate(patterns[:args.top], 1):
            print(f"{i}. {pattern['pattern_id']} ({pattern['language']}/{pattern['type']})")
            print(f"   Value score: {pattern['value_score']:.2f}")
            print(f"   Hit ratio: {pattern['hit_ratio']:.2f}")
            print(f"   Avg execution time: {pattern['avg_execution_time']:.2f}ms")
            print(f"   Executions: {pattern['executions']}, Matches: {pattern['matches']}")
            print()
    
    elif args.by == "bottleneck":
        analysis = pattern_statistics.analyze_patterns()
        
        if analysis.get("status") == "no_data":
            print("No pattern statistics available.")
            return
        
        bottlenecks = analysis["performance_bottlenecks"]
        
        print(f"\n{'='*50}")
        print("PERFORMANCE BOTTLENECKS")
        print(f"{'='*50}")
        
        for i, pattern in enumerate(bottlenecks[:args.top], 1):
            print(f"{i}. {pattern['pattern_id']} ({pattern['language']}/{pattern['type']})")
            print(f"   Value score: {pattern['value_score']:.2f}")
            print(f"   Avg execution time: {pattern['avg_execution_time']:.2f}ms")
            print(f"   Executions: {pattern['executions']}, Matches: {pattern['matches']}")
            print()

def recommendations_command(args):
    """Run the recommendations command."""
    recommendations = pattern_statistics.get_recommendations()
    
    if not recommendations:
        print("No recommendations available. Run more pattern executions to generate recommendations.")
        return
    
    print(f"\n{'='*50}")
    print("PATTERN OPTIMIZATION RECOMMENDATIONS")
    print(f"{'='*50}")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec['type'].upper()}")
        
        if "pattern_id" in rec:
            print(f"   Pattern: {rec['pattern_id']} ({rec.get('language', 'unknown')})")
        elif "language" in rec:
            print(f"   Language: {rec['language']}")
        
        print(f"   Reason: {rec['reason']}")
        print()
    
    # Save to file if specified
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(recommendations, f, indent=2)
            print(f"Recommendations saved to {args.output}")
        except Exception as e:
            print(f"Error saving recommendations: {str(e)}")

def visualize_command(args):
    """Run the visualize command."""
    print("Generating visualization...")
    
    output_path = pattern_statistics.generate_visualization(args.output)
    
    if output_path:
        print(f"Visualization saved to {output_path}")
    else:
        print("Failed to generate visualization. Check logs for details.")

def export_command(args):
    """Run the export command."""
    print("Exporting pattern statistics...")
    
    output_path = pattern_statistics.export_statistics(args.output)
    
    if output_path:
        print(f"Statistics exported to {output_path}")
    else:
        print("Failed to export statistics. Check logs for details.")

def warm_command(args):
    """Run the warm command."""
    recommendations = pattern_statistics.generate_cache_warming_recommendations()
    
    if not recommendations:
        print("No cache warming recommendations available.")
        return
    
    print(f"\n{'='*50}")
    print("CACHE WARMING RECOMMENDATIONS")
    print(f"{'='*50}")
    
    print(f"Found {len(recommendations)} patterns recommended for cache warming:")
    
    # Group by priority
    by_priority = {"high": [], "medium": [], "low": []}
    for rec in recommendations:
        by_priority[rec["priority"]].append(rec)
    
    for priority in ["high", "medium", "low"]:
        if by_priority[priority]:
            print(f"\n{priority.upper()} PRIORITY:")
            for i, rec in enumerate(by_priority[priority], 1):
                print(f"  {i}. {rec['pattern_id']} ({rec['language']}/{rec['type']})")
                print(f"     Reason: {rec['reason']}")
    
    # Save to file if specified
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(recommendations, f, indent=2)
            print(f"Cache warming recommendations saved to {args.output}")
        except Exception as e:
            print(f"Error saving cache warming recommendations: {str(e)}")

def pattern_command(args):
    """Run the pattern command."""
    # Convert pattern type string to enum
    try:
        pattern_type = PatternType(args.type)
    except ValueError:
        print(f"Invalid pattern type: {args.type}")
        print("Valid types are: " + ", ".join([pt.value for pt in PatternType]))
        return
    
    metrics = pattern_statistics.get_pattern_metrics(
        pattern_id=args.pattern_id,
        language=args.language,
        pattern_type=pattern_type
    )
    
    if not metrics:
        print(f"No statistics found for pattern '{args.pattern_id}' "
              f"({args.language}/{args.type})")
        return
    
    print(f"\n{'='*50}")
    print(f"PATTERN DETAILS: {args.pattern_id}")
    print(f"{'='*50}")
    
    print(f"Language: {metrics['language']}")
    print(f"Type: {metrics['pattern_type']}")
    print("\nExecution metrics:")
    print(f"  Executions: {metrics['executions']}")
    print(f"  Matches: {metrics['matches']}")
    print(f"  Hit ratio: {metrics['hit_ratio']:.2f}")
    print(f"  Average execution time: {metrics['avg_execution_time_ms']:.2f}ms")
    print(f"  Total execution time: {metrics['total_execution_time_ms']:.2f}ms")
    print(f"  Total compilation time: {metrics['total_compilation_time_ms']:.2f}ms")
    print(f"  Estimated memory usage: {metrics['estimated_memory_bytes']} bytes")
    print(f"  Value score: {metrics['value_score']:.2f}")
    
    # Show history if available
    if metrics['execution_times'] and len(metrics['execution_times']) > 1:
        print("\nExecution history (last 5):")
        for i in range(min(5, len(metrics['execution_times']))):
            idx = len(metrics['execution_times']) - i - 1
            print(f"  {datetime.fromtimestamp(metrics['timestamps'][idx]).strftime('%Y-%m-%d %H:%M:%S')}: "
                  f"{metrics['execution_times'][idx]:.2f}ms, {metrics['match_counts'][idx]} matches")

def main():
    """Main function."""
    args = parse_args()
    
    # Execute the appropriate command
    commands = {
        "analyze": analyze_command,
        "show": show_command,
        "recommendations": recommendations_command,
        "visualize": visualize_command,
        "export": export_command,
        "warm": warm_command,
        "pattern": pattern_command
    }
    
    if args.command in commands:
        commands[args.command](args)
    else:
        print(f"Unknown command: {args.command}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 