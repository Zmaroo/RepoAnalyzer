"""File utility functions.

This module provides utilities for file operations, including:
1. Path manipulation and validation
2. File filtering and pattern matching
3. Ignore pattern handling
"""

import os
from pathlib import Path
from typing import List, Set, Optional, Dict, Any
from utils.logger import log
from parsers.types import FileType
from parsers.models import FileClassification
from parsers.file_classification import classify_file as core_classify_file
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ErrorSeverity,
    ProcessingError
)
from utils.cache import UnifiedCache, cache_coordinator
from utils.request_cache import cached_in_request
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
import asyncio
from config import FileConfig

# Initialize file config
file_config = FileConfig()

# Initialize cache
_cache: Optional[UnifiedCache] = None
_initialized = False
_pending_tasks: Set[asyncio.Task] = set()

async def initialize():
    """Initialize file utils resources."""
    global _initialized, _cache
    if not _initialized:
        try:
            async with AsyncErrorBoundary("file_utils_initialization"):
                # Initialize cache
                _cache = UnifiedCache("file_utils")
                await cache_coordinator.register_cache(_cache)
                
                # Register with health monitor
                global_health_monitor.register_component(
                    "file_utils",
                    health_check=_check_health
                )
                
                _initialized = True
                log("File utils initialized", level="info")
        except Exception as e:
            log(f"Error initializing file utils: {e}", level="error")
            raise

async def _check_health() -> Dict[str, Any]:
    """Health check for file utils."""
    return {
        "status": ComponentStatus.HEALTHY,
        "details": {
            "initialized": _initialized,
            "cache_available": _cache is not None
        }
    }

def should_ignore(file_path: str) -> bool:
    """Check if file should be ignored based on patterns.
    
    Args:
        file_path: The path to check
        
    Returns:
        True if the file should be ignored, False otherwise
    """
    # Use patterns from config
    ignore_patterns = set(file_config.ignore_patterns)
    
    path_parts = Path(file_path).parts
    return any(pattern in path_parts for pattern in ignore_patterns)

@handle_async_errors()
@cached_in_request(lambda file_path: f"classify:{file_path}")
async def classify_file(file_path: str) -> Optional[FileClassification]:
    """Get file classification based on extension and content.
    
    This function adds ignore pattern handling on top of the core classification
    system in parsers.file_classification.
    
    Args:
        file_path: The path to classify
        
    Returns:
        FileClassification object or None if file should be ignored
    """
    if not _initialized:
        await initialize()
        
    async with AsyncErrorBoundary(f"classifying file: {file_path}", severity=ErrorSeverity.WARNING):
        try:
            if should_ignore(file_path):
                return None
                
            # Check cache first
            if _cache:
                cached_result = await _cache.get_async(file_path)
                if cached_result:
                    return cached_result
            
            with monitor_operation("classify_file", "file_utils"):
                # Use the core classification system
                result = await core_classify_file(file_path)
                
                # Cache the result
                if _cache and result:
                    await _cache.set_async(file_path, result)
                
                return result
                
        except Exception as e:
            log(f"Error classifying file {file_path}: {e}", level="error")
            return None

@handle_async_errors()
@cached_in_request(lambda base_path, file_types: f"get_files:{base_path}:{sorted(file_types) if file_types else None}")
async def get_files(base_path: str, file_types: Set = None) -> List[str]:
    """Get all processable files in directory.
    
    Args:
        base_path: The root directory to search
        file_types: Optional set of FileType values to include
        
    Returns:
        List of file paths
    """
    if not _initialized:
        await initialize()
        
    async with AsyncErrorBoundary(f"getting files from: {base_path}", severity=ErrorSeverity.WARNING):
        if file_types is None:
            file_types = {FileType.CODE, FileType.DOC}
            
        files = []
        try:
            with monitor_operation("get_files", "file_utils"):
                for root, _, filenames in os.walk(base_path):
                    for filename in filenames:
                        file_path = os.path.join(root, filename)
                        
                        # Skip ignored files
                        if should_ignore(file_path):
                            continue
                        
                        # Check file type
                        classification = await classify_file(file_path)
                        if classification and classification.file_type in file_types:
                            files.append(file_path)
                        
            return files
        except Exception as e:
            log(f"Error getting files: {e}", level="error")
            return []

@handle_async_errors()
async def get_relative_path(file_path: str, base_path: str) -> str:
    """Get relative path from base_path.
    
    Args:
        file_path: The absolute file path
        base_path: The base directory path
        
    Returns:
        Relative path string
    """
    if not _initialized:
        await initialize()
        
    async with AsyncErrorBoundary(f"getting relative path for: {file_path}", severity=ErrorSeverity.WARNING):
        try:
            with monitor_operation("get_relative_path", "file_utils"):
                return os.path.relpath(file_path, base_path)
        except Exception as e:
            log(f"Error getting relative path: {e}", level="error")
            return file_path

@handle_async_errors()
@cached_in_request(lambda file_path: f"processable:{file_path}")
async def is_processable_file(file_path: str) -> bool:
    """Check if file can be processed.
    
    Args:
        file_path: The file path to check
        
    Returns:
        True if file can be processed, False otherwise
    """
    if not _initialized:
        await initialize()
        
    async with AsyncErrorBoundary(f"checking if file is processable: {file_path}", severity=ErrorSeverity.WARNING):
        try:
            with monitor_operation("is_processable_file", "file_utils"):
                if should_ignore(file_path):
                    return False
                    
                classification = await classify_file(file_path)
                return (classification is not None and 
                        classification.file_type in {FileType.CODE, FileType.DOC})
        except Exception as e:
            log(f"Error checking file processability: {e}", level="error")
            return False

async def cleanup():
    """Clean up file utils resources."""
    global _initialized, _cache
    try:
        # Clean up cache
        if _cache:
            await _cache.clear_async()
            await cache_coordinator.unregister_cache("file_utils")
            _cache = None
        
        # Clean up any pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*_pending_tasks, return_exceptions=True)
            _pending_tasks.clear()
        
        # Unregister from health monitor
        global_health_monitor.unregister_component("file_utils")
        
        _initialized = False
        log("File utils cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up file utils: {e}", level="error")
        raise ProcessingError(f"Failed to cleanup file utils: {e}")