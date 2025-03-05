"""[1.0] Unified repository indexing system.

Flow:
1. Entry Points:
   - index_active_project(): For current working directory
   - process_repository_indexing(): Core indexing pipeline
   - ProcessingCoordinator: Handles individual file processing

2. Processing Pipeline:
   - File Discovery: get_files() finds all processable files
   - Batch Processing: Files are processed in configurable batches
   - Graph Updates: Neo4j projections are updated after indexing

3. Integration Points:
   - FileProcessor: Handles parsing and storage
   - Language Registry: Determines file language and parser
   - File Utils: Handles file validation and path management
"""

import os
import asyncio
from typing import Optional, Dict, List, Set, Any
from indexer.async_utils import batch_process_files
from utils.logger import log
from indexer.async_utils import async_read_file
from indexer.file_utils import get_files, get_relative_path, is_processable_file
from parsers.types import ParserResult, FileType, ExtractedFeatures
from parsers.models import FileClassification
from parsers.language_support import language_registry
from parsers.query_patterns import initialize_pattern_system
from db.neo4j_ops import auto_reinvoke_projection_once
from db.upsert_ops import upsert_code_snippet
from db.transaction import transaction_scope
from db.graph_sync import graph_sync
from indexer.file_processor import FileProcessor
from semantic.search import search_code
from utils.error_handling import (
    handle_async_errors,
    ErrorBoundary,
    ErrorSeverity,
    ProcessingError,
    DatabaseError
)
from utils.request_cache import request_cache_context, cached_in_request
from utils.async_runner import submit_async_task, get_loop, cleanup_tasks
from utils.app_init import register_shutdown_handler

# Ensure pattern system is initialized
initialize_pattern_system()

class UnifiedIndexer:
    """[1.1] Core indexing system coordinator."""
    
    def __init__(self):
        self._tasks: Set[asyncio.Future] = set()
        self._loop = get_loop()
        self._initialized = False
        register_shutdown_handler(self.cleanup)
    
    async def initialize(self):
        """Initialize the indexer."""
        if not self._initialized:
            try:
                # Any indexer-specific initialization can go here
                self._initialized = True
                log("UnifiedIndexer initialized", level="info")
            except Exception as e:
                log(f"Error initializing UnifiedIndexer: {e}", level="error")
                raise
    
    async def process_file(self, file_path: str, repo_id: int, repo_path: str) -> None:
        """Process a single file for indexing."""
        if not self._initialized:
            await self.initialize()
            
        try:
            future = submit_async_task(self._process_single_file(file_path, repo_id, repo_path))
            self._tasks.add(future)
            await asyncio.wrap_future(future)
        except Exception as e:
            log(f"Error submitting file processing task: {e}", level="error")
        finally:
            if future in self._tasks:
                self._tasks.remove(future)
    
    async def process_batch(self, files: List[str], repo_id: int, repo_path: str) -> None:
        """Process a batch of files for indexing."""
        if not self._initialized:
            await self.initialize()
            
        batch_tasks = []
        for file in files:
            try:
                future = submit_async_task(self._process_single_file(file, repo_id, repo_path))
                batch_tasks.append(future)
                self._tasks.add(future)
            except Exception as e:
                log(f"Error submitting batch processing task: {e}", level="error")
        
        if batch_tasks:
            try:
                results = await asyncio.gather(*[asyncio.wrap_future(f) for f in batch_tasks], return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        log(f"Error in batch processing: {result}", level="error")
            except Exception as e:
                log(f"Error waiting for batch tasks: {e}", level="error")
            finally:
                for task in batch_tasks:
                    if task in self._tasks:
                        self._tasks.remove(task)
    
    async def wait_for_completion(self) -> None:
        """Wait for all pending tasks to complete."""
        if self._tasks:
            try:
                results = await asyncio.gather(*[asyncio.wrap_future(f) for f in self._tasks], return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        log(f"Error in task completion: {result}", level="error")
            except Exception as e:
                log(f"Error waiting for tasks: {e}", level="error")
            finally:
                self._tasks.clear()
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            # Wait for any pending tasks
            await self.wait_for_completion()
            self._initialized = False
            log("UnifiedIndexer cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up UnifiedIndexer: {e}", level="error")

class ProcessingCoordinator:
    """[1.2] Central coordinator for file processing."""
    
    def __init__(self):
        self.file_processor = FileProcessor()
        self._tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def process_file(self, file_path: str, repo_id: int, repo_path: str) -> Optional[Dict]:
        """[1.3] Single entry point for file processing."""
        async with ErrorBoundary(f"processing file {file_path}", severity=ErrorSeverity.ERROR):
            try:
                if not is_processable_file(file_path):
                    log(f"File not processable: {file_path}", level="debug")
                    return None
                    
                future = submit_async_task(
                    self.file_processor.process_file(file_path, repo_id, repo_path)
                )
                self._tasks.add(future)
                try:
                    return await asyncio.wrap_future(future)
                finally:
                    self._tasks.remove(future)
                    
            except asyncio.CancelledError:
                # Cancel all tracked tasks on interruption
                for task in self._tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._tasks], return_exceptions=True)
                raise
            finally:
                # Clean up any remaining tasks
                if self._tasks:
                    await asyncio.gather(*[asyncio.wrap_future(f) for f in self._tasks], return_exceptions=True)
                    self._tasks.clear()

    async def cleanup(self):
        """Cleanup all processing resources."""
        try:
            # Clean up processor
            self.file_processor.clear_cache()
            
            # Clean up any pending tasks
            if self._tasks:
                for task in self._tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._tasks], return_exceptions=True)
                self._tasks.clear()
            
            log("ProcessingCoordinator cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up ProcessingCoordinator: {e}", level="error")

@handle_async_errors(error_types=(ProcessingError, DatabaseError))
async def process_repository_indexing(repo_path: str, repo_id: int, repo_type: str = "active", single_file: bool = False) -> None:
    """[1.4] Central repository indexing pipeline with request-level caching."""
    tasks: Set[asyncio.Future] = set()
    coordinator = None
    try:
        # Initialize coordinator
        coordinator = ProcessingCoordinator()
        
        # Get files to process
        files = get_files(repo_path, {FileType.CODE, FileType.DOC})
        if not files:
            log(f"No files found to process in {repo_path}", level="warning")
            return
        
        log(f"Processing {len(files)} files from repository {repo_id}", level="info")
        
        async with transaction_scope() as txn:
            await txn.track_repo_change(repo_id)
            
            # Process files in batches to control memory usage
            batch_size = 10  # Adjust based on your system's capability
            for i in range(0, len(files), batch_size):
                batch = files[i:i + batch_size]
                batch_futures = []
                
                for file in batch:
                    if is_processable_file(file):
                        future = submit_async_task(coordinator.process_file(file, repo_id, repo_path))
                        batch_futures.append(future)
                        tasks.add(future)
                
                if batch_futures:
                    # Wait for this batch to complete before starting the next
                    results = await asyncio.gather(*[asyncio.wrap_future(f) for f in batch_futures], return_exceptions=True)
                    # Check for errors but continue processing
                    for result in results:
                        if isinstance(result, Exception):
                            log(f"Error processing file batch: {result}", level="error")
                    
                    # Remove completed tasks
                    for future in batch_futures:
                        if future in tasks:
                            tasks.remove(future)
                
                # Give other tasks a chance to run
                await asyncio.sleep(0)
            
            # Update the graph projection
            try:
                await graph_sync.ensure_projection(repo_id)
                log(f"Graph projection updated for repository {repo_id}", level="info")
            except Exception as e:
                log(f"Error updating graph projection: {e}", level="error")
    finally:
        # Clean up any remaining tasks
        if tasks:
            await asyncio.gather(*[asyncio.wrap_future(f) for f in tasks], return_exceptions=True)
            tasks.clear()
        if coordinator:
            await coordinator.cleanup()

async def index_active_project() -> None:
    """[2.5] Index the currently active project (working directory)."""
    repo_path = os.getcwd()
    repo_name = os.path.basename(os.path.abspath(repo_path))
    
    # Import locally to avoid circular imports
    from indexer.clone_and_index import get_or_create_repo
    
    async with transaction_scope() as txn:
        # Obtain (or create) a repository record
        repo_id = await get_or_create_repo(repo_name, repo_type="active")
        await txn.track_repo_change(repo_id)
        
        log(f"Active project repo: {repo_name} (id: {repo_id}) at {repo_path}")
        await process_repository_indexing(repo_path, repo_id, repo_type="active")

def index_active_project_sync() -> None:
    """Synchronous wrapper for indexing the active project."""
    loop = get_loop()
    future = submit_async_task(index_active_project())
    loop.run_until_complete(future)

if __name__ == "__main__":
    index_active_project_sync() 