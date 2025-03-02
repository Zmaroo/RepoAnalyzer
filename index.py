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
import aiohttp
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Set, Tuple
from utils.logger import log
from parsers.types import ParserResult, FileType, ParserType, Documentation, ComplexityMetrics, ExtractedFeatures
from parsers.models import FileMetadata, FileClassification, LanguageFeatures, PatternMatch, PatternDefinition, QueryPattern, QueryResult
from parsers.feature_extractor import BaseFeatureExtractor, TreeSitterFeatureExtractor, CustomFeatureExtractor
from db.neo4j_ops import create_schema_indexes_and_constraints, auto_reinvoke_projection_once
from db.psql import close_db_pool, query, init_db_pool
from db.schema import create_all_tables, drop_all_tables
from indexer.unified_indexer import process_repository_indexing
from db.upsert_ops import upsert_repository, share_docs_with_repo
from embedding.embedding_models import code_embedder, doc_embedder
from semantic.search import search_code, search_docs, search_engine
from ai_tools.graph_capabilities import graph_analysis
from ai_tools.ai_interface import AIAssistant
from watcher.file_watcher import watch_directory
from utils.error_handling import handle_async_errors, ErrorBoundary, handle_errors, AsyncErrorBoundary
from utils.app_init import initialize_application
import concurrent.futures
ai_assistant = AIAssistant()


@handle_async_errors
async def process_share_docs(share_docs_arg: str):
    """
    Shares documentation based on input argument.
    Expected format: "doc_id1,doc_id2:target_repo_id"
    """
    with AsyncErrorBoundary(operation_name='sharing documentation'):
        doc_ids_str, target_repo = share_docs_arg.split(':')
        doc_ids = [int(doc_id.strip()) for doc_id in doc_ids_str.split(',')]
        result = await share_docs_with_repo(doc_ids, int(target_repo))
        log(f'Sharing docs result: {result}', level='info')


@handle_async_errors
async def handle_file_change(file_path: str, repo_id: int):
    log(f'File changed: {file_path}', level='info')
    await process_repository_indexing(file_path, repo_id, single_file=True)
    await auto_reinvoke_projection_once(repo_id)
    await graph_analysis.analyze_code_structure(repo_id)


@handle_async_errors
async def learn_from_reference_repo(reference_repo_id: int, active_repo_id:
    int=None):
    """
    Learn patterns from a reference repository and optionally apply them to an active repo.
    """
    with AsyncErrorBoundary(operation_name='learning from reference repository'
        ):
        if isinstance(reference_repo_id, list):
            learn_result = (await ai_assistant.
                deep_learn_from_multiple_repositories(reference_repo_id))
        else:
            learn_result = await ai_assistant.learn_from_reference_repo(
                reference_repo_id)
        log(f'Learned patterns from reference repo: {learn_result}', level=
            'info')
        if active_repo_id:
            apply_result = await ai_assistant.apply_reference_patterns(
                reference_repo_id, active_repo_id)
            log(f'Applied patterns to active repo: {apply_result}', level=
                'info')
            return apply_result
        return learn_result


@handle_async_errors
async def handle_shutdown(loop=None):
    """Handle graceful shutdown of the application."""
    log('Initiating graceful shutdown...', level='info')
    try:
        await close_db_pool()
        log('Database pool closed', level='info')
    except Exception as e:
        log(f'Error during database pool cleanup: {e}', level='error')
    try:
        ai_assistant.close()
        log('AI Assistant closed', level='info')
    except Exception as e:
        log(f'Error closing AI Assistant: {e}', level='error')
    for task in asyncio.all_tasks(loop=loop):
        if task is not asyncio.current_task(loop=loop):
            task.cancel()
    log('Shutdown complete', level='info')
    if loop:
        loop.stop()


@handle_async_errors
async def main_async(args):
    """Main async coordinator for indexing, documentation operations, and watch mode."""
    try:
        await init_db_pool()
        if args.clean:
            log('Cleaning databases and reinitializing schema...', level='info'
                )
            await drop_all_tables()
            await create_all_tables()
            create_schema_indexes_and_constraints()
        repo_path = args.index if args.index else os.getcwd()
        repo_name = os.path.basename(os.path.abspath(repo_path))
        repo_id = await upsert_repository({'repo_name': repo_name,
            'repo_type': 'active', 'source_url': args.clone_ref})
        reference_repo_id = None
        reference_repo_ids = []
        if args.learn_ref:
            reference_repo = os.path.basename(os.path.abspath(args.learn_ref))
            reference_repo_id = await upsert_repository({'repo_name':
                reference_repo, 'repo_type': 'reference', 'active_repo_id':
                repo_id, 'source_url': args.learn_ref if '://' in args.
                learn_ref else None})
            reference_repo_ids.append(reference_repo_id)
        if args.multi_ref:
            multi_refs = args.multi_ref.split(',')
            for ref in multi_refs:
                ref = ref.strip()
                if ref.isdigit():
                    reference_repo_ids.append(int(ref))
                else:
                    ref_name = os.path.basename(os.path.abspath(ref))
                    ref_id = await upsert_repository({'repo_name': ref_name,
                        'repo_type': 'reference', 'active_repo_id': repo_id,
                        'source_url': ref if '://' in ref else None})
                    reference_repo_ids.append(ref_id)
        tasks = []
        tasks.append(process_repository_indexing(repo_path, repo_id))
        if args.learn_ref:
            tasks.append(process_repository_indexing(args.learn_ref,
                reference_repo_id))
        if args.multi_ref:
            multi_refs = args.multi_ref.split(',')
            for i, ref in enumerate(multi_refs):
                ref = ref.strip()
                if not ref.isdigit():
                    tasks.append(process_repository_indexing(ref,
                        reference_repo_ids[i]))
        if args.share_docs:
            tasks.append(process_share_docs(args.share_docs))
        if args.search_docs:
            results = await search_docs(args.search_docs, repo_id=repo_id)
            log(f'Doc search results: {results}', level='info')
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if args.deep_learning and len(reference_repo_ids) >= 2:
            log(f'Starting deep learning from {len(reference_repo_ids)} reference repositories'
                , level='info')
            deep_learning_result = (await ai_assistant.
                deep_learn_from_multiple_repositories(reference_repo_ids))
            if args.apply_ref_patterns:
                await ai_assistant.apply_cross_repository_patterns(repo_id,
                    reference_repo_ids)
            log(f'Deep learning complete: {deep_learning_result}', level='info'
                )
        elif reference_repo_id or reference_repo_ids:
            repo_to_learn = reference_repo_id or reference_repo_ids[0]
            await learn_from_reference_repo(repo_to_learn, repo_id if args.
                apply_ref_patterns else None)
        if args.watch:
            log('Watch mode enabled: Starting file watcher...', level='info')
            watcher_task = asyncio.create_task(watch_directory(repo_path,
                repo_id, on_change=handle_file_change))
            await watcher_task
        else:
            log('Invoking graph projection once after indexing.', level='info')
            await auto_reinvoke_projection_once(repo_id)
            await graph_analysis.analyze_code_structure(repo_id)
    except asyncio.CancelledError:
        log('Indexing was cancelled.', level='info')
        raise
    except Exception as e:
        log(f'Unexpected error: {e}', level='error')
    finally:
        await close_db_pool()
        ai_assistant.close()
        log('Cleanup complete.', level='info')


@handle_errors(error_types=(Exception,))
def main():
    """CLI entry point with argument parsing."""
    parser = argparse.ArgumentParser(description=
        'Repository indexing and analysis tool.')
    parser.add_argument('--clean', action='store_true', help=
        'Clean and reinitialize databases before starting')
    parser.add_argument('--index', nargs='?', type=str, help=
        'Local repository path to index. Defaults to current directory.',
        default=os.getcwd(), const=os.getcwd())
    parser.add_argument('--clone-ref', type=str, help=
        'Clone and index a reference repository from GitHub (provide Git URL)')
    parser.add_argument('--share-docs', type=str, help=
        'Share documents with target repository (format: doc_id1,doc_id2:target_repo_id)'
        )
    parser.add_argument('--search-docs', type=str, help=
        'Search for documentation by query string')
    parser.add_argument('--learn-ref', type=str, help=
        'Learn patterns from a reference repository (provide path)')
    parser.add_argument('--apply-ref-patterns', action='store_true', help=
        'Apply reference patterns to active repository')
    parser.add_argument('--deep-learning', action='store_true', help=
        'Enable deep learning from multiple reference repositories')
    parser.add_argument('--watch', action='store_true', help=
        'Watch for file changes and reindex')
    parser.add_argument('--multi-ref', type=str, help=
        'Comma-separated list of reference repositories to use (paths or repo IDs)'
        )
    args = parser.parse_args()
    if not initialize_application():
        log('Failed to initialize application', level='error')
        sys.exit(1)
    try:
        loop = asyncio.get_event_loop()
        for sig_name in ('SIGINT', 'SIGTERM'):
            if hasattr(signal, sig_name):
                loop.add_signal_handler(getattr(signal, sig_name), lambda :
                    asyncio.create_task(_handle_shutdown_wrapper(loop)))
        loop.run_until_complete(main_async(args))
    except KeyboardInterrupt:
        log('Operation interrupted by user.', level='info')
        loop.run_until_complete(asyncio.wait_for(handle_shutdown(loop),
            timeout=10))
    except Exception as e:
        log(f'Error: {e}', level='error')
        sys.exit(1)


@handle_errors(error_types=(Exception,))
def _handle_shutdown_wrapper(loop):
    """Wrapper to handle async shutdown with a timeout to prevent hanging."""
    try:
        shutdown_task = asyncio.create_task(handle_shutdown(loop))
        future = asyncio.run_coroutine_threadsafe(asyncio.wait_for(
            shutdown_task, timeout=10), loop)
        future.result(timeout=1)
        log('Shutdown initiated', level='debug')
    except (asyncio.TimeoutError, concurrent.futures.TimeoutError):
        log('Shutdown timed out, forcing exit', level='warning')
        sys.exit(1)
    except Exception as e:
        log(f'Error in shutdown wrapper: {e}', level='error')
        sys.exit(1)


if __name__ == '__main__':
    main()
