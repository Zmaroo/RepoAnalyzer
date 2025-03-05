"""[1.0] Indexer module initialization.

This module provides the core functionality for repository indexing and analysis.
It coordinates file processing, pattern extraction, and database storage.
"""

from .clone_and_index import clone_and_index_repo, get_or_create_repo
from .file_processor import FileProcessor
from .file_utils import get_file_classification, get_files, get_relative_path, is_processable_file
from .unified_indexer import (
    index_active_project,
    index_active_project_sync,
    process_repository_indexing,
    UnifiedIndexer,
    ProcessingCoordinator
)
# Import from common instead of async_utils to avoid circular dependencies
from .common import async_read_file, handle_async_errors
from .async_utils import batch_process_files

# Initialize pattern system when indexer is imported
from parsers.query_patterns import initialize_pattern_system
initialize_pattern_system()

# Import utilities for initialization
from utils.app_init import register_shutdown_handler
from utils.logger import log
from utils.async_runner import cleanup_tasks

# Create cleanup function for indexer components
async def cleanup_indexer():
    """Cleanup indexer components."""
    try:
        # Cleanup any active processors
        from .file_processor import FileProcessor
        processor = FileProcessor()
        processor.clear_cache()
        
        # Cleanup any active coordinators
        from .unified_indexer import ProcessingCoordinator
        coordinator = ProcessingCoordinator()
        coordinator.cleanup()
        
        log("Indexer components cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up indexer components: {e}", level="error")

# Register cleanup handler
register_shutdown_handler(cleanup_indexer)

__all__ = [
    # Core functionality
    "clone_and_index_repo",
    "get_or_create_repo",
    "FileProcessor",
    "UnifiedIndexer",
    "ProcessingCoordinator",
    
    # File utilities
    "get_file_classification",
    "get_files",
    "get_relative_path",
    "is_processable_file",
    
    # Indexing operations
    "index_active_project",
    "index_active_project_sync",
    "process_repository_indexing",
    
    # Async utilities
    "async_read_file",
    "handle_async_errors",
    "batch_process_files"
] 