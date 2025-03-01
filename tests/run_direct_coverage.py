#!/usr/bin/env python3
"""
Direct Coverage Runner for RepoAnalyzer

This script runs coverage directly on a specified script without pytest.
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
    """Ensure coverage is installed."""
    try:
        import coverage
        print("Coverage tools already installed.")
    except ImportError:
        print("Installing coverage...")
        subprocess.run([sys.executable, "-m", "pip", "install", "coverage"], check=True)

def main():
    parser = argparse.ArgumentParser(description="Run direct coverage on a script")
    parser.add_argument("--script", type=str, default="test_system.py",
                        help="Script to run with coverage")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--xml", action="store_true", help="Generate XML coverage report")
    parser.add_argument("--args", type=str, help="Arguments to pass to the script")
    args = parser.parse_args()
    
    # Ensure we have coverage tools
    ensure_coverage_installed()
    
    # Prepare output directory
    reports_dir = Path("test_reports")
    reports_dir.mkdir(exist_ok=True)
    
    # Build commands
    # First run coverage to collect data
    cmd = ["coverage", "run", "--source=indexer,parsers,db,utils,embedding,semantic,ai_tools,watcher,analytics"]
    
    # Add the script to run with coverage
    cmd.append(args.script)
    
    # Add any script arguments
    if args.args:
        cmd.extend(args.args.split())
    
    # Run the coverage collection
    result = run_command(cmd)
    
    if result != 0:
        print(f"\n❌ Script {args.script} failed with exit code {result}")
        return result
    
    # Generate reports after successful run
    report_cmds = []
    
    # Always generate terminal report
    report_cmds.append(["coverage", "report"])
    
    if args.html:
        html_dir = reports_dir / "htmlcov"
        report_cmds.append(["coverage", "html", f"--directory={html_dir}"])
    
    if args.xml:
        xml_path = reports_dir / "coverage.xml"
        report_cmds.append(["coverage", "xml", f"-o={xml_path}"])
    
    # Run all report commands
    for cmd in report_cmds:
        run_command(cmd)
    
    print("\n✅ Coverage analysis completed.")
    if args.html:
        print(f"\nHTML coverage report generated at: {reports_dir}/htmlcov/index.html")
    if args.xml:
        print(f"\nXML coverage report generated at: {reports_dir}/coverage.xml")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 