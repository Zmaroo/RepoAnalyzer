"""[6.0] Pattern processing and validation.

This module provides pattern processing capabilities for code analysis and manipulation.
Core pattern processing functionality separated from AI capabilities.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Union, Optional, Set, Tuple
from dataclasses import dataclass, field
import asyncio
import re
import time
import importlib
import numpy as np
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    ParserType, PatternCategory, PatternPurpose, FileType, 
    PatternDefinition, QueryPattern, AIContext, 
    AIProcessingResult, PatternType, PatternRelationType,
    FeatureCategory, ParserResult, PatternValidationResult,
    ExtractedFeatures, Pattern
)
from parsers.models import (
    PatternMatch, PATTERN_CATEGORIES, ProcessedPattern, 
    QueryResult, PatternRelationship
)
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from parsers.base_parser import BaseParser
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from parsers.language_mapping import normalize_language_name
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.cache import UnifiedCache, cache_coordinator
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.shutdown import register_shutdown_handler
from db.pattern_storage import PatternStorageMetrics, get_pattern_storage
from db.transaction import transaction_scope
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks
import traceback
import os
import psutil
from parsers.query_patterns import (
    create_pattern,
    validate_pattern,
    is_language_supported,
    get_parser_type_for_language
)

@dataclass
class PatternProcessor(BaseParser):
    """Pattern processing management.
    
    This class manages pattern processing for languages,
    integrating with the parser system for efficient pattern handling.
    
    Attributes:
        language_id (str): The identifier for the language
        patterns (Dict[str, Pattern]): Map of pattern names to patterns
        _pattern_cache (UnifiedCache): Cache for processed patterns
    """
    
    def __init__(self, language_id: str):
        """Initialize pattern processor.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )
        self.patterns = {}
        self._pattern_cache = None
        self._processing_stats = {
            "total_processed": 0,
            "successful_processing": 0,
            "failed_processing": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "processing_times": []
        }
        
        # Pattern tracking
        self._pattern_usage_stats = {}
        self._pattern_success_rates = {}
        self._adaptive_thresholds = {}
        self._learning_enabled = True
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize pattern processor.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"pattern_processor_initialization_{self.language_id}"):
                # Initialize cache
                self._pattern_cache = UnifiedCache(f"pattern_processor_{self.language_id}")
                await cache_coordinator.register_cache(
                    f"pattern_processor_{self.language_id}",
                    self._pattern_cache
                )
                
                # Load patterns through async_runner
                init_task = submit_async_task(self._load_patterns())
                await asyncio.wrap_future(init_task)
                
                if not self.patterns:
                    raise ProcessingError(f"Failed to load patterns for {self.language_id}")
                
                await log(f"Pattern processor initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing pattern processor: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"pattern_processor_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"pattern_processor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"processor_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize pattern processor for {self.language_id}: {e}")
    
    async def _load_patterns(self) -> None:
        """Load patterns from storage."""
        try:
            async with transaction_scope(distributed=True) as txn:
                # Record transaction start
                await txn.record_operation("load_patterns_start", {
                    "language_id": self.language_id,
                    "start_time": time.time()
                })
                
                # Load patterns
                patterns_result = await txn.fetch("""
                    SELECT pattern_name, pattern_data FROM language_patterns
                    WHERE language_id = $1
                """, self.language_id)
                
                if patterns_result:
                    self.patterns = {
                        row["pattern_name"]: Pattern(**row["pattern_data"])
                        for row in patterns_result
                    }
                
                # Record transaction metrics
                await txn.record_operation("load_patterns_complete", {
                    "language_id": self.language_id,
                    "pattern_count": len(self.patterns),
                    "end_time": time.time()
                })
                
        except Exception as e:
            await log(f"Error loading patterns: {e}", level="error")
            raise ProcessingError(f"Failed to load patterns: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def process_pattern(
        self,
        pattern_name: str,
        content: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process a pattern.
        
        Args:
            pattern_name: The name of the pattern to process
            content: The content to process
            context: The processing context
            
        Returns:
            PatternValidationResult: The validation result
        """
        try:
            async with AsyncErrorBoundary(f"pattern_processing_{self.language_id}"):
                # Check cache first
                cache_key = f"pattern:{self.language_id}:{pattern_name}:{hash(content)}"
                cached_result = await self._pattern_cache.get(cache_key)
                if cached_result:
                    self._processing_stats["cache_hits"] += 1
                    return PatternValidationResult(**cached_result)
                
                self._processing_stats["cache_misses"] += 1
                
                # Process through async_runner
                process_task = submit_async_task(
                    self._process_pattern_content(pattern_name, content, context)
                )
                result = await asyncio.wrap_future(process_task)
                
                # Cache result
                await self._pattern_cache.set(cache_key, result.__dict__)
                
                # Update stats
                self._processing_stats["total_processed"] += 1
                self._processing_stats["successful_processing"] += 1
                
                await log(f"Pattern processed for {self.language_id}", level="info")
                return result
                
        except Exception as e:
            await log(f"Error processing pattern: {e}", level="error")
            self._processing_stats["failed_processing"] += 1
            await ErrorAudit.record_error(
                e,
                f"pattern_processing_{self.language_id}",
                ProcessingError,
                context={
                    "pattern_name": pattern_name,
                    "content_size": len(content)
                }
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def _process_pattern_content(
        self,
        pattern_name: str,
        content: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process pattern content."""
        try:
            start_time = time.time()
            
            # Get pattern
            pattern = self.patterns.get(pattern_name)
            if not pattern:
                return PatternValidationResult(
                    is_valid=False,
                    errors=[f"Pattern {pattern_name} not found"]
                )
            
            # Process pattern
            matches = await pattern.match(content, context)
            
            # Update timing stats
            processing_time = time.time() - start_time
            self._processing_stats["processing_times"].append(processing_time)
            
            # Update pattern stats
            await self._update_pattern_stats(
                pattern_name,
                bool(matches),
                processing_time,
                len(matches) if matches else 0
            )
            
            return PatternValidationResult(
                is_valid=bool(matches),
                errors=[] if matches else ["No matches found"],
                validation_time=processing_time
            )
            
        except Exception as e:
            await log(f"Error processing pattern content: {e}", level="error")
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def _update_pattern_stats(
        self,
        pattern_name: str,
        success: bool,
        processing_time: float,
        matches_found: int
    ) -> None:
        """Update pattern usage statistics for learning."""
        if not self._learning_enabled:
            return
            
        if pattern_name not in self._pattern_usage_stats:
            self._pattern_usage_stats[pattern_name] = {
                "uses": 0,
                "successes": 0,
                "failures": 0,
                "avg_time": 0.0,
                "matches_found": 0
            }
        
        stats = self._pattern_usage_stats[pattern_name]
        stats["uses"] += 1
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
        
        # Update moving averages
        stats["avg_time"] = (stats["avg_time"] * (stats["uses"] - 1) + processing_time) / stats["uses"]
        stats["matches_found"] = (stats["matches_found"] * (stats["uses"] - 1) + matches_found) / stats["uses"]
        
        # Update success rate
        self._pattern_success_rates[pattern_name] = stats["successes"] / stats["uses"]
        
        # Adjust thresholds based on pattern performance
        if stats["uses"] > 100:  # Wait for sufficient data
            if self._pattern_success_rates[pattern_name] < 0.3:  # Low success rate
                self._adaptive_thresholds[pattern_name] = {
                    "max_time": stats["avg_time"] * 0.8,  # Reduce time allowance
                    "min_matches": stats["matches_found"] * 1.2  # Require more matches
                }
            elif self._pattern_success_rates[pattern_name] > 0.8:  # High success rate
                self._adaptive_thresholds[pattern_name] = {
                    "max_time": stats["avg_time"] * 1.2,  # Allow more time
                    "min_matches": stats["matches_found"] * 0.8  # Accept fewer matches
                }
    
    async def _cleanup(self) -> None:
        """Clean up pattern processor resources."""
        try:
            # Clean up cache
            if self._pattern_cache:
                await cache_coordinator.unregister_cache(f"pattern_processor_{self.language_id}")
                self._pattern_cache = None
            
            # Save processing stats using distributed transaction
            async with transaction_scope(distributed=True) as txn:
                # Record transaction start
                await txn.record_operation("pattern_processor_cleanup_start", {
                    "language_id": self.language_id,
                    "start_time": time.time()
                })
                
                # Save processing stats
                await txn.execute("""
                    INSERT INTO pattern_processor_stats (
                        timestamp, language_id,
                        total_processed, successful_processing,
                        failed_processing, avg_processing_time
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """, (
                    time.time(),
                    self.language_id,
                    self._processing_stats["total_processed"],
                    self._processing_stats["successful_processing"],
                    self._processing_stats["failed_processing"],
                    sum(self._processing_stats["processing_times"]) / len(self._processing_stats["processing_times"])
                    if self._processing_stats["processing_times"] else 0
                ))
                
                # Save pattern stats
                for pattern_name, stats in self._pattern_usage_stats.items():
                    await txn.execute("""
                        INSERT INTO pattern_usage_stats (
                            timestamp, language_id, pattern_name,
                            uses, successes, failures,
                            avg_time, matches_found
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, (
                        time.time(),
                        self.language_id,
                        pattern_name,
                        stats["uses"],
                        stats["successes"],
                        stats["failures"],
                        stats["avg_time"],
                        stats["matches_found"]
                    ))
                
                # Record transaction metrics
                await txn.record_operation("pattern_processor_cleanup_complete", {
                    "language_id": self.language_id,
                    "pattern_count": len(self._pattern_usage_stats),
                    "end_time": time.time()
                })
            
            await log(f"Pattern processor cleaned up for {self.language_id}", level="info")
            
        except Exception as e:
            await log(f"Error cleaning up pattern processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup pattern processor: {e}")

# Global instance cache
_processor_instances: Dict[str, PatternProcessor] = {}

async def get_pattern_processor(language_id: str) -> Optional[PatternProcessor]:
    """Get a pattern processor instance.
    
    Args:
        language_id: The language to get processor for
        
    Returns:
        Optional[PatternProcessor]: The processor instance or None if initialization fails
    """
    if language_id not in _processor_instances:
        processor = PatternProcessor(language_id)
        if await processor.initialize():
            _processor_instances[language_id] = processor
        else:
            return None
    return _processor_instances[language_id]

# Export commonly used functions
__all__ = [
    'get_pattern_processor',
    'validate_all_patterns',
    'report_validation_results'
] 