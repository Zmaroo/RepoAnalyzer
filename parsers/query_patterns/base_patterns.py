"""Base pattern classes for RepoAnalyzer query patterns.

This module provides the abstract base classes that define the common interface
and functionality for both tree-sitter and regex-based query patterns.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Callable, Set, TypeVar, Generic
from dataclasses import dataclass, field
import asyncio
import time
import os
import json
import copy
from collections import defaultdict

# Core parser components
from parsers.types import (
    QueryPattern, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, FileType, ParserType, PatternValidationResult,
    ExtractedFeatures, BlockType, AICapability
)
from parsers.block_extractor import ExtractedBlock

# Utilities
from utils.logger import log
from utils.cache import UnifiedCache, cache_coordinator
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ProcessingError, ErrorSeverity
from utils.shutdown import register_shutdown_handler
from utils.health_monitor import global_health_monitor, ComponentStatus

# Define DATA_DIR for pattern insights storage
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

@dataclass
class BasePatternContext:
    """Base context information for pattern matching.
    
    This class provides context for pattern matching operations,
    with common fields used by all parser types.
    """
    # Core structure information
    code_structure: Dict[str, Any] = field(default_factory=dict)  # AST or custom structure info
    language_stats: Dict[str, int] = field(default_factory=dict)  # Language usage statistics
    project_patterns: List[str] = field(default_factory=list)     # Common patterns in project
    file_location: str = ""                                       # File path/module location
    dependencies: Set[str] = field(default_factory=set)           # Project dependencies
    recent_changes: List[Dict] = field(default_factory=list)      # Recent file modifications
    extracted_blocks: List[ExtractedBlock] = field(default_factory=list)  # Extracted code blocks
    parser_type: ParserType = ParserType.UNKNOWN                  # Parser type being used
    
    # Enhanced context for pattern processing
    metadata: Dict[str, Any] = field(default_factory=dict)        # Additional metadata
    validation_results: Dict[str, PatternValidationResult] = field(default_factory=dict)  # Validation status
    pattern_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # Pattern performance stats
    block_types: List[BlockType] = field(default_factory=list)    # Types of blocks in the file
    relationships: Dict[str, List[str]] = field(default_factory=dict)  # Pattern relationships
    ai_capabilities: Set[AICapability] = field(default_factory=set)  # AI capabilities for this context
    language_id: str = ""                                         # Language identifier
    file_type: FileType = FileType.CODE                           # Type of file
    processing_timestamp: float = field(default_factory=time.time)  # Time of creation
    
    def get_context_key(self) -> str:
        """Generate a unique key for this context."""
        return f"{self.file_location}:{len(self.dependencies)}:{len(self.project_patterns)}:{self.parser_type.value}:{self.language_id}"
    
    def get_parser_specific_context(self) -> Dict[str, Any]:
        """Get parser-specific context information."""
        # This will be overridden by specific implementations
        return {"parser_type": self.parser_type.value}
    
    def update_metadata(self, key: str, value: Any) -> None:
        """Update metadata with new information."""
        self.metadata[key] = value
        self.processing_timestamp = time.time()  # Update timestamp


class BasePatternPerformanceMetrics:
    """Base class for tracking pattern performance metrics."""
    
    def __init__(self):
        """Initialize pattern performance metrics."""
        # Usage statistics
        self.total_uses = 0
        self.successful_matches = 0
        self.failed_matches = 0
        self.execution_times: List[float] = []
        
        # Context-specific performance
        self.context_performance: Dict[str, Dict[str, float]] = {}
        
        # Quality metrics
        self.false_positives = 0
        self.false_negatives = 0
        self.validation_failures = 0
        
        # Parser-specific statistics
        self.parser_stats: Dict[ParserType, Dict[str, int]] = {
            ParserType.TREE_SITTER: defaultdict(int),
            ParserType.CUSTOM: defaultdict(int),
            ParserType.UNKNOWN: defaultdict(int)
        }
        
        # Pattern-specific metrics
        self.pattern_match_counts: Dict[str, int] = defaultdict(int)
        self.pattern_timings: Dict[str, List[float]] = defaultdict(list)
        
        # Memory and performance tracking
        self.memory_usage: List[int] = []
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Time tracking
        self.last_updated = time.time()
        self.creation_time = time.time()
    
    def update(
        self,
        success: bool,
        execution_time: float,
        context_key: Optional[str] = None,
        parser_type: Optional[ParserType] = None,
        pattern_name: Optional[str] = None,
        memory_usage: Optional[int] = None,
        cache_hit: bool = False
    ):
        """Update metrics with new data."""
        # Update basic usage stats
        self.total_uses += 1
        if success:
            self.successful_matches += 1
        else:
            self.failed_matches += 1
        self.execution_times.append(execution_time)
        
        # Update context-specific performance
        if context_key:
            if context_key not in self.context_performance:
                self.context_performance[context_key] = {
                    "uses": 0,
                    "successes": 0,
                    "avg_time": 0.0
                }
            
            perf = self.context_performance[context_key]
            perf["uses"] += 1
            if success:
                perf["successes"] += 1
            perf["avg_time"] = (perf["avg_time"] * (perf["uses"] - 1) + execution_time) / perf["uses"]
        
        # Update parser-specific stats
        if parser_type:
            stats = self.parser_stats[parser_type]
            stats["total"] += 1
            if success:
                stats["successful"] += 1
            else:
                stats["failed"] += 1
            stats["avg_time"] = ((stats.get("avg_time", 0) * (stats["total"] - 1)) + execution_time) / stats["total"]
        
        # Update pattern-specific metrics
        if pattern_name:
            self.pattern_match_counts[pattern_name] += 1
            self.pattern_timings[pattern_name].append(execution_time)
        
        # Update memory usage
        if memory_usage is not None:
            self.memory_usage.append(memory_usage)
        
        # Update cache stats
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
            
        self.last_updated = time.time()
    
    def get_success_rate(self, parser_type: Optional[ParserType] = None) -> float:
        """Get success rate, optionally for a specific parser type."""
        if parser_type:
            stats = self.parser_stats[parser_type]
            return stats.get("successful", 0) / stats.get("total", 1) if stats.get("total", 0) > 0 else 0.0
        return self.successful_matches / self.total_uses if self.total_uses > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """Get overall success rate across all parser types."""
        return self.successful_matches / self.total_uses if self.total_uses > 0 else 0.0
    
    @property
    def avg_execution_time(self) -> float:
        """Get average execution time across all matches."""
        return sum(self.execution_times) / len(self.execution_times) if self.execution_times else 0.0
    
    def get_avg_execution_time(self, parser_type: Optional[ParserType] = None) -> float:
        """Get average execution time, optionally for a specific parser type."""
        if parser_type:
            return self.parser_stats[parser_type].get("avg_time", 0.0)
        return self.avg_execution_time
    
    def get_avg_memory_usage(self) -> int:
        """Get average memory usage in bytes."""
        return int(sum(self.memory_usage) / len(self.memory_usage)) if self.memory_usage else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a serializable dictionary."""
        return {
            "total_uses": self.total_uses,
            "successful_matches": self.successful_matches,
            "failed_matches": self.failed_matches,
            "success_rate": self.success_rate,
            "avg_execution_time": self.avg_execution_time,
            "parser_stats": {k.value: v for k, v in self.parser_stats.items()},
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "last_updated": self.last_updated,
            "creation_time": self.creation_time,
            "avg_memory_usage": self.get_avg_memory_usage()
        }


class BasePattern(ABC):
    """Base class for all query patterns."""
    
    def __init__(
        self, 
        name: str,
        pattern: str,
        category: PatternCategory,
        purpose: PatternPurpose,
        language_id: str = "*",
        confidence: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None,
        extract: Optional[Callable] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ):
        """Initialize base pattern.
        
        Args:
            name: Name of the pattern
            pattern: Pattern string (different format based on parser type)
            category: Pattern category
            purpose: Pattern purpose
            language_id: Language identifier
            confidence: Initial confidence level
            metadata: Additional metadata
            extract: Function to extract structured data from matches
            test_cases: Test cases for pattern validation
        """
        self.name = name
        self.pattern = pattern
        self.category = category
        self.purpose = purpose
        self.language_id = language_id
        self.confidence = confidence
        self.metadata = metadata or {}
        self.extract = extract
        self.test_cases = test_cases or []
        
        # Pattern performance metrics
        self.metrics = BasePatternPerformanceMetrics()
        
        # Caching support
        self._pattern_cache = UnifiedCache(
            f"{self.__class__.__name__}_{name}_cache", 
            eviction_policy="lru", 
            max_size=1000
        )
        
        # Health tracking
        register_shutdown_handler(self.cleanup)
    
    @abstractmethod
    async def initialize(self):
        """Initialize required components."""
        # Register cache with coordinator
        await cache_coordinator.register_cache(
            f"{self.__class__.__name__}_{self.name}_cache", 
            self._pattern_cache
        )
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            # Unregister cache
            await cache_coordinator.unregister_cache(
                f"{self.__class__.__name__}_{self.name}_cache"
            )
            
            # Report pattern health
            await global_health_monitor.update_component_status(
                f"{self.__class__.__name__}_{self.name}",
                ComponentStatus.SHUTDOWN,
                details={
                    "metrics": self.metrics.to_dict()
                }
            )
        except Exception as e:
            await log(
                f"Error cleaning up pattern: {e}", 
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id
                }
            )
    
    @abstractmethod
    async def matches(
        self,
        source_code: str,
        context: Optional[BasePatternContext] = None
    ) -> List[Dict[str, Any]]:
        """Match pattern against source code.
        
        Args:
            source_code: Source code to match against
            context: Optional context information
            
        Returns:
            List of matches with extracted information
        """
        pass
    
    def _estimate_memory_usage(self) -> int:
        """Estimate current memory usage for tracking."""
        import sys
        import gc
        
        gc.collect()  # Force garbage collection for more accurate measurement
        return sys.getsizeof(self) + sum(sys.getsizeof(obj) for obj in gc.get_objects() 
                                        if hasattr(obj, '__dict__') and id(self) in [id(x) for x in gc.get_referrers(obj)])


class BaseAdaptivePattern(BasePattern):
    """Base class for adaptive patterns that can learn and improve."""
    
    def __init__(
        self, 
        name: str,
        pattern: str,
        category: PatternCategory,
        purpose: PatternPurpose,
        language_id: str = "*",
        confidence: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None,
        extract: Optional[Callable] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ):
        """Initialize adaptive pattern."""
        super().__init__(
            name=name,
            pattern=pattern,
            category=category,
            purpose=purpose,
            language_id=language_id,
            confidence=confidence,
            metadata=metadata,
            extract=extract,
            test_cases=test_cases
        )
        
        # Adaptation tracking
        self.adaptations: List[Dict[str, Any]] = []
        
        # Enhanced capabilities
        self.requires_semantic = metadata.get("requires_semantic", False) if metadata else False
        self.is_nestable = metadata.get("is_nestable", False) if metadata else False
        self.contains_blocks = metadata.get("contains_blocks", []) if metadata else []
        self.extraction_priority = metadata.get("extraction_priority", 5) if metadata else 5
        self.block_type = metadata.get("block_type") if metadata else None
    
    def should_adapt(self, context: BasePatternContext) -> bool:
        """Determine if pattern should adapt to context."""
        # Check context-specific performance
        if context_key := context.get_context_key():
            if perf := self.metrics.context_performance.get(context_key):
                # Adapt if we have enough data and success rate is low
                return perf["uses"] > 10 and perf["successes"] / perf["uses"] < 0.5
        
        # Check overall performance
        success_rate = self.metrics.get_success_rate(context.parser_type)
        if success_rate < 0.5 and self.metrics.parser_stats[context.parser_type].get("total", 0) > 10:
            return True
        
        return False
    
    @abstractmethod
    async def adapt_to_context(self, context: BasePatternContext) -> None:
        """Adapt pattern based on context."""
        pass


class BaseResilientPattern(BaseAdaptivePattern):
    """Base class for resilient patterns that handle errors gracefully."""
    
    def __init__(
        self, 
        name: str,
        pattern: str,
        category: PatternCategory,
        purpose: PatternPurpose,
        language_id: str = "*",
        confidence: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None,
        extract: Optional[Callable] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ):
        """Initialize resilient pattern."""
        super().__init__(
            name=name,
            pattern=pattern,
            category=category,
            purpose=purpose,
            language_id=language_id,
            confidence=confidence,
            metadata=metadata,
            extract=extract,
            test_cases=test_cases
        )
        
        # Error handling capabilities
        self.max_retries = metadata.get("max_retries", 3) if metadata else 3
        self.chunk_size = metadata.get("chunk_size", 1000) if metadata else 1000
        self.chunk_overlap = metadata.get("chunk_overlap", 100) if metadata else 100
    
    async def matches(
        self,
        source_code: str,
        context: Optional[BasePatternContext] = None
    ) -> List[Dict[str, Any]]:
        """Match with error handling.
        
        Args:
            source_code: Source code to match against
            context: Optional context information
            
        Returns:
            List of matches with extracted information
        """
        start_time = time.time()
        context_key = context.get_context_key() if context else None
        parser_type = context.parser_type if context else ParserType.UNKNOWN
        
        try:
            # Try to match normally
            matches = await self._specific_matches(source_code, context)
            
            # Update metrics
            execution_time = time.time() - start_time
            self.metrics.update(
                success=bool(matches),
                execution_time=execution_time,
                context_key=context_key,
                parser_type=parser_type,
                pattern_name=self.name
            )
            
            return matches
        except Exception as e:
            # Handle errors and try to recover
            execution_time = time.time() - start_time
            self.metrics.update(
                success=False,
                execution_time=execution_time,
                context_key=context_key,
                parser_type=parser_type,
                pattern_name=self.name
            )
            
            try:
                # Try recovery mechanisms
                return await self._handle_match_error(e, source_code, context)
            except Exception as recovery_error:
                await log(
                    f"Error in resilient pattern recovery: {recovery_error}", 
                    level="error",
                    context={
                        "pattern_name": self.name,
                        "language_id": self.language_id,
                        "original_error": str(e)
                    }
                )
                return []
    
    @abstractmethod
    async def _specific_matches(
        self,
        source_code: str,
        context: Optional[BasePatternContext] = None
    ) -> List[Dict[str, Any]]:
        """Implementation-specific matching logic."""
        pass
    
    @abstractmethod
    async def _handle_match_error(
        self, 
        error: Exception,
        source_code: str,
        context: Optional[BasePatternContext] = None
    ) -> List[Dict[str, Any]]:
        """Implementation-specific error handling."""
        pass
    
    def _classify_error(self, error_msg: str) -> str:
        """Classify error type based on error message."""
        error_msg = str(error_msg).lower()
        
        if "syntax" in error_msg:
            return "syntax_error"
        elif "timeout" in error_msg or "time limit" in error_msg:
            return "timeout_error"
        elif "memory" in error_msg:
            return "memory_error"
        elif "match limit" in error_msg:
            return "match_limit_error"
        elif "partial" in error_msg:
            return "partial_match_error"
        elif "ambiguous" in error_msg:
            return "ambiguous_match_error"
        elif "recursion" in error_msg:
            return "recursion_error"
        else:
            return "unknown_error"
    
    def _split_into_chunks(self, source_code: str, chunk_size: int = 1000) -> List[str]:
        """Split source code into chunks for processing.
        
        Args:
            source_code: Source code to split
            chunk_size: Size of each chunk
            
        Returns:
            List of source code chunks
        """
        chunks = []
        for i in range(0, len(source_code), chunk_size - self.chunk_overlap):
            end = min(i + chunk_size, len(source_code))
            chunks.append(source_code[i:end])
            if end == len(source_code):
                break
        return chunks


class BaseCrossProjectPatternLearner(ABC):
    """Base class for cross-project pattern learning."""
    
    def __init__(self, patterns=None):
        """Initialize cross-project pattern learner.
        
        Args:
            patterns: Optional list of patterns to learn from
        """
        self.patterns = patterns or []
        self.project_insights = {}
        self.pattern_improvements = defaultdict(list)
        self.training_projects = set()
        self.pattern_variations = defaultdict(list)
        
        # Model state
        self.initialized = False
        
        # Performance tracking
        self.metrics = {
            "projects_analyzed": 0,
            "patterns_improved": 0,
            "success_rate_before": {},
            "success_rate_after": {},
            "last_update": time.time()
        }
    
    async def initialize(self) -> None:
        """Initialize pattern learner."""
        if self.initialized:
            return
            
        # Load previous insights if available
        await self._load_insights()
        self.initialized = True
        
        await log(
            f"{self.__class__.__name__} initialized", 
            level="info",
            context={
                "patterns_count": len(self.patterns),
                "projects_analyzed": self.metrics["projects_analyzed"]
            }
        )
    
    @abstractmethod
    async def learn_from_project(
        self, 
        project_id: str, 
        source_files: List[Dict[str, str]]
    ) -> None:
        """Learn from project source files."""
        pass
    
    @abstractmethod
    async def apply_improvements(
        self, 
        pattern_names: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Apply learned improvements to patterns."""
        pass
    
    async def cleanup(self):
        """Clean up pattern learner resources."""
        try:
            # Save insights to disk
            await self._save_insights()
            
            # Update final status
            await global_health_monitor.update_component_status(
                f"{self.__class__.__name__}",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self.metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"{self.__class__.__name__}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
    
    async def _load_insights(self) -> None:
        """Load previously saved insights."""
        insights_path = os.path.join(
            DATA_DIR, 
            f"{self.__class__.__name__.lower()}_insights.json"
        )
        
        try:
            if os.path.exists(insights_path):
                with open(insights_path, 'r') as f:
                    data = json.load(f)
                    
                    # Load data
                    self.project_insights = data.get("project_insights", {})
                    self.pattern_improvements = defaultdict(list, data.get("pattern_improvements", {}))
                    self.training_projects = set(data.get("training_projects", []))
                    self.pattern_variations = defaultdict(list, data.get("pattern_variations", {}))
                    self.metrics = data.get("metrics", self.metrics)
                    
                await log(
                    f"Loaded {self.__class__.__name__} insights", 
                    level="info",
                    context={
                        "projects": len(self.project_insights),
                        "improvements": sum(len(imps) for imps in self.pattern_improvements.values())
                    }
                )
        except Exception as e:
            await log(
                f"Could not load {self.__class__.__name__} insights: {e}",
                level="warning"
            )
    
    async def _save_insights(self) -> None:
        """Save insights to disk."""
        try:
            # Ensure data directory exists
            os.makedirs(DATA_DIR, exist_ok=True)
            
            # Prepare data for serialization
            data = {
                "project_insights": self.project_insights,
                "pattern_improvements": dict(self.pattern_improvements),
                "training_projects": list(self.training_projects),
                "pattern_variations": dict(self.pattern_variations),
                "metrics": self.metrics,
                "timestamp": time.time()
            }
            
            # Write to file
            insights_path = os.path.join(
                DATA_DIR, 
                f"{self.__class__.__name__.lower()}_insights.json"
            )
            
            with open(insights_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            await log(
                f"Saved {self.__class__.__name__} insights",
                level="info"
            )
        except Exception as e:
            await log(
                f"Error saving {self.__class__.__name__} insights: {e}",
                level="error"
            )

# Export base types
__all__ = [
    'BasePatternContext',
    'BasePatternPerformanceMetrics',
    'BasePattern',
    'BaseAdaptivePattern',
    'BaseResilientPattern',
    'BaseCrossProjectPatternLearner'
] 