#!/usr/bin/env python3
"""
Error Handling Audit Tool

This script runs a comprehensive audit of exception handling practices 
across the RepoAnalyzer codebase, generating a detailed report with 
statistics and recommendations for standardization.
"""

import os
import sys
import asyncio
import argparse
import json
from datetime import datetime

# Add parent directory to path so we can import project modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from utils.error_handling import ErrorAudit, run_exception_audit
from utils.logger import log

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run an audit of exception handling across the codebase"
    )
    parser.add_argument(
        "--dir", 
        default=parent_dir,
        help="Root directory to analyze (default: project root)"
    )
    parser.add_argument(
        "--output", 
        default=None,
        help="Output file path for the report (default: auto-generated)"
    )
    parser.add_argument(
        "--format", 
        choices=["json", "text"], 
        default="json",
        help="Output format (default: json)"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose output"
    )
    return parser.parse_args()

def print_report_summary(report, output_path=None):
    """Print a human-readable summary of the audit report."""
    stats = report["statistics"]
    recommendations = report["recommendations"]
    
    print("\n" + "="*80)
    print(f"EXCEPTION HANDLING AUDIT REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")
    
    print(f"Total errors tracked: {stats.get('total_errors', 0)}")
    print(f"Unique error types: {stats.get('unique_error_types', 0)}")
    
    # Error types by count
    print("\nERROR TYPES:")
    error_counts = stats.get('error_counts_by_type', {})
    for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {error_type}: {count}")
    
    # Errors by category
    print("\nERROR CATEGORIES:")
    category_counts = stats.get('error_counts_by_category', {})
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count}")
    
    # Error handling coverage
    coverage = stats.get('error_handling_coverage', {})
    print("\nERROR HANDLING COVERAGE:")
    print(f"  Functions analyzed: {coverage.get('total_functions', 0)}")
    print(f"  Functions with standardized handling: {coverage.get('decorated_functions', 0)}")
    print(f"  Coverage percentage: {coverage.get('coverage_percentage', 0):.1f}%")
    
    # Top error locations
    print("\nTOP ERROR LOCATIONS:")
    locations = stats.get('top_error_locations', [])
    for location, count in locations:
        print(f"  {location}: {count} errors")
    
    # Raw try/except blocks
    print(f"\nRaw try/except blocks detected: {stats.get('raw_exception_handlers', 0)}")
    
    # Show recommendations
    print("\nRECOMMENDATIONS:")
    if not recommendations:
        print("  No recommendations found.")
    else:
        for i, rec in enumerate(recommendations[:10], 1):  # Show top 10
            print(f"  {i}. {rec['location']}")
            print(f"     Issue: {rec['issue']}")
            print(f"     Recommendation: {rec['recommendation']}")
            print(f"     Error count: {rec['error_count']}")
            print()
    
    print(f"\nTotal recommendations: {len(recommendations)}")
    if output_path:
        print(f"\nFull report saved to: {output_path}")
    print("="*80 + "\n")

async def main():
    """Run the exception handling audit."""
    args = parse_args()
    
    log(f"Starting exception handling audit of {args.dir}", level="info")
    
    try:
        # Analyze the codebase directly using ErrorAudit class methods
        log("Starting exception handling audit...", level="info")
        
        # Analyze the codebase for error handling patterns
        ErrorAudit.analyze_codebase(args.dir)
        
        # Generate the report
        report = ErrorAudit.get_error_report()
        recommendations = ErrorAudit.get_standardization_recommendations()
        
        # Save the report to a file (this is an async method)
        await ErrorAudit.save_report()
        
        # Log a summary
        log(
            f"Exception audit complete: found {report.get('total_errors', 0)} errors "
            f"across {report.get('unique_error_types', 0)} types with "
            f"{len(recommendations)} recommendations",
            level="info"
        )
        
        result = {
            "statistics": report,
            "recommendations": recommendations
        }
    except Exception as e:
        log(f"Error running exception audit: {e}", level="error")
        result = {
            "statistics": {},
            "recommendations": [],
            "error": str(e)
        }
    
    # Save the report
    output_path = args.output
    if not output_path:
        # Create reports directory if needed
        reports_dir = os.path.join(parent_dir, "reports", "errors")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Use timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(reports_dir, f"error_audit_{timestamp}.{args.format}")
    
    # Save report to file
    with open(output_path, 'w') as f:
        if args.format == "json":
            json.dump(result, f, indent=2)
        else:
            # Simple text format
            f.write(f"EXCEPTION HANDLING AUDIT REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Total errors tracked: {result['statistics'].get('total_errors', 0)}\n")
            f.write(f"Unique error types: {result['statistics'].get('unique_error_types', 0)}\n\n")
            
            f.write("RECOMMENDATIONS:\n")
            for i, rec in enumerate(result['recommendations'], 1):
                f.write(f"{i}. {rec['location']}\n")
                f.write(f"   Issue: {rec['issue']}\n")
                f.write(f"   Recommendation: {rec['recommendation']}\n")
                f.write(f"   Error count: {rec['error_count']}\n\n")
    
    log(f"Exception audit report saved to {output_path}", level="info")
    
    # Print summary to console
    if args.verbose or args.format == "text":
        print_report_summary(result, output_path)
    else:
        print(f"Exception audit complete. Report saved to: {output_path}")

if __name__ == "__main__":
    asyncio.run(main()) 