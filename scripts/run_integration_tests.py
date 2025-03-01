#!/usr/bin/env python3
"""
Run Integration Tests for the RepoAnalyzer

This script runs all integration tests for the RepoAnalyzer project.
It discovers all test files matching the pattern test_integration_*.py
and runs them individually, collecting the results.

Usage:
    python scripts/run_integration_tests.py [module_name]

    If a module name is provided, only integration tests for that module will be run.
    For example: python scripts/run_integration_tests.py indexer
"""

import os
import sys
import glob
import subprocess
import time
import argparse
from typing import List, Dict, Any, Optional

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log

# Define test discovery patterns for integration tests
INTEGRATION_TEST_PATTERN = 'test_integration_*.py'


def find_test_files(module: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Find test files based on patterns.
    
    Args:
        module: Optional module name to filter tests
        
    Returns:
        Dictionary with module names and their test files
    """
    test_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests')
    
    integration_tests = glob.glob(os.path.join(test_dir, INTEGRATION_TEST_PATTERN))
    
    # Organize tests by module
    test_files = {}
    
    for test_file in integration_tests:
        basename = os.path.basename(test_file)
        # Extract module name from test filename (e.g., test_integration_indexer.py -> indexer)
        parts = basename.split('_')
        if len(parts) > 2:
            module_name = parts[2].split('.')[0]  # Get module name without .py extension
            
            # Filter by module if specified
            if module and module != module_name:
                continue
                
            if module_name not in test_files:
                test_files[module_name] = []
            
            test_files[module_name].append(test_file)
    
    return test_files


def run_test(test_file: str) -> bool:
    """
    Run a single test file and return if it was successful.
    
    Args:
        test_file: Path to the test file
        
    Returns:
        True if the test passed, False otherwise
    """
    log(f"Running test: {os.path.basename(test_file)}", level="info")
    
    result = subprocess.run(
        [sys.executable, test_file],
        capture_output=True,
        text=True
    )
    
    # Output the test results
    if result.stdout:
        log(result.stdout, level="info")
    
    if result.stderr:
        log(result.stderr, level="warning")
    
    return result.returncode == 0


def main():
    """Run all integration tests."""
    parser = argparse.ArgumentParser(description="Run integration tests for RepoAnalyzer")
    parser.add_argument('module', nargs='?', help="Optional module name to test (e.g., 'indexer')")
    args = parser.parse_args()
    
    log(f"Running integration tests for RepoAnalyzer{'s ' + args.module + ' module' if args.module else ''}", level="info")
    
    test_files = find_test_files(args.module)
    
    if not test_files:
        if args.module:
            log(f"No integration tests found for module: {args.module}", level="warning")
        else:
            log("No integration tests found", level="warning")
        return
    
    # Test results by module
    results = {}
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    skipped_tests = 0
    start_time = time.time()
    
    # Run tests for each module
    for module, files in test_files.items():
        results[module] = {
            "total": len(files),
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "files": {}
        }
        
        log(f"Running integration tests for module: {module}", level="info")
        
        for test_file in files:
            try:
                success = run_test(test_file)
                
                result_status = "SUCCESS" if success else "FAILED"
                results[module]["files"][test_file] = result_status
                
                if success:
                    results[module]["passed"] += 1
                    passed_tests += 1
                else:
                    results[module]["failed"] += 1
                    failed_tests += 1
                
                total_tests += 1
                
                log(f"Test {os.path.basename(test_file)}: {result_status}", level="info")
                
            except Exception as e:
                log(f"Error running test {test_file}: {str(e)}", level="error")
                results[module]["skipped"] += 1
                skipped_tests += 1
    
    # Print summary
    end_time = time.time()
    duration = end_time - start_time
    
    log("\n" + "=" * 60, level="info")
    log(f"INTEGRATION TEST SUMMARY", level="info")
    log("=" * 60, level="info")
    log(f"Total time: {duration:.2f} seconds", level="info")
    log(f"Total tests: {total_tests}", level="info")
    log(f"Passed: {passed_tests}", level="info")
    log(f"Failed: {failed_tests}", level="info")
    log(f"Skipped: {skipped_tests}", level="info")
    log("=" * 60, level="info")
    
    # Print results by module
    log("Results by module:", level="info")
    for module, result in results.items():
        status = "SUCCESS" if result["failed"] == 0 else "FAILED"
        log(f"  {module}: {status} ({result['passed']}/{result['total']} passed)", level="info")
    
    log("=" * 60, level="info")
    
    # Return non-zero exit code if any tests failed
    if failed_tests > 0:
        sys.exit(1)


if __name__ == "__main__":
    main() 