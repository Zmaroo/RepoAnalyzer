"""[1.0] Repository indexing system.

This module provides the core functionality for indexing repositories:
1. File discovery and classification
2. Language detection and parsing
3. Feature extraction and storage
4. Graph projection and analysis
"""

import os
import asyncio
from typing import Optional, Dict, List, Set, Any
from utils.logger import log
from parsers.types import ParserResult, FileType, ExtractedFeatures
from parsers.models import FileClassification
from parsers.language_support import language_registry
from parsers.query_patterns import initialize_pattern_system
from db.upsert_ops import UpsertCoordinator
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
from utils.async_runner import submit_async_task, get_loop, cleanup_tasks
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

# Export main functionality
from .unified_indexer import (
    UnifiedIndexer,
    ProcessingCoordinator,
    process_repository_indexing,
    index_active_project,
    index_active_project_sync
)

# Initialize pattern system
async def initialize():
    """Initialize the indexing system."""
    await ensure_pattern_system()
    log("Indexing system initialized", level="info")

# Register cleanup handler
register_shutdown_handler(cleanup_tasks)

__all__ = [
    # Core functionality
    "clone_and_index_repo",
    "get_or_create_repo",
    "FileProcessor",
    "UnifiedIndexer",
    "ProcessingCoordinator",
    
    # File utilities
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