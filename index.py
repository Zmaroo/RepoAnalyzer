#!/usr/bin/env python
"""
Improved Repository Indexing Entry Point with Automated Graph Projection Re‑invocation

This module coordinates repository indexing and analysis using a modern,
asyncio‑driven structure. It supports:
  - Active repository indexing (defaulting to the current working directory)
  - Cloning and indexing a reference repository via a GitHub URL (--clone-ref)
  - Documentation operations (e.g. sharing, searching)
  - Watch mode: files are monitored and changes are reindexed continuously
"""

import argparse
import asyncio
import os
import signal
import sys
from utils.logger import log  # Use our central logger
from parsers.types import (
    ParserResult,
    FileType,
    ParserType,
    Documentation,
    ComplexityMetrics,
    ExtractedFeatures
)
from parsers.models import (
    FileMetadata,
    FileClassification,
    LanguageFeatures,
    PatternMatch,
    PatternDefinition,
    QueryPattern,
    QueryResult,
    FeatureExtractor
)

# Use the new consolidated module for schema initialization.
from db.neo4j_ops import (
    create_schema_indexes_and_constraints,
    auto_reinvoke_projection_once
)
from db.psql import close_db_pool, query  # Asynchronous cleanup method.
from db.schema import create_all_tables, drop_all_tables
from indexer.unified_indexer import process_repository_indexing
from db.upsert_ops import upsert_repository, share_docs_with_repo
from embedding.embedding_models import code_embedder, doc_embedder  # Use global instances
from semantic.search import (  # Updated import path
    search_code,
    search_docs,
    search_engine
)
from ai_tools.graph_capabilities import graph_analysis  # Add graph analysis
from watcher.file_watcher import watch_directory

# ------------------------------------------------------------------
# Asynchronous tasks delegating major responsibilities.
# ------------------------------------------------------------------

async def process_share_docs(share_docs_arg: str):
    """
    Shares documentation based on input argument.
    Expected format: "doc_id1,doc_id2:target_repo_id"
    """
    try:
        doc_ids_str, target_repo = share_docs_arg.split(":")
        doc_ids = [int(doc_id.strip()) for doc_id in doc_ids_str.split(",")]
        result = await share_docs_with_repo(doc_ids, int(target_repo))
        log(f"Sharing docs result: {result}", level="info")
    except Exception as e:
        log(f"Error sharing docs: {e}", level="error")

async def handle_file_change(file_path: str, repo_id: int):
    log(f"File changed: {file_path}", level="info")
    await process_repository_indexing(file_path, repo_id, single_file=True)
    await graph_analysis.analyze_code_structure(repo_id)

# ------------------------------------------------------------------
# Main async routine assembling tasks (indexing, sharing, searching).
# ------------------------------------------------------------------

async def main_async(args):
    """Main async coordinator for indexing, documentation operations, and watch mode."""
    try:
        if args.clean:
            log("Cleaning databases and reinitializing schema...", level="info")
            await drop_all_tables()
            await create_all_tables()
            create_schema_indexes_and_constraints()
            
        repo_path = args.index if args.index else os.getcwd()
        repo_name = os.path.basename(os.path.abspath(repo_path))
        
        # [0.2] Repository Setup
        repo_id = await upsert_repository({
            'repo_name': repo_name,
            'repo_type': 'active',
            'source_url': args.clone_ref
        })
        
        # [0.3] Processing Tasks
        tasks = []
        # Core indexing using UnifiedIndexer [1.0]
        tasks.append(process_repository_indexing(repo_path, repo_id))
        
        # Documentation operations
        if args.share_docs:
            tasks.append(process_share_docs(args.share_docs))
        if args.search_docs:
            # Uses SearchEngine [5.0]
            results = await search_docs(args.search_docs, repo_id=repo_id)
            log(f"Doc search results: {results}", level="info")

        # Run primary tasks concurrently and tolerate individual failures
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # [0.4] Watch Mode
        if args.watch:
            log("Watch mode enabled: Starting file watcher...", level="info")
            
            # The watcher receives an on_change callback
            watcher_task = asyncio.create_task(watch_directory(repo_path, repo_id, on_change=handle_file_change))
            await watcher_task
        else:
            # One-time graph analysis
            log("Invoking graph projection once after indexing.", level="info")
            auto_reinvoke_projection_once()
            await graph_analysis.analyze_code_structure(repo_id)
    except asyncio.CancelledError:
        log("Indexing was cancelled.", level="info")
        raise
    except Exception as e:
        log(f"Unexpected error: {e}", level="error")
    finally:
        await close_db_pool()
        log("Cleanup complete.", level="info")

def main():
    """CLI entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="Repository indexing and analysis tool.")
    parser.add_argument("--clean", action="store_true",
                        help="Clean and reinitialize databases before starting")
    parser.add_argument("--index", nargs="?", type=str,
                        help="Local repository path to index. Defaults to current directory.",
                        default=os.getcwd(), const=os.getcwd())
    parser.add_argument("--clone-ref", type=str,
                        help="Clone and index a reference repository from GitHub (provide Git URL)")
    parser.add_argument("--share-docs", type=str,
                        help="Share docs in format 'doc_id1,doc_id2:target_repo_id'")
    parser.add_argument("--search-docs", type=str,
                        help="Search for documentation by term")
    parser.add_argument("--watch", action="store_true",
                        help="Watch for file changes and continuously update graph projection")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        log("KeyboardInterrupt caught – shutting down.", level="warning")
        sys.exit(0)

if __name__ == "__main__":
    main() 