"""File classification management.

This module provides file classification capabilities for languages,
integrating with the parser system and caching infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    FileClassification as FileClassificationType
)
from parsers.base_parser import BaseParser
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary,
    handle_async_errors,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context, cached_in_request
from db.transaction import transaction_scope

@dataclass
class FileClassifier(BaseParser):
    """File classification management.
    
    This class manages file classification,
    integrating with the parser system for efficient classification.
    
    Attributes:
        language_id (str): The identifier for the language
        file_types (Set[FileType]): Set of supported file types
        _classification_cache (UnifiedCache): Cache for classifications
    """
    
    def __init__(self, language_id: str):
        """Initialize file classifier.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CONFIG,
            parser_type=ParserType.CUSTOM
        )
        self.file_types = set()
        self._classification_cache = None
        self._classification_stats = {
            "total_classifications": 0,
            "successful_classifications": 0,
            "failed_classifications": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "classification_times": []
        }
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize file classifier.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"file_classifier_initialization_{self.language_id}"):
                # Initialize cache
                self._classification_cache = UnifiedCache(f"file_classifier_{self.language_id}")
                await cache_coordinator.register_cache(
                    f"file_classifier_{self.language_id}",
                    self._classification_cache
                )
                
                # Load file types through async_runner
                init_task = submit_async_task(self._load_file_types())
                await asyncio.wrap_future(init_task)
                
                if not self.file_types:
                    raise ProcessingError(f"Failed to load file types for {self.language_id}")
                
                await log(f"File classifier initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing file classifier: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"file_classifier_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"file_classifier_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"classifier_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize file classifier for {self.language_id}: {e}")
    
    async def _load_file_types(self) -> None:
        """Load supported file types from storage."""
        try:
            async with transaction_scope() as txn:
                # Load file types
                file_types_result = await txn.fetch("""
                    SELECT file_type FROM language_file_types
                    WHERE language_id = $1
                """, self.language_id)
                
                if file_types_result:
                    self.file_types = {FileType(row["file_type"]) for row in file_types_result}
                    
        except Exception as e:
            await log(f"Error loading file types: {e}", level="error")
            raise ProcessingError(f"Failed to load file types: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def classify_file(self, file_path: str, content: str) -> FileClassificationType:
        """Classify a file based on its content.
        
        Args:
            file_path: The path to the file
            content: The file content
            
        Returns:
            FileClassificationType: The file classification
        """
        try:
            async with AsyncErrorBoundary(f"file_classification_{self.language_id}"):
                # Check cache first
                cache_key = f"classification:{self.language_id}:{hash(content)}"
                cached_classification = await self._classification_cache.get(cache_key)
                if cached_classification:
                    self._classification_stats["cache_hits"] += 1
                    return FileClassificationType(**cached_classification)
                
                self._classification_stats["cache_misses"] += 1
                
                # Classify through async_runner
                classify_task = submit_async_task(self._classify_content(file_path, content))
                classification = await asyncio.wrap_future(classify_task)
                
                # Cache classification
                await self._classification_cache.set(cache_key, classification.__dict__)
                
                # Update stats
                self._classification_stats["total_classifications"] += 1
                self._classification_stats["successful_classifications"] += 1
                
                await log(f"File classified for {self.language_id}", level="info")
                return classification
                
        except Exception as e:
            await log(f"Error classifying file: {e}", level="error")
            self._classification_stats["failed_classifications"] += 1
            await ErrorAudit.record_error(
                e,
                f"file_classification_{self.language_id}",
                ProcessingError,
                context={"file_path": file_path}
            )
            return FileClassificationType()
    
    async def _classify_content(self, file_path: str, content: str) -> FileClassificationType:
        """Classify file content."""
        classification = FileClassificationType()
        
        try:
            # Get pattern processor instance
            from parsers.pattern_processor import pattern_processor
            
            start_time = time.time()
            
            # Determine file type from extension
            import os
            ext = os.path.splitext(file_path)[1].lower()
            
            # Get patterns for file type detection
            patterns = await pattern_processor.get_patterns_for_file_type(
                self.language_id,
                ext
            )
            
            if patterns:
                for pattern in patterns:
                    try:
                        # Process pattern
                        processed = await pattern_processor.process_pattern(
                            pattern["name"],
                            content,
                            self.language_id
                        )
                        
                        if processed.matches:
                            # Update classification based on pattern type
                            if pattern["name"] == "file_type":
                                classification.file_type = FileType(processed.matches[0]["type"])
                            elif pattern["name"] == "language":
                                classification.language = processed.matches[0]["language"]
                            elif pattern["name"] == "encoding":
                                classification.encoding = processed.matches[0]["encoding"]
                            elif pattern["name"] == "binary":
                                classification.is_binary = bool(processed.matches[0]["is_binary"])
                            
                    except Exception as e:
                        await log(f"Error processing pattern {pattern['name']}: {e}", level="warning")
                        continue
            
            # Update timing stats
            classification_time = time.time() - start_time
            self._classification_stats["classification_times"].append(classification_time)
            
        except Exception as e:
            await log(f"Error classifying content: {e}", level="error")
            
        return classification
    
    async def _cleanup(self) -> None:
        """Clean up file classifier resources."""
        try:
            # Clean up cache
            if self._classification_cache:
                await cache_coordinator.unregister_cache(f"file_classifier_{self.language_id}")
                self._classification_cache = None
            
            # Save classification stats
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO file_classifier_stats (
                        timestamp, language_id,
                        total_classifications, successful_classifications,
                        failed_classifications, avg_classification_time
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """, (
                    time.time(),
                    self.language_id,
                    self._classification_stats["total_classifications"],
                    self._classification_stats["successful_classifications"],
                    self._classification_stats["failed_classifications"],
                    sum(self._classification_stats["classification_times"]) / len(self._classification_stats["classification_times"])
                    if self._classification_stats["classification_times"] else 0
                ))
            
            await log(f"File classifier cleaned up for {self.language_id}", level="info")
            
        except Exception as e:
            await log(f"Error cleaning up file classifier: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup file classifier: {e}")

# Global instance cache
_classifier_instances: Dict[str, FileClassifier] = {}

async def get_file_classifier(language_id: str) -> Optional[FileClassifier]:
    """Get a file classifier instance.
    
    Args:
        language_id: The language to get classifier for
        
    Returns:
        Optional[FileClassifier]: The classifier instance or None if initialization fails
    """
    if language_id not in _classifier_instances:
        classifier = FileClassifier(language_id)
        if await classifier.initialize():
            _classifier_instances[language_id] = classifier
        else:
            return None
    return _classifier_instances[language_id] 