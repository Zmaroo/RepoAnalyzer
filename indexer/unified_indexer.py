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
from db.upsert_ops import UpsertCoordinator  # Use UpsertCoordinator for database operations
from db.transaction import transaction_scope
from db.graph_sync import graph_sync
from indexer.file_processor import FileProcessor
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ErrorSeverity,
    ProcessingError,
    DatabaseError
)
from utils.request_cache import request_cache_context, cached_in_request
from utils.shutdown import register_shutdown_handler

# Initialize pattern system
_pattern_system_initialized = False

async def ensure_pattern_system():
    """Ensure pattern system is initialized."""
    global _pattern_system_initialized
    if not _pattern_system_initialized:
        await initialize_pattern_system()
        _pattern_system_initialized = True

# Initialize upsert coordinator
_upsert_coordinator = UpsertCoordinator()

class UnifiedIndexer:
    """[1.1] Core indexing system coordinator."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._processing_coordinator = None
        self._file_processor = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("UnifiedIndexer not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'UnifiedIndexer':
        """Async factory method to create and initialize a UnifiedIndexer instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="unified indexer initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize required components
                from indexer.file_processor import FileProcessor
                from indexer.processing_coordinator import ProcessingCoordinator
                
                # Initialize file processor
                instance._file_processor = await FileProcessor.create()
                
                # Initialize processing coordinator
                instance._processing_coordinator = await ProcessingCoordinator.create()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("unified_indexer")
                
                instance._initialized = True
                await log("Unified indexer initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing unified indexer: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize unified indexer: {e}")
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up components in reverse initialization order
            if self._processing_coordinator:
                await self._processing_coordinator.cleanup()
            if self._file_processor:
                await self._file_processor.cleanup()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("unified_indexer")
            
            self._initialized = False
            await log("Unified indexer cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up unified indexer: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup unified indexer: {e}")

class ProcessingCoordinator:
    """[1.2] Coordinates file processing tasks."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._processing_queue = asyncio.Queue()
        self._active_tasks: Set[asyncio.Task] = set()
        self._file_processor = None
        self._batch_size = 10
        self._max_concurrent_tasks = 5
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("ProcessingCoordinator not initialized. Use create() to initialize.")
        if not self._file_processor:
            raise ProcessingError("File processor not initialized")
        return True
    
    @classmethod
    async def create(cls) -> 'ProcessingCoordinator':
        """Async factory method to create and initialize a ProcessingCoordinator instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="processing coordinator initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize required components
                from indexer.file_processor import FileProcessor
                instance._file_processor = await FileProcessor.create()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("processing_coordinator")
                
                instance._initialized = True
                await log("Processing coordinator initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing processing coordinator: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize processing coordinator: {e}")
    
    async def process_file(self, file_path: str, repo_id: int, repo_path: str) -> None:
        """Process a single file for indexing."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            async with self._lock:
                task = asyncio.create_task(self._process_single_file(file_path, repo_id, repo_path))
                self._pending_tasks.add(task)
                task.add_done_callback(lambda t: self._pending_tasks.remove(t) if t in self._pending_tasks else None)
                await task
        except Exception as e:
            await log(f"Error processing file {file_path}: {e}", level="error")
            raise ProcessingError(f"Failed to process file {file_path}: {e}")
    
    async def process_batch(self, files: List[str], repo_id: int, repo_path: str) -> None:
        """Process a batch of files for indexing."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with self._lock:
            batch_tasks = []
            for file in files:
                try:
                    task = asyncio.create_task(self._process_single_file(file, repo_id, repo_path))
                    batch_tasks.append(task)
                    self._pending_tasks.add(task)
                    task.add_done_callback(lambda t: self._pending_tasks.remove(t) if t in self._pending_tasks else None)
                except Exception as e:
                    await log(f"Error submitting batch processing task for {file}: {e}", level="error")
            
            if batch_tasks:
                try:
                    results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            await log(f"Error in batch processing: {result}", level="error")
                except Exception as e:
                    await log(f"Error waiting for batch tasks: {e}", level="error")
                    raise ProcessingError(f"Failed to process batch: {e}")
    
    async def _process_single_file(self, file_path: str, repo_id: int, repo_path: str) -> None:
        """Process a single file with error handling."""
        try:
            await self._file_processor.process_file(file_path, repo_id, repo_path)
        except Exception as e:
            await log(f"Error processing file {file_path}: {e}", level="error")
            raise ProcessingError(f"Failed to process file {file_path}: {e}")
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            if not self._initialized:
                return
                
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up file processor
            if self._file_processor:
                await self._file_processor.cleanup()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("processing_coordinator")
            
            self._initialized = False
            await log("Processing coordinator cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up processing coordinator: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup processing coordinator: {e}")

@handle_async_errors
async def process_repository_indexing(repo_path: str, repo_id: int, repo_type: str = "active", single_file: bool = False) -> None:
    """Process a repository for indexing.
    
    Args:
        repo_path: Path to the repository
        repo_id: ID of the repository
        repo_type: Type of repository (active/reference)
        single_file: Whether to process a single file
    """
    async with AsyncErrorBoundary(f"indexing repository {repo_path}", severity=ErrorSeverity.ERROR):
        try:
            # Initialize components
            if not _upsert_coordinator._initialized:
                await _upsert_coordinator.initialize()
            
            # Get all processable files
            files = get_files(repo_path)
            if not files:
                log(f"No processable files found in {repo_path}", level="warning")
                return
                
            # Process files in batches
            await batch_process_files(files, repo_id, repo_path)
            
            # Update graph projection
            await graph_sync.invalidate_projection(repo_id)
            await graph_sync.ensure_projection(repo_id)
            
        except Exception as e:
            log(f"Error processing repository {repo_path}: {e}", level="error")
            raise

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
    loop = asyncio.get_event_loop()
    loop.run_until_complete(index_active_project())

if __name__ == "__main__":
    index_active_project_sync() 