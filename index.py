#!/usr/bin/env python
"""
Improved Repository Indexing Entry Point with Automated Graph Projection Re‑invocation

This module coordinates repository indexing and analysis using a modern,
asyncio‑driven structure. It supports:
  - Active repository indexing (defaulting to the current working directory)
  - Cloning and indexing a reference repository via a GitHub URL (--clone-ref)
  - Documentation operations (e.g. sharing, searching)
  - Watch mode: files are monitored and changes are reindexed continuously
  - Reference repository learning: learn patterns from reference repositories
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
    QueryResult
)
from parsers.feature_extractor import (
    BaseFeatureExtractor,
    TreeSitterFeatureExtractor,
    CustomFeatureExtractor
)

# Use the new consolidated module for schema initialization.
from db.neo4j_ops import (
    create_schema_indexes_and_constraints,
    auto_reinvoke_projection_once
)
from db.psql import close_db_pool, query, init_db_pool  # Asynchronous cleanup method.
from db.schema import create_all_tables, drop_all_tables
from indexer.unified_indexer import process_repository_indexing
from db.upsert_ops import upsert_repository, share_docs_with_repo
from embedding.embedding_models import code_embedder, doc_embedder  # Use global instances
from semantic.search import (  # Updated import path
    search_code,
    search_docs,
    search_engine
)
# TODO: Implement AI tools before enabling these imports
# from ai_tools.graph_capabilities import graph_analysis
# from ai_tools.ai_interface import AIAssistant
from watcher.file_watcher import watch_directory
from utils.error_handling import handle_async_errors, ErrorBoundary, handle_errors
from utils.app_init import register_shutdown_handler, _initialize_components
from utils.async_runner import submit_async_task, cleanup_tasks

# TODO: Implement AI Assistant before enabling
# ai_assistant = AIAssistant()

# ------------------------------------------------------------------
# Asynchronous tasks delegating major responsibilities.
# ------------------------------------------------------------------

@handle_async_errors
async def process_share_docs(share_docs_arg: str):
    """
    Shares documentation based on input argument.
    Expected format: "doc_id1,doc_id2:target_repo_id"
    """
    with ErrorBoundary("sharing documentation"):
        doc_ids_str, target_repo = share_docs_arg.split(":")
        doc_ids = [int(doc_id.strip()) for doc_id in doc_ids_str.split(",")]
        result = await share_docs_with_repo(doc_ids, int(target_repo))
        log(f"Sharing docs result: {result}", level="info")

@handle_async_errors
async def handle_file_change(file_path: str, repo_id: int):
    log(f"File changed: {file_path}", level="info")
    await process_repository_indexing(file_path, repo_id, single_file=True)
    await auto_reinvoke_projection_once(repo_id)
    # TODO: Implement graph analysis before enabling
    # await graph_analysis.analyze_code_structure(repo_id)

# TODO: Implement AI Assistant before enabling
# @handle_async_errors
# async def learn_from_reference_repo(reference_repo_id: int, active_repo_id: int = None):
#     """
#     Learn patterns from a reference repository and optionally apply them to an active repo.
#     """
#     with ErrorBoundary("learning from reference repository"):
#         # Add support for deep learning from multiple repositories
#         if isinstance(reference_repo_id, list):
#             learn_result = await ai_assistant.deep_learn_from_multiple_repositories(reference_repo_id)
#         else:
#             # Learn from single reference repository
#             learn_result = await ai_assistant.learn_from_reference_repo(reference_repo_id)
#         
#         log(f"Learned patterns from reference repo: {learn_result}", level="info")
#         
#         # Apply patterns to active repository if specified
#         if active_repo_id:
#             apply_result = await ai_assistant.apply_reference_patterns(reference_repo_id, active_repo_id)
#             log(f"Applied patterns to active repo: {apply_result}", level="info")
#             return apply_result
#         return learn_result

# ------------------------------------------------------------------
# Main async routine assembling tasks (indexing, sharing, searching).
# ------------------------------------------------------------------

@handle_async_errors
async def main_async(args):
    """Main async coordinator for indexing, documentation operations, and watch mode."""
    try:
        # Initialize application components including database pools
        await _initialize_components()
        
        if args.clean:
            log("Cleaning databases and reinitializing schema...", level="info")
            await drop_all_tables()
            await create_all_tables()
            await create_schema_indexes_and_constraints()
            
        repo_path = args.index if args.index else os.getcwd()
        repo_name = os.path.basename(os.path.abspath(repo_path))
        
        # [0.2] Repository Setup
        repo_id = await upsert_repository({
            'repo_name': repo_name,
            'repo_type': 'active',
            'source_url': args.clone_ref
        })
        
        # Store reference repository if provided
        reference_repo_id = None
        reference_repo_ids = []
        
        # Handle single reference repository
        if args.learn_ref:
            reference_repo = os.path.basename(os.path.abspath(args.learn_ref))
            reference_repo_id = await upsert_repository({
                'repo_name': reference_repo,
                'repo_type': 'reference',
                'active_repo_id': repo_id,
                'source_url': args.learn_ref if '://' in args.learn_ref else None
            })
            reference_repo_ids.append(reference_repo_id)
        
        # Handle multiple reference repositories
        if args.multi_ref:
            multi_refs = args.multi_ref.split(',')
            for ref in multi_refs:
                ref = ref.strip()
                # Check if it's a repository ID
                if ref.isdigit():
                    reference_repo_ids.append(int(ref))
                else:
                    # It's a path or URL
                    ref_name = os.path.basename(os.path.abspath(ref))
                    ref_id = await upsert_repository({
                        'repo_name': ref_name,
                        'repo_type': 'reference',
                        'active_repo_id': repo_id,
                        'source_url': ref if '://' in ref else None
                    })
                    reference_repo_ids.append(ref_id)
        
        # [0.3] Processing Tasks
        futures = []
        # Core indexing using UnifiedIndexer [1.0]
        futures.append(submit_async_task(process_repository_indexing(repo_path, repo_id)))
        
        # Index reference repository if provided
        if args.learn_ref:
            futures.append(submit_async_task(process_repository_indexing(args.learn_ref, reference_repo_id)))
        
        # Index multiple reference repositories
        if args.multi_ref:
            multi_refs = args.multi_ref.split(',')
            for i, ref in enumerate(multi_refs):
                ref = ref.strip()
                if not ref.isdigit():  # Only process paths, not repository IDs
                    futures.append(submit_async_task(process_repository_indexing(ref, reference_repo_ids[i])))
        
        # Documentation operations
        if args.share_docs:
            futures.append(submit_async_task(process_share_docs(args.share_docs)))
        if args.search_docs:
            # Uses SearchEngine [5.0]
            results = await search_docs(args.search_docs, repo_id=repo_id)
            log(f"Doc search results: {results}", level="info")

        # Wait for all futures to complete
        if futures:
            await asyncio.gather(*[f.result() for f in futures], return_exceptions=True)
        
        # TODO: Implement AI Assistant before enabling reference repository learning
        # Reference repository learning
        # if args.deep_learning and len(reference_repo_ids) >= 2:
        #     # Deep learning from multiple reference repositories
        #     log(f"Starting deep learning from {len(reference_repo_ids)} reference repositories", level="info")
        #     deep_learning_result = await ai_assistant.deep_learn_from_multiple_repositories(reference_repo_ids)
        #     
        #     if args.apply_ref_patterns:
        #         # Apply patterns from all reference repositories to the active repo
        #         await ai_assistant.apply_cross_repository_patterns(repo_id, reference_repo_ids)
        #         
        #     log(f"Deep learning complete: {deep_learning_result}", level="info")
        # elif reference_repo_id or reference_repo_ids:
        #     # Regular learning from a single reference repository
        #     repo_to_learn = reference_repo_id or reference_repo_ids[0]
        #     await learn_from_reference_repo(repo_to_learn, repo_id if args.apply_ref_patterns else None)
        
        # [0.4] Watch Mode
        if args.watch:
            log("Watch mode enabled: Starting file watcher...", level="info")
            
            # The watcher receives an on_change callback
            watcher_future = submit_async_task(watch_directory(repo_path, repo_id, on_change=handle_file_change))
            await watcher_future
        else:
            # One-time graph analysis
            log("Invoking graph projection once after indexing.", level="info")
            await auto_reinvoke_projection_once(repo_id)
            # TODO: Implement graph analysis before enabling
            # await graph_analysis.analyze_code_structure(repo_id)
    except asyncio.CancelledError:
        log("Indexing was cancelled.", level="info")
        raise
    except Exception as e:
        log(f"Unexpected error: {e}", level="error")
    finally:
        # Cleanup database connections
        await close_db_pool()
        from db.connection import driver
        await driver.close()
        log("Cleanup complete.", level="info")

async def cleanup():
    """Clean up resources before exiting."""
    from db.connection import driver
    await driver.close()
    log("Cleanup complete.", level="info")

@handle_async_errors(error_types=(Exception,))
async def main():
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
    parser.add_argument("--learn-ref", type=str,
                        help="Learn patterns from a reference repository (path or URL)")
    parser.add_argument("--multi-ref", type=str, 
                        help="Learn from multiple reference repositories (comma-separated paths or repository IDs)")
    parser.add_argument("--apply-ref-patterns", action="store_true",
                        help="Apply learned patterns from reference repo to the active repo")
    parser.add_argument("--deep-learning", action="store_true",
                        help="Use deep learning across multiple repositories (requires --multi-ref)")
    
    args = parser.parse_args()
    
    try:
        await main_async(args)
    except KeyboardInterrupt:
        log("KeyboardInterrupt caught – shutting down.", level="warning")
        sys.exit(0)
    except Exception as e:
        log(f"Fatal error in main process: {e}", level="error")
        sys.exit(1)

if __name__ == "__main__":
    # Register cleanup handlers before starting
    from utils.app_init import register_shutdown_handler
    from utils.async_runner import cleanup_tasks
    from db.psql import close_db_pool
    from db.connection import driver
    
    register_shutdown_handler(cleanup_tasks)  # Should be first to ensure tasks are cleaned up
    register_shutdown_handler(close_db_pool)
    register_shutdown_handler(driver.close)
    
    asyncio.run(main()) 