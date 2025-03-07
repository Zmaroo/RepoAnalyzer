"""[6.0] Pattern processing and validation.

This module provides pattern processing capabilities for code analysis and manipulation.
Core pattern processing functionality separated from AI capabilities.
"""

from typing import Dict, Any, List, Union, Optional, Set
from dataclasses import dataclass, field
import asyncio
import re
import time
import numpy as np
from parsers.types import (
    ParserType, PatternCategory, PatternPurpose, FileType, 
    PatternDefinition, QueryPattern, AIContext, 
    AIProcessingResult, PatternType, PatternRelationType
)
from parsers.models import (
    PatternMatch, PATTERN_CATEGORIES, ProcessedPattern, 
    QueryResult, PatternRelationship
)
from parsers.parser_interfaces import AIParserInterface
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ProcessingError
)
from utils.cache import UnifiedCache
from utils.shutdown import register_shutdown_handler
from db.pattern_storage import PatternStorageMetrics
from db.transaction import transaction_scope
from ai_tools.pattern_integration import PatternLearningMetrics

class PatternProcessor(AIParserInterface):
    """Core pattern processing system."""
    
    def __init__(self):
        """Initialize pattern processor."""
        super().__init__(
            language_id="pattern_processor",
            file_type=FileType.CODE,
            capabilities=set()  # Core processor doesn't have AI capabilities
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._pattern_cache: Dict[str, Any] = {}
        self._metrics = PatternStorageMetrics()
        self._learning_metrics = PatternLearningMetrics()
        self._processing_stats = {
            "total_patterns": 0,
            "matched_patterns": 0,
            "failed_patterns": 0
        }
        self._lock = asyncio.Lock()

    @classmethod
    async def create(cls) -> 'PatternProcessor':
        """Create and initialize a pattern processor instance."""
        instance = cls()
        await instance.initialize()
        return instance

    async def initialize(self) -> bool:
        """Initialize the pattern processor."""
        if self._initialized:
            return True

        try:
            async with AsyncErrorBoundary("pattern_processor_initialization"):
                # Initialize cache
                self._cache = UnifiedCache("pattern_processor")
                
                # Register shutdown handler
                register_shutdown_handler(self.cleanup)
                
                self._initialized = True
                await log("Pattern processor initialized", level="info")
                return True
        except Exception as e:
            await log(f"Error initializing pattern processor: {e}", level="error")
            return False

    async def process_pattern(
        self,
        pattern_name: str,
        source_code: str,
        language_id: str
    ) -> ProcessedPattern:
        """Process a single pattern against source code."""
        if not self._initialized:
            await self.initialize()

        try:
            async with self._lock:
                # Check cache first
                cache_key = f"{pattern_name}:{language_id}:{hash(source_code)}"
                cached_result = await self._cache.get(cache_key)
                if cached_result:
                    return ProcessedPattern(**cached_result)

                pattern = await self._get_pattern(pattern_name, language_id)
                if not pattern:
                    raise ProcessingError(f"Pattern {pattern_name} not found")

                matches = await self._process_pattern_internal(source_code, pattern)
                
                result = ProcessedPattern(
                    pattern_name=pattern_name,
                    matches=matches,
                    category=pattern.category,
                    purpose=pattern.purpose
                )

                # Cache result
                await self._cache.set(cache_key, result.__dict__)
                
                self._processing_stats["total_patterns"] += 1
                if matches:
                    self._processing_stats["matched_patterns"] += 1
                
                return result

        except Exception as e:
            self._processing_stats["failed_patterns"] += 1
            await log(f"Error processing pattern {pattern_name}: {e}", level="error")
            return ProcessedPattern(
                pattern_name=pattern_name,
                error=str(e)
            )

    async def process_for_purpose(
        self,
        source_code: str,
        purpose: PatternPurpose,
        file_type: FileType = FileType.CODE,
        categories: Optional[List[PatternCategory]] = None
    ) -> List[ProcessedPattern]:
        """Process patterns for a specific purpose."""
        if not self._initialized:
            await self.initialize()
        
        results = []
        if categories is None:
            categories = self._get_relevant_categories(purpose)
        
        for category in categories:
            patterns = await self._get_patterns_for_category(category, purpose)
            category_results = await self._process_category_patterns(
                source_code, patterns, category, purpose, file_type
            )
            results.extend(category_results)
        
        return results

    async def _process_pattern_internal(
        self,
        source_code: str,
        pattern: QueryPattern
    ) -> List[PatternMatch]:
        """Internal pattern processing implementation."""
        start_time = time.time()
        matches = []

        try:
            if pattern.tree_sitter:
                matches = await self._process_tree_sitter_pattern(source_code, pattern)
            elif pattern.regex:
                matches = await self._process_regex_pattern(source_code, pattern)

            execution_time = time.time() - start_time
            await self._track_metrics(pattern.pattern_name, execution_time, len(matches))
            
            return matches

        except Exception as e:
            await log(f"Error in pattern processing: {e}", level="error")
            return []

    def _get_relevant_categories(self, purpose: PatternPurpose) -> List[PatternCategory]:
        """Get relevant categories based on purpose."""
        purpose_category_map = {
            PatternPurpose.UNDERSTANDING: [
                PatternCategory.SYNTAX,
                PatternCategory.SEMANTICS,
                PatternCategory.CONTEXT,
                PatternCategory.DEPENDENCIES
            ],
            PatternPurpose.MODIFICATION: [
                PatternCategory.CODE_PATTERNS,
                PatternCategory.BEST_PRACTICES,
                PatternCategory.USER_PATTERNS
            ],
            PatternPurpose.VALIDATION: [
                PatternCategory.COMMON_ISSUES,
                PatternCategory.BEST_PRACTICES
            ],
            PatternPurpose.LEARNING: [
                PatternCategory.LEARNING,
                PatternCategory.USER_PATTERNS
            ]
        }
        return purpose_category_map.get(purpose, list(PatternCategory))

    async def _track_metrics(
        self,
        pattern_name: str,
        execution_time: float,
        match_count: int
    ) -> None:
        """Track pattern processing metrics."""
        async with transaction_scope() as txn:
            await self._metrics.track_pattern_execution(
                pattern_name,
                execution_time,
                match_count
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get pattern processing metrics."""
        return {
            "storage": self._metrics.__dict__,
            "learning": self._learning_metrics.__dict__,
            "processing": self._processing_stats
        }

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics = PatternStorageMetrics()
        self._learning_metrics = PatternLearningMetrics()
        self._processing_stats = {
            "total_patterns": 0,
            "matched_patterns": 0,
            "failed_patterns": 0
        }

    async def cleanup(self):
        """Clean up processor resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._pattern_cache.clear()
            self._initialized = False
            await log("Pattern processor cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up pattern processor: {e}", level="error")

    async def _process_regex_pattern(self, source_code: str, pattern: QueryPattern) -> List[PatternMatch]:
        """Process using regex pattern."""
        matches = []
        for match in pattern.regex.finditer(source_code):
            result = PatternMatch(
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                metadata={
                    "groups": match.groups(),
                    "named_groups": match.groupdict()
                }
            )
            if pattern.extract:
                try:
                    extracted = pattern.extract(result)
                    if extracted:
                        result.metadata.update(extracted)
                except Exception as e:
                    await log(f"Error in pattern extraction: {e}", level="error")
            matches.append(result)
        return matches

    async def _process_tree_sitter_pattern(self, source_code: str, pattern: QueryPattern) -> List[PatternMatch]:
        """Process using tree-sitter pattern."""
        from tree_sitter_language_pack import get_parser
        
        matches = []
        parser = get_parser(pattern.language_id)
        if not parser:
            return matches

        tree = await parser.parse(bytes(source_code, "utf8"))
        if not tree:
            return matches

        query = parser.language.query(pattern.tree_sitter)
        for match in query.matches(tree.root_node):
            captures = {capture.name: capture.node for capture in match.captures}
            result = PatternMatch(
                text=match.pattern_node.text.decode('utf8'),
                start=match.pattern_node.start_point,
                end=match.pattern_node.end_point,
                metadata={"captures": captures}
            )
            
            if pattern.extract:
                try:
                    extracted = pattern.extract(result)
                    if extracted:
                        result.metadata.update(extracted)
                except Exception as e:
                    await log(f"Error in pattern extraction: {e}", level="error")
            
            matches.append(result)
        
        return matches

    async def validate_pattern(self, pattern: QueryPattern, language: str) -> bool:
        """Validate a pattern for a specific language."""
        try:
            # Validate basic structure
            if not pattern.pattern:
                return False

            # Validate based on type
            if pattern.tree_sitter:
                from tree_sitter_language_pack import get_parser
                parser = get_parser(language)
                if not parser:
                    return False
                try:
                    parser.language.query(pattern.tree_sitter)
                    return True
                except Exception:
                    return False
            elif pattern.regex:
                try:
                    re.compile(pattern.pattern)
                    return True
                except Exception:
                    return False

            return False
        except Exception as e:
            await log(f"Error validating pattern: {e}", level="error")
            return False

# Global instance
pattern_processor = PatternProcessor()

async def get_pattern_processor() -> PatternProcessor:
    """Get the global pattern processor instance."""
    if not pattern_processor._initialized:
        await pattern_processor.initialize()
    return pattern_processor 