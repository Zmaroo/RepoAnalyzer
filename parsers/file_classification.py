"""File classification utilities for RepoAnalyzer.

This module provides utilities for classifying files based on their content,
extension, and other characteristics. It handles detection of binary files,
language identification, and file type determination.
"""

from typing import Dict, Any, List, Optional, Union, Set
import os
import asyncio
import mimetypes
import time
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
)
from parsers.models import QueryResult, FileClassification, PATTERN_CATEGORIES
from parsers.language_mapping import normalize_language_name, detect_language
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorAudit
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from db.transaction import transaction_scope

class FileClassifier:
    """File classifier that handles file type and language detection."""
    
    def __init__(self):
        """Initialize file classifier."""
        self._initialized = False
        self._cache = None
        self._metrics = {
            "total_classifications": 0,
            "successful_classifications": 0,
            "failed_classifications": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "classification_times": []
        }
        self._warmup_complete = False
        register_shutdown_handler(self.cleanup)
    
    async def ensure_initialized(self):
        """Ensure the file classifier is initialized."""
        if not self._initialized:
            raise ProcessingError("File classifier not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'FileClassifier':
        """Create and initialize a file classifier instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("file_classifier_initialization"):
                # Initialize health monitoring first
                await global_health_monitor.update_component_status(
                    "file_classifier",
                    ComponentStatus.INITIALIZING,
                    details={"stage": "starting"}
                )
                
                # Initialize cache
                instance._cache = UnifiedCache("file_classifier")
                await cache_coordinator.register_cache(instance._cache)
                
                # Initialize cache analytics
                analytics = await get_cache_analytics()
                analytics.register_warmup_function(
                    "file_classifier",
                    instance._warmup_cache
                )
                
                instance._initialized = True
                await log("File classifier initialized", level="info")
                
                # Update final status
                await global_health_monitor.update_component_status(
                    "file_classifier",
                    ComponentStatus.HEALTHY,
                    details={"stage": "complete"}
                )
                
                return instance
        except Exception as e:
            await log(f"Error initializing file classifier: {e}", level="error")
            await global_health_monitor.update_component_status(
                "file_classifier",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            # Cleanup on initialization failure
            cleanup_task = submit_async_task(instance.cleanup())
            await asyncio.wrap_future(cleanup_task)
            raise ProcessingError(f"Failed to initialize file classifier: {e}")
    
    async def _warmup_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for file classifier cache."""
        results = {}
        for key in keys:
            try:
                # Check if key is a file path
                if os.path.exists(key):
                    # Classify file
                    classification = await self.classify_file(key)
                    if classification:
                        results[key] = classification.__dict__
            except Exception as e:
                await log(f"Error warming up cache for {key}: {e}", level="warning")
        return results
    
    @handle_async_errors(error_types=ProcessingError)
    async def classify_file(self, file_path: str, content: Optional[str] = None) -> FileClassification:
        """Classify a file based on its path and optional content."""
        if not self._initialized:
            await self.ensure_initialized()
            
        start_time = time.time()
        self._metrics["total_classifications"] += 1
        
        # Get request context for metrics
        request_cache = get_current_request_cache()
        if request_cache:
            await request_cache.set(
                "classification_count",
                (await request_cache.get("classification_count", 0)) + 1
            )
        
        try:
            async with request_cache_context() as cache:
                # Check cache first
                cache_key = f"classification:{file_path}"
                cached_result = await self._cache.get(cache_key)
                if cached_result:
                    self._metrics["cache_hits"] += 1
                    if request_cache:
                        await request_cache.set(
                            "classification_cache_hits",
                            (await request_cache.get("classification_cache_hits", 0)) + 1
                        )
                    return FileClassification(**cached_result)
                
                self._metrics["cache_misses"] += 1
                
                # Check if file exists
                if not os.path.exists(file_path):
                    raise ProcessingError(f"File not found: {file_path}")
                
                # Check if file is binary
                is_binary = await self._is_binary_file(file_path)
                if is_binary:
                    result = FileClassification(
                        file_path=file_path,
                        file_type=FileType.BINARY,
                        language_id="binary",
                        parser_type=ParserType.UNKNOWN,
                        confidence=1.0
                    )
                    await self._cache.set(cache_key, result.__dict__)
                    return result
                
                # Get file content if not provided
                if content is None:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                
                # Detect language
                language_id = await detect_language(os.path.basename(file_path))
                if not language_id:
                    # Try to detect from content
                    language_id = await self._detect_language_from_content(content)
                
                # Get parser type
                parser_type = ParserType.UNKNOWN
                if language_id:
                    if language_id in CUSTOM_PARSER_CLASSES:
                        parser_type = ParserType.CUSTOM
                    elif language_id in SupportedLanguage.__args__:
                        parser_type = ParserType.TREE_SITTER
                
                # Get file type
                file_type = await self._get_file_type(file_path, language_id)
                
                # Create result
                result = FileClassification(
                    file_path=file_path,
                    file_type=file_type,
                    language_id=language_id or "unknown",
                    parser_type=parser_type,
                    confidence=1.0 if language_id else 0.5
                )
                
                # Cache result
                await self._cache.set(cache_key, result.__dict__)
                
                # Update metrics
                self._metrics["successful_classifications"] += 1
                classification_time = time.time() - start_time
                self._metrics["classification_times"].append(classification_time)
                
                # Track request-level metrics
                if request_cache:
                    classification_metrics = {
                        "file_path": file_path,
                        "language_id": language_id,
                        "file_type": file_type.value,
                        "classification_time": classification_time,
                        "timestamp": time.time()
                    }
                    await request_cache.set(
                        f"classification_metrics_{file_path}",
                        classification_metrics
                    )
                
                return result
        except Exception as e:
            self._metrics["failed_classifications"] += 1
            classification_time = time.time() - start_time
            
            # Track error in request context
            if request_cache:
                await request_cache.set(
                    "last_classification_error",
                    {
                        "error": str(e),
                        "file_path": file_path,
                        "timestamp": time.time()
                    }
                )
            
            await log(f"Error classifying file {file_path}: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                "file_classification",
                ProcessingError,
                context={
                    "file_path": file_path,
                    "classification_time": classification_time
                }
            )
            
            return FileClassification(
                file_path=file_path,
                file_type=FileType.UNKNOWN,
                language_id="unknown",
                parser_type=ParserType.UNKNOWN,
                confidence=0.0
            )
    
    async def _is_binary_file(self, file_path: str) -> bool:
        """Check if a file is binary."""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except Exception as e:
            await log(f"Error checking if file is binary: {e}", level="error")
            return False
    
    async def _detect_language_from_content(self, content: str) -> Optional[str]:
        """Detect language from file content."""
        # This could be expanded with more sophisticated content analysis
        # For now, just return None to indicate unknown language
        return None
    
    async def _get_file_type(self, file_path: str, language_id: Optional[str]) -> FileType:
        """Get file type based on file path and language."""
        # Check mime type first
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            if mime_type.startswith('text/'):
                return FileType.TEXT
            elif mime_type.startswith('application/'):
                if mime_type in ['application/json', 'application/xml', 'application/yaml']:
                    return FileType.CONFIG
                else:
                    return FileType.BINARY
            elif mime_type.startswith('image/') or mime_type.startswith('audio/') or mime_type.startswith('video/'):
                return FileType.BINARY
        
        # Check language-based file type
        if language_id:
            if language_id in CUSTOM_PARSER_CLASSES or language_id in SupportedLanguage.__args__:
                return FileType.CODE
            elif language_id in ['json', 'yaml', 'toml', 'ini']:
                return FileType.CONFIG
            elif language_id in ['markdown', 'rst', 'asciidoc']:
                return FileType.DOCUMENTATION
        
        # Default to TEXT for unknown types
        return FileType.TEXT
    
    async def cleanup(self):
        """Clean up file classifier resources."""
        try:
            if not self._initialized:
                return
                
            # Update status
            await global_health_monitor.update_component_status(
                "file_classifier",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache("file_classifier")
                self._cache = None
            
            # Save metrics to database
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO file_classifier_metrics (
                        timestamp, total_classifications,
                        successful_classifications, failed_classifications,
                        cache_hits, cache_misses, avg_classification_time
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, (
                    time.time(),
                    self._metrics["total_classifications"],
                    self._metrics["successful_classifications"],
                    self._metrics["failed_classifications"],
                    self._metrics["cache_hits"],
                    self._metrics["cache_misses"],
                    sum(self._metrics["classification_times"]) / len(self._metrics["classification_times"]) if self._metrics["classification_times"] else 0
                ))
            
            # Let async_runner handle remaining tasks
            cleanup_tasks()
            
            self._initialized = False
            await log("File classifier cleaned up", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                "file_classifier",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
        except Exception as e:
            await log(f"Error cleaning up file classifier: {e}", level="error")
            await global_health_monitor.update_component_status(
                "file_classifier",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
            raise ProcessingError(f"Failed to cleanup file classifier: {e}")

# Create singleton instance
file_classifier = None

async def get_file_classifier() -> FileClassifier:
    """Get or create the file classifier singleton instance."""
    global file_classifier
    if file_classifier is None:
        file_classifier = await FileClassifier.create()
    return file_classifier

async def classify_file(file_path: str, content: Optional[str] = None) -> FileClassification:
    """Classify a file using the file classifier singleton."""
    classifier = await get_file_classifier()
    return await classifier.classify_file(file_path, content)

# Export public interfaces
__all__ = [
    'FileClassifier',
    'get_file_classifier',
    'classify_file'
] 