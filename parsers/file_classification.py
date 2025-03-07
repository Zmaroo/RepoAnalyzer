"""
File classification and language detection module.

This module provides tools for classifying files based on their content and extension,
determining the appropriate parser type, and extracting language information.
"""

import os
import re
from typing import Dict, Optional, Tuple, List, Set, Union, Callable, Any
import asyncio
from dataclasses import dataclass, field

from parsers.models import FileClassification, FileMetadata
from parsers.types import ParserType, FileType, AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
from parsers.language_mapping import (
    # Import mappings
    TREE_SITTER_LANGUAGES,
    CUSTOM_PARSER_LANGUAGES,
    FULL_EXTENSION_MAP,
    FILENAME_MAP,
    BINARY_EXTENSIONS,
    
    # Import functions
    normalize_language_name,
    is_supported_language,
    get_parser_type,
    get_file_type,
    detect_language,
    get_complete_language_info,
    get_parser_info_for_language,
    get_ai_capabilities
)
from parsers.parser_interfaces import AIParserInterface
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity, ProcessingError, ErrorAudit
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator, cache_metrics
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
from db.transaction import transaction_scope
import time
import psutil

# Track initialization state and tasks
_initialized = False
_pending_tasks: Set[asyncio.Task] = set()

@dataclass
class FileClassifier(AIParserInterface):
    """[3.1] File classification system with AI capabilities."""
    
    def __init__(self):
        """Initialize file classifier."""
        super().__init__(
            language_id="file_classifier",
            file_type=FileType.CODE,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.DOCUMENTATION
            }
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._warmup_complete = False
    
    async def ensure_initialized(self):
        """Ensure the classifier is initialized."""
        if not self._initialized:
            raise ProcessingError("File classifier not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'FileClassifier':
        """[3.1.1] Create and initialize a file classifier instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("file_classifier_initialization"):
                # Initialize language mapping module
                from parsers.language_mapping import initialize as init_language_mapping
                await init_language_mapping()
                
                # Register with health monitor
                global_health_monitor.register_component(
                    "file_classifier",
                    health_check=instance._check_health
                )
                
                instance._initialized = True
                log("File classifier initialized", level="info")
                return instance
        except Exception as e:
            log(f"Error initializing file classifier: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize file classifier: {e}")
    
    async def classify_file(
        self,
        file_path: str,
        content: Optional[str] = None
    ) -> FileClassification:
        """[3.1.2] Classify a file based on its path and optional content."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary(f"classify_file_{file_path}"):
            try:
                # Use unified language detection from language_mapping
                language_id, confidence, is_binary = await detect_language(file_path, content)
                
                # Log detection confidence if it's low
                if confidence < 0.5:
                    log(f"Low confidence ({confidence:.2f}) language detection for {file_path}: {language_id}", level="debug")
                
                # Get complete language information
                language_info = get_complete_language_info(language_id)
                
                # Create classification
                return FileClassification(
                    file_path=file_path,
                    language_id=language_info["canonical_name"],
                    parser_type=language_info["parser_type"],
                    file_type=language_info["file_type"],
                    is_binary=is_binary
                )
            except Exception as e:
                log(f"Error classifying file {file_path}: {e}", level="error")
                raise ProcessingError(f"Failed to classify file {file_path}: {e}")
    
    async def _check_health(self) -> Dict[str, Any]:
        """Health check for file classifier."""
        # Get language mapping metrics
        from parsers.language_mapping import _metrics, _check_health
        language_mapping_health = await _check_health()
        
        # Add file classifier specific metrics
        status = language_mapping_health["status"]
        details = language_mapping_health["details"]
        details["classifier_status"] = {
            "initialized": self._initialized,
            "warmup_complete": self._warmup_complete
        }
        
        return {
            "status": status,
            "details": details
        }
    
    async def cleanup(self):
        """Clean up classifier resources."""
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
            
            # Unregister from health monitor
            global_health_monitor.unregister_component("file_classifier")
            
            self._initialized = False
            log("File classifier cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up file classifier: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup file classifier: {e}")

# Global instance
_file_classifier = None

async def get_file_classifier() -> FileClassifier:
    """[3.2] Get the global file classifier instance."""
    global _file_classifier
    if not _file_classifier:
        _file_classifier = await FileClassifier.create()
    return _file_classifier

@handle_async_errors(error_types=(Exception,))
async def initialize():
    """Initialize file classification resources."""
    global _initialized
    if not _initialized:
        try:
            async with AsyncErrorBoundary("file_classification_initialization"):
                # No special initialization needed yet
                _initialized = True
                log("File classification initialized", level="info")
        except Exception as e:
            log(f"Error initializing file classification: {e}", level="error")
            raise

@handle_async_errors(error_types=(Exception,))
async def get_supported_languages() -> Dict[str, ParserType]:
    """
    Get a dictionary of all supported languages and their parser types.
    Returns:
        Dictionary with language IDs as keys and parser types as values
    """
    # Use the function from language_mapping.py
    from parsers.language_mapping import get_supported_languages as get_langs
    task = asyncio.create_task(get_langs())
    _pending_tasks.add(task)
    try:
        return await task
    finally:
        _pending_tasks.remove(task)

@handle_async_errors(error_types=(Exception,))
async def get_supported_extensions() -> Dict[str, str]:
    """
    Get a dictionary of all supported file extensions and their corresponding languages.
    Returns:
        Dictionary with extensions as keys and language IDs as values
    """
    # Use the function from language_mapping.py
    from parsers.language_mapping import get_supported_extensions as get_exts
    task = asyncio.create_task(get_exts())
    _pending_tasks.add(task)
    try:
        return await task
    finally:
        _pending_tasks.remove(task)

async def cleanup():
    """Clean up file classification resources."""
    global _initialized
    try:
        # Clean up any pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*_pending_tasks, return_exceptions=True)
            _pending_tasks.clear()
        
        _initialized = False
        log("File classification cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up file classification: {e}", level="error")

# Register cleanup handler
register_shutdown_handler(cleanup) 