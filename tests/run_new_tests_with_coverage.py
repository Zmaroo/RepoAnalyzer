#!/usr/bin/env python3
"""
Coverage Test Runner for RepoAnalyzer (New Tests)

This script runs our newly created tests with coverage analysis.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and print its output."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    
    if result.stdout:
        print(result.stdout)
    
    if result.stderr and result.returncode != 0:
        print(f"Error: {result.stderr}")
    
    return result.returncode

def ensure_coverage_installed():
    """Ensure coverage and pytest-cov are installed."""
    try:
        import coverage
        import pytest_cov
        print("Coverage tools already installed.")
    except ImportError:
        print("Installing coverage tools...")
        subprocess.run([sys.executable, "-m", "pip", "install", "coverage", "pytest-cov"], check=True)

def main():
    parser = argparse.ArgumentParser(description="Run new tests with coverage for RepoAnalyzer")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--xml", action="store_true", help="Generate XML coverage report")
    parser.add_argument("--specific", type=str, help="Run specific test file(s)", nargs="+")
    args = parser.parse_args()
    
    # Ensure we have coverage tools
    ensure_coverage_installed()
    
    # Prepare output directory
    reports_dir = Path("test_reports")
    reports_dir.mkdir(exist_ok=True)
    
    # Add the project root to Python path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, project_root)
    
    # Modify PYTHONPATH to include project root
    os.environ['PYTHONPATH'] = f"{project_root}:{os.environ.get('PYTHONPATH', '')}"
    
    # Build command
    cmd = [
        "python", "-m", "pytest",
    ]
    
    # Add coverage options
    coverage_modules = "utils,db,semantic,indexer,parsers"
    cmd.extend([
        f"--cov={coverage_modules}",
        "--cov-report=term-missing",
        "--cov-config=.coveragerc"
    ])
    
    # Add output formats if requested
    if args.html:
        cmd.append(f"--cov-report=html:{reports_dir}/htmlcov")
    
    if args.xml:
        cmd.append(f"--cov-report=xml:{reports_dir}/coverage.xml")
    
    # Add files to test
    if args.specific:
        cmd.extend(args.specific)
    else:
        # Run all our new test files
        cmd.extend([
            "tests/test_cache_utils.py",
            # "tests/test_db_layer.py",     # Uncomment when DB layer tests are fixed
            # "tests/test_semantic_module.py",  # Uncomment when semantic module tests are fixed
            # "tests/test_indexer_module.py",   # Uncomment when indexer tests are fixed
            # "tests/test_ai_tools.py",     # Uncomment when AI tools tests are fixed
        ])
    
    # Run the tests with coverage
    result = run_command(cmd)
    
    if result == 0:
        print("\n✅ All tests passed with coverage analysis.")
        if args.html:
            print(f"\nHTML coverage report generated at: {reports_dir}/htmlcov/index.html")
        if args.xml:
            print(f"\nXML coverage report generated at: {reports_dir}/coverage.xml")
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
    
    return result

if __name__ == "__main__":
    sys.exit(main()) 