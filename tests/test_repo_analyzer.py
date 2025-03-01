#!/usr/bin/env python3
"""
Test script to analyze the RepoAnalyzer project itself.

This script uses the RepoAnalyzer's own functionality to analyze its own codebase,
demonstrating the tool's capabilities on a real-world Python project.
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path

# Get the current project directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import the RepoAnalyzer components
from index import main_async
from utils.logger import log
from db.schema import drop_all_tables, create_all_tables
from db.neo4j_ops import create_schema_indexes_and_constraints
from db.psql import close_db_pool

class Args:
    """Mock args for main_async."""
    
    def __init__(self):
        self.clean = True  # Start with clean database
        self.index = PROJECT_DIR  # Analyze this project
        self.clone_ref = None
        self.share_docs = None
        self.search_docs = None
        self.watch = False
        self.learn_ref = None
        self.multi_ref = None
        self.apply_ref_patterns = False
        self.deep_learning = False

async def analyze_repo():
    """Run the analyzer on the RepoAnalyzer project itself."""
    log("Starting analysis of the RepoAnalyzer project itself", level="info")
    
    try:
        # Create args object
        args = Args()
        
        # Run the main async function
        await main_async(args)
        
        log("Analysis completed successfully!", level="info")
    except Exception as e:
        log(f"Error during analysis: {e}", level="error")
    finally:
        # Ensure database connection is closed
        await close_db_pool()

def main():
    """Main entry point."""
    try:
        asyncio.run(analyze_repo())
    except KeyboardInterrupt:
        log("Analysis interrupted by user", level="warning")
        sys.exit(0)
    except Exception as e:
        log(f"Fatal error: {e}", level="error")
        sys.exit(1)

if __name__ == "__main__":
    main() 