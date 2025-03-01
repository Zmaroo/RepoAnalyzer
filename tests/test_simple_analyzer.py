#!/usr/bin/env python3
"""
Simple Test Script to analyze the RepoAnalyzer project itself.

This script takes a more direct approach by using the individual components
of the RepoAnalyzer system rather than the main entry point.
"""

import os
import sys
import asyncio
from pathlib import Path

# Get the current project directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import the core components we need
from indexer.file_processor import FileProcessor
from indexer.unified_indexer import process_repository_indexing
from db.schema import drop_all_tables, create_all_tables
from db.neo4j_ops import create_schema_indexes_and_constraints, auto_reinvoke_projection_once
from db.upsert_ops import upsert_repository
from utils.logger import log
from ai_tools.ai_interface import ai_assistant

async def analyze_repo():
    """Analyze the repository directly using core components."""
    log("Starting simple analysis of the RepoAnalyzer project itself", level="info")
    
    try:
        # Initialize database schema
        log("Initializing database schema...", level="info")
        await drop_all_tables()
        await create_all_tables()
        create_schema_indexes_and_constraints()
        
        # Create repository record
        repo_name = os.path.basename(PROJECT_DIR)
        repo_id = await upsert_repository({
            'repo_name': repo_name,
            'repo_type': 'active',
            'source_url': None
        })
        log(f"Created repository record with ID: {repo_id}", level="info")
        
        # Process the repository
        log(f"Processing repository: {PROJECT_DIR}", level="info")
        result = await process_repository_indexing(PROJECT_DIR, repo_id)
        log(f"Repository processing result: {result}", level="info")
        
        # Generate graph projection
        log("Creating graph projection...", level="info")
        await auto_reinvoke_projection_once(repo_id)
        
        # Analyze code structure
        log("Analyzing code structure...", level="info")
        structure_result = await ai_assistant.analyze_code_structure(repo_id)
        log(f"Structure analysis complete with {len(structure_result)} metrics", level="info")
        
        # Search for key components
        log("Searching for key components...", level="info")
        search_results = await ai_assistant.search_code_snippets("file_processor", repo_id)
        log(f"Found {len(search_results)} relevant code snippets", level="info")
        
        log("Analysis completed successfully!", level="info")
        
    except Exception as e:
        log(f"Error during analysis: {e}", level="error")
        import traceback
        log(traceback.format_exc(), level="error")

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