"""Enhanced pattern functionality for RepoAnalyzer custom parsers.

This module provides advanced pattern capabilities that enhance the existing
query patterns with features like context awareness, learning, and error recovery.
Specialized for custom regex parsers with a unified interface.
"""

from typing import Dict, Any, List, Optional, Set, TypeVar, Generic, Union, Callable, Tuple
from dataclasses import dataclass, field, asdict
import asyncio
import time
import re
import copy
from collections import defaultdict
import os
import json

# Core parser components
from parsers.types import (
    QueryPattern, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, FileType, ParserType, PatternValidationResult,
    ExtractedFeatures, BlockType, AICapability
)
from parsers.base_parser import BaseParser
from parsers.block_extractor import BlockExtractor, ExtractedBlock
from parsers.language_mapping import normalize_language_name

# Custom parser support
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES

# Utilities
from utils.logger import log
from utils.cache import UnifiedCache, cache_coordinator
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ProcessingError, ErrorSeverity
from utils.shutdown import register_shutdown_handler
from utils.health_monitor import global_health_monitor, ComponentStatus
from db.transaction import transaction_scope

# Define DATA_DIR for pattern insights storage
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

@dataclass
class PatternContext:
    """Context information for pattern matching.
    
    This class provides context for pattern matching operations,
    supporting custom regex parsing approaches.
    """
    # Core structure information
    code_structure: Dict[str, Any] = field(default_factory=dict)  # Custom parser structure info
    language_stats: Dict[str, int] = field(default_factory=dict)  # Language usage statistics
    project_patterns: List[str] = field(default_factory=list)     # Common patterns in project
    file_location: str = ""                                       # File path/module location
    dependencies: Set[str] = field(default_factory=set)           # Project dependencies
    recent_changes: List[Dict] = field(default_factory=list)      # Recent file modifications
    extracted_blocks: List[ExtractedBlock] = field(default_factory=list)  # Extracted code blocks
    parser_type: ParserType = ParserType.CUSTOM                   # Custom parser type
    
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
        return {
            "custom_structure": self.code_structure,
            "language_id": self.language_id,
            "custom_parser_available": True,
            "regex_context": self.metadata.get("regex_context", {}),
            "pattern_flags": self.metadata.get("pattern_flags", re.MULTILINE | re.DOTALL)
        }
    
    def update_metadata(self, key: str, value: Any) -> None:
        """Update metadata with new information."""
        self.metadata[key] = value
        self.processing_timestamp = time.time()  # Update timestamp

class PatternPerformanceMetrics:
    """Track pattern performance metrics.
    
    Provides comprehensive tracking of pattern usage and performance
    metrics across both tree-sitter and custom parsers.
    """
    
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
        """Update metrics with new data.
        
        Args:
            success: Whether the pattern match was successful
            execution_time: Time taken for the match
            context_key: Unique key for the context
            parser_type: Type of parser used
            pattern_name: Name of the pattern
            memory_usage: Bytes used for this operation
            cache_hit: Whether the result was from cache
        """
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
        """Get success rate, optionally for a specific parser type.
        
        Args:
            parser_type: Optional parser type to get success rate for
            
        Returns:
            Success rate as a float between 0 and 1
        """
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
        """Get average execution time, optionally for a specific parser type.
        
        Args:
            parser_type: Optional parser type to get execution time for
            
        Returns:
            Average execution time in seconds
        """
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

class AdaptivePattern(QueryPattern):
    """Self-improving pattern with learning capabilities.
    
    This pattern type supports regex-based parsing approaches,
    with automatic adaptation and learning capabilities based on context and usage.
    """
    
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
        regex_pattern: Optional[str] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ):
        """Initialize adaptive pattern.
        
        Args:
            name: Name of the pattern
            pattern: Primary pattern string
            category: Pattern category
            purpose: Pattern purpose
            language_id: Language identifier
            confidence: Initial confidence level
            metadata: Additional metadata
            extract: Function to extract structured data from matches
            regex_pattern: Regex pattern for custom parsers
            test_cases: Test cases for pattern validation
        """
        super().__init__(
            name=name,
            pattern=pattern,
            category=category,
            purpose=purpose,
            language_id=language_id,
            confidence=confidence,
            metadata=metadata or {},
            extract=extract,
            regex_pattern=regex_pattern,
            test_cases=test_cases or []
        )
        
        # If regex pattern not explicitly provided, use pattern as regex
        if regex_pattern is None and pattern:
            self.regex_pattern = pattern
        
        # Pattern performance metrics
        self.metrics = PatternPerformanceMetrics()
        
        # Adaptation tracking
        self.adaptations: List[Dict[str, Any]] = []
        
        # Caching support
        self._pattern_cache = UnifiedCache(
            "adaptive_pattern_cache", 
            eviction_policy="lru", 
            max_size=1000
        )
        
        # Required components
        self._block_extractor = None
        self._base_parser = None
        
        # Enhanced capabilities
        self.requires_semantic = False
        self.is_nestable = metadata.get("is_nestable", False) if metadata else False
        self.contains_blocks = metadata.get("contains_blocks", []) if metadata else []
        self.extraction_priority = metadata.get("extraction_priority", 5) if metadata else 5
        self.block_type = metadata.get("block_type") if metadata else None
        
        # Health monitoring and cleanup
        register_shutdown_handler(self.cleanup)
    
    async def initialize(self):
        """Initialize required components."""
        if not self._block_extractor:
            from parsers.block_extractor import get_block_extractor
            self._block_extractor = await get_block_extractor()
        
        if not self._base_parser:
            # Use appropriate parser type based on what's available
            self._base_parser = await BaseParser.create(
                self.language_id,
                FileType.CODE,
                ParserType.CUSTOM
            )
            
        # Register cache with coordinator
        await cache_coordinator.register_cache("adaptive_pattern_cache", self._pattern_cache)
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            # Unregister cache
            await cache_coordinator.unregister_cache("adaptive_pattern_cache")
            
            # Report adaptive pattern health
            await global_health_monitor.update_component_status(
                f"adaptive_pattern_{self.name}",
                ComponentStatus.SHUTDOWN,
                details={
                    "metrics": self.metrics.to_dict(),
                    "adaptations": len(self.adaptations)
                }
            )
        except Exception as e:
            await log(
                f"Error cleaning up adaptive pattern: {e}", 
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id
                }
            )
    
    async def matches(
        self,
        source_code: str,
        context: Optional[PatternContext] = None
    ) -> List[Dict[str, Any]]:
        """Get matches with adaptation and learning.
        
        This method handles regex pattern matching based on the context.
        
        Args:
            source_code: Source code to match against
            context: Optional context information
            
        Returns:
            List of matches with extracted information
        """
        await self.initialize()
        start_time = time.time()
        context_key = context.get_context_key() if context else None
        
        try:
            # Check if we should adapt
            if context and self.should_adapt(context):
                await self.adapt_to_context(context)
            
            # Try cache first
            cache_key = f"{hash(source_code)}:{context_key or ''}:{ParserType.CUSTOM.value}"
            cached_result = await self._pattern_cache.get(cache_key)
            if cached_result:
                self.metrics.update(
                    success=bool(cached_result),
                    execution_time=0.001,  # Negligible time for cache hit
                    context_key=context_key,
                    parser_type=ParserType.CUSTOM,
                    pattern_name=self.name,
                    cache_hit=True
                )
                return cached_result
            
            # Extract blocks if available
            blocks = []
            if context and hasattr(context, 'extracted_blocks') and context.extracted_blocks:
                blocks = context.extracted_blocks
            elif source_code:
                # Parse with base parser
                ast = await self._base_parser._parse_source(source_code)
                if ast:
                    blocks = await self._block_extractor.get_child_blocks(
                        self.language_id,
                        source_code,
                        ast["root"] if "root" in ast else ast
                    )
            
            # Get matches from blocks
            matches = []
            memory_before = self._estimate_memory_usage()
            
            if blocks:
                for block in blocks:
                    block_matches = await self._match_block(block, context)
                    if block_matches:
                        matches.extend(block_matches)
            
            # If no blocks or no matches, try full source
            if not matches:
                matches = await self._regex_matches(source_code)
            
            # Calculate memory usage
            memory_usage = self._estimate_memory_usage() - memory_before
            
            # Update metrics
            execution_time = time.time() - start_time
            self.metrics.update(
                success=bool(matches),
                execution_time=execution_time,
                context_key=context_key,
                parser_type=ParserType.CUSTOM,
                pattern_name=self.name,
                memory_usage=memory_usage,
                cache_hit=False
            )
            
            # Cache result
            await self._pattern_cache.set(cache_key, matches)
            
            return matches
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.metrics.update(
                success=False,
                execution_time=execution_time,
                context_key=context_key,
                parser_type=ParserType.CUSTOM,
                pattern_name=self.name
            )
            await log(
                f"Error in adaptive pattern matching: {e}", 
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "parser_type": ParserType.CUSTOM.value
                }
            )
            return []
    
    def _estimate_memory_usage(self) -> int:
        """Estimate current memory usage for tracking."""
        import sys
        import gc
        
        gc.collect()  # Force garbage collection for more accurate measurement
        return sys.getsizeof(self) + sum(sys.getsizeof(obj) for obj in gc.get_objects() 
                                        if hasattr(obj, '__dict__') and id(self) in [id(x) for x in gc.get_referrers(obj)])
    
    async def _regex_matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Get matches using regex pattern."""
        if not hasattr(self, 'regex_pattern') or not self.regex_pattern:
            return []
            
        try:
            import re
            pattern = re.compile(self.regex_pattern, re.MULTILINE | re.DOTALL)
            
            matches = []
            for match in pattern.finditer(source_code):
                match_data = {
                    "match": match,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                    "groups": match.groups(),
                    "named_groups": match.groupdict()
                }
                
                if self.extract:
                    try:
                        extracted = self.extract(match)
                        if extracted:
                            match_data.update(extracted)
                    except Exception as e:
                        await log(f"Error in regex extraction for {self.name}: {e}", level="warning")
                
                matches.append(match_data)
                
            return matches
        except Exception as e:
            await log(f"Error in regex matching for {self.name}: {e}", level="error")
            return []
    
    async def _match_block(
        self,
        block: ExtractedBlock,
        context: Optional[PatternContext]
    ) -> List[Dict[str, Any]]:
        """Match pattern against a code block.
        
        Args:
            block: Extracted code block
            context: Optional context information
            
        Returns:
            List of matches with extracted information
        """
        try:
            # Use regex for matching
            import re
            pattern = re.compile(self.regex_pattern, re.MULTILINE | re.DOTALL)
            
            matches = []
            for match in pattern.finditer(block.content):
                match_data = {
                    "match": match,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                    "groups": match.groups(),
                    "named_groups": match.groupdict(),
                    "block": block.__dict__
                }
                
                if self.extract:
                    try:
                        extracted = self.extract(match)
                        if extracted:
                            match_data.update(extracted)
                    except Exception as e:
                        await log(f"Error in regex block extraction: {e}", level="warning")
                
                matches.append(match_data)
            
            return matches
                
        except Exception as e:
            await log(
                f"Error matching block: {e}", 
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "block_type": getattr(block, 'block_type', 'unknown')
                }
            )
            return []
    
    def should_adapt(self, context: PatternContext) -> bool:
        """Determine if pattern should adapt to context.
        
        Args:
            context: Context information
            
        Returns:
            True if pattern should adapt, False otherwise
        """
        # Check context-specific performance
        if context_key := context.get_context_key():
            if perf := self.metrics.context_performance.get(context_key):
                # Adapt if we have enough data and success rate is low
                return perf["uses"] > 10 and perf["successes"] / perf["uses"] < 0.5
        
        # Check overall performance
        success_rate = self.metrics.get_success_rate(ParserType.CUSTOM)
        if success_rate < 0.5 and self.metrics.parser_stats[ParserType.CUSTOM].get("total", 0) > 10:
            return True
        
        return False
    
    async def adapt_to_context(self, context: PatternContext) -> None:
        """Adapt pattern based on context.
        
        This method adapts the pattern based on the context,
        improving performance for future matches.
        
        Args:
            context: Context information for adaptation
        """
        try:
            await self._adapt_regex_pattern(context)
            
            # Record adaptation
            self.adaptations.append({
                "timestamp": time.time(),
                "context_key": context.get_context_key(),
                "parser_type": ParserType.CUSTOM.value,
                "success_rate_before": self.metrics.success_rate,
                "context_metadata": {
                    "language_id": context.language_id,
                    "file_type": context.file_type.value if hasattr(context.file_type, 'value') else str(context.file_type),
                    "block_types": [bt.value if hasattr(bt, 'value') else str(bt) for bt in context.block_types]
                }
            })
            
            # Update health status
            await global_health_monitor.update_component_status(
                f"adaptive_pattern_{self.name}",
                ComponentStatus.HEALTHY,
                details={
                    "adaptations": len(self.adaptations),
                    "success_rate": self.metrics.success_rate,
                    "last_adapted": time.time()
                }
            )
        except Exception as e:
            await log(
                f"Error adapting pattern: {e}", 
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "parser_type": ParserType.CUSTOM.value
                }
            )
    
    async def _adapt_regex_pattern(self, context: PatternContext) -> None:
        """Adapt regex pattern.
        
        Args:
            context: Context information for adaptation
        """
        if not hasattr(self, 'regex_pattern') or not self.regex_pattern:
            return
            
        # Analyze common patterns in context
        common_patterns = self._analyze_common_patterns(context)
        
        # Modify pattern to better match common patterns
        old_pattern = self.regex_pattern
        self.regex_pattern = self._enhance_regex_pattern(self.regex_pattern, common_patterns)
        
        # Log adaptation if pattern changed
        if old_pattern != self.regex_pattern:
            await log(
                f"Adapted regex pattern for {self.name}", 
                level="info",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "common_patterns": common_patterns[:3] if common_patterns else []
                }
            )
    
    def _analyze_common_patterns(self, context: PatternContext) -> List[str]:
        """Analyze common patterns in context.
        
        Args:
            context: Context information
            
        Returns:
            List of common patterns
        """
        # This is a placeholder for actual analysis logic
        # In a real implementation, you'd analyze the context to identify patterns
        common_patterns = []
        
        if hasattr(context, 'project_patterns'):
            common_patterns = context.project_patterns
            
        return common_patterns
    
    def _enhance_regex_pattern(self, pattern: str, common_patterns: List[str]) -> str:
        """Enhance regex pattern based on common patterns.
        
        Args:
            pattern: Original regex pattern
            common_patterns: Common patterns to incorporate
            
        Returns:
            Enhanced regex pattern
        """
        # This is a placeholder for actual enhancement logic
        # In a real implementation, you'd merge the original pattern with insights
        # from common patterns
        
        # For now, just return the original pattern
        return pattern
    
    def _get_language_id(self, file_path: str) -> str:
        """Get language ID from file path.
        
        Args:
            file_path: Path to source file
            
        Returns:
            Language identifier
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        # Map extensions to language IDs
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'c_sharp',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.html': 'html',
            '.css': 'css',
            '.rs': 'rust',
            '.swift': 'swift',
            '.kt': 'kotlin'
        }
        
        return ext_map.get(ext, 'unknown')
    
    def _get_file_type(self, file_path: str) -> FileType:
        """Get file type from file path.
        
        Args:
            file_path: Path to source file
            
        Returns:
            File type
        """
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path).lower()
        
        # Determine file type
        if ext in ['.py', '.js', '.ts', '.java', '.c', '.cpp', '.cs', '.go', '.rb', '.php', '.rs', '.swift', '.kt']:
            return FileType.SOURCE
        elif ext in ['.h', '.hpp', '.hxx']:
            return FileType.HEADER
        elif ext in ['.json', '.xml', '.yaml', '.yml', '.toml']:
            return FileType.CONFIG
        elif ext in ['.md', '.rst', '.txt']:
            return FileType.DOCUMENTATION
        elif ext in ['.html', '.css']:
            return FileType.MARKUP
        elif filename in ['makefile', 'dockerfile', 'jenkinsfile'] or ext in ['.sh', '.bat', '.ps1']:
            return FileType.BUILD
        elif ext in ['.test.js', '.spec.js', '.test.py', '.spec.py']:
            return FileType.TEST
        else:
            return FileType.OTHER

class CrossProjectPatternLearner:
    """Pattern learner that improves patterns across multiple projects.
    
    This class analyzes patterns across different codebases to generate
    improvements that enhance matching accuracy for custom regex parsers.
    """
    
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
            "regex_improvements": 0,
            "success_rate_before": {},
            "success_rate_after": {},
            "last_update": time.time()
        }
    
    async def initialize(self) -> None:
        """Initialize pattern learner with saved insights."""
        if self.initialized:
            return
            
        # Load previous insights if available
        await self._load_insights()
        self.initialized = True
        
        await log(
            "CrossProjectPatternLearner initialized", 
            level="info",
            context={
                "patterns_count": len(self.patterns),
                "projects_analyzed": self.metrics["projects_analyzed"]
            }
        )
    
    async def learn_from_project(
        self, 
        project_id: str, 
        source_files: List[Dict[str, str]]
    ) -> None:
        """Learn from project source files.
        
        Analyzes code patterns in the provided project and uses them to
        enhance existing regex patterns.
        
        Args:
            project_id: Unique project identifier
            source_files: List of source files with content
        """
        if not self.initialized:
            await self.initialize()
            
        if project_id in self.training_projects:
            # Skip already processed projects
            return
            
        try:
            # Extract patterns from project
            project_patterns = await self._extract_patterns_from_project(source_files)
            
            # Store project insights
            self.project_insights[project_id] = {
                "file_count": len(source_files),
                "pattern_counts": {name: len(instances) for name, instances in project_patterns.items()},
                "timestamp": time.time()
            }
            
            # Update pattern variations with new examples
            for pattern_name, instances in project_patterns.items():
                # Update regex pattern variations
                regex_variations = self._extract_regex_variations(instances)
                for var in regex_variations:
                    if var and var not in self.pattern_variations[pattern_name]:
                        self.pattern_variations[pattern_name].append(var)
            
            # Record project as processed
            self.training_projects.add(project_id)
            self.metrics["projects_analyzed"] += 1
            
            # Save insights to disk
            await self._save_insights()
            
            await log(
                f"Learned from project {project_id}", 
                level="info",
                context={
                    "project_id": project_id,
                    "file_count": len(source_files),
                    "patterns_found": len(project_patterns)
                }
            )
        except Exception as e:
            await log(
                f"Error learning from project {project_id}: {e}", 
                level="error",
                context={"project_id": project_id}
            )
    
    async def apply_improvements(
        self, 
        pattern_names: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Apply learned improvements to patterns.
        
        Args:
            pattern_names: Optional list of pattern names to improve
            
        Returns:
            Dictionary mapping pattern names to whether they were improved
        """
        if not self.initialized:
            await self.initialize()
            
        results = {}
        patterns_to_improve = [p for p in self.patterns 
                              if pattern_names is None or p.name in pattern_names]
        
        for pattern in patterns_to_improve:
            improved = False
            
            # Store original metrics for comparison
            if hasattr(pattern, 'metrics'):
                original_success_rate = pattern.metrics.success_rate
                
            # Apply regex improvements
            regex_improved = await self._improve_regex_pattern(pattern)
            improved = improved or regex_improved
                
            if regex_improved:
                self.metrics["regex_improvements"] += 1
            
            # Record improvement results
            results[pattern.name] = improved
            
            if improved:
                self.metrics["patterns_improved"] += 1
                
                # Compare metrics after improvement
                if hasattr(pattern, 'metrics'):
                    new_success_rate = pattern.metrics.success_rate
                    self.metrics["success_rate_before"][pattern.name] = original_success_rate
                    self.metrics["success_rate_after"][pattern.name] = new_success_rate
                
                await log(
                    f"Improved pattern {pattern.name}", 
                    level="info",
                    context={
                        "pattern": pattern.name
                    }
                )
        
        # Update metrics timestamp
        self.metrics["last_update"] = time.time()
        
        # Save updated insights
        await self._save_insights()
        
        return results
    
    async def _extract_patterns_from_project(
        self, 
        source_files: List[Dict[str, str]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extract patterns from project source files.
        
        Args:
            source_files: List of source files with content
            
        Returns:
            Dictionary mapping pattern names to lists of instances
        """
        extracted_patterns = defaultdict(list)
        
        for file_info in source_files:
            try:
                content = file_info.get("content", "")
                file_path = file_info.get("path", "")
                
                if not content or not file_path:
                    continue
                
                # Determine language from file extension
                language_id = self._get_language_id(file_path)
                
                # Create context with custom parser type
                context = PatternContext(
                    code_structure={},
                    language_id=language_id,
                    file_location=file_path,
                    file_type=self._get_file_type(file_path),
                    parser_type=ParserType.CUSTOM
                )
                
                # Process each pattern
                for pattern in self.patterns:
                    # Skip patterns that don't apply to this language
                    if pattern.language_id not in ["*", language_id]:
                        continue
                    
                    # Get matches from pattern
                    try:
                        matches = await pattern.matches(content, context)
                        
                        # Store pattern instances with metadata
                        for match in matches:
                            instance = {
                                "match": self._clean_match_data(match),
                                "pattern_name": pattern.name,
                                "language_id": language_id,
                                "file_path": file_path
                            }
                            extracted_patterns[pattern.name].append(instance)
                    except Exception as e:
                        await log(
                            f"Error matching pattern {pattern.name}: {e}", 
                            level="warning",
                            context={
                                "pattern": pattern.name,
                                "file_path": file_path,
                                "language_id": language_id
                            }
                        )
            except Exception as e:
                await log(
                    f"Error processing file: {e}", 
                    level="warning",
                    context={"file_path": file_info.get("path", "unknown")}
                )
        
        return dict(extracted_patterns)
    
    def _clean_match_data(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Clean match data for storage.
        
        Args:
            match: Raw match data
            
        Returns:
            Cleaned match data suitable for storage
        """
        cleaned = {}
        
        # Handle regex matches
        if "match" in match and hasattr(match["match"], "group"):
            cleaned["match_text"] = match["match"].group(0)
            cleaned["groups"] = list(match["match"].groups())
            cleaned["named_groups"] = match["match"].groupdict()
        
        # Copy simple fields
        for key, value in match.items():
            if key not in ["match"] and not isinstance(value, (dict, list)):
                cleaned[key] = value
        
        return cleaned
    
    def _extract_regex_variations(self, instances: List[Dict[str, Any]]) -> List[str]:
        """Extract regex pattern variations from instances.
        
        Args:
            instances: List of pattern instances
            
        Returns:
            List of regex pattern variations
        """
        # Group similar text patterns
        grouped_instances = self._group_by_content(instances)
        variations = []
        
        for group in grouped_instances:
            if len(group) < 2:  # Need at least a few examples to generalize
                continue
                
            # Extract match texts
            texts = []
            for instance in group:
                match_data = instance["match"]
                if "match_text" in match_data:
                    texts.append(match_data["match_text"])
                elif "text" in match_data:
                    texts.append(match_data["text"])
            
            if len(texts) >= 2:
                # Generate regex from examples
                variation = self._generate_regex_from_examples(texts)
                if variation:
                    variations.append(variation)
        
        return variations
    
    def _group_by_content(self, instances: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group instances by similar content.
        
        Args:
            instances: List of pattern instances
            
        Returns:
            List of instance groups with similar content
        """
        groups = []
        processed = set()
        
        for i, instance in enumerate(instances):
            if i in processed:
                continue
            
            # Create new group
            group = [instance]
            processed.add(i)
            
            # Find similar instances
            for j, other in enumerate(instances):
                if j in processed:
                    continue
                
                if self._similar_content(instance["match"], other["match"]):
                    group.append(other)
                    processed.add(j)
            
            if len(group) >= 2:
                groups.append(group)
        
        return groups
    
    def _similar_content(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """Check if two matches have similar content.
        
        Args:
            a: First match data
            b: Second match data
            
        Returns:
            True if matches have similar content
        """
        # Get text content from matches
        text_a = a.get("match_text", a.get("text", ""))
        text_b = b.get("match_text", b.get("text", ""))
        
        if not text_a or not text_b:
            return False
        
        # Calculate similarity ratio
        len_diff = abs(len(text_a) - len(text_b)) / max(len(text_a), len(text_b))
        
        # Check for similar patterns
        chars_a = set(text_a)
        chars_b = set(text_b)
        char_similarity = len(chars_a & chars_b) / len(chars_a | chars_b) if chars_a or chars_b else 0
        
        # Check for similar words
        words_a = set(re.findall(r'\w+', text_a))
        words_b = set(re.findall(r'\w+', text_b))
        word_similarity = len(words_a & words_b) / len(words_a | words_b) if words_a or words_b else 0
        
        return len_diff < 0.3 and (char_similarity > 0.7 or word_similarity > 0.5)
    
    def _generate_regex_from_examples(self, examples: List[str]) -> Optional[str]:
        """Generate regex pattern from example texts.
        
        Args:
            examples: List of example texts
            
        Returns:
            Generated regex pattern or None
        """
        if not examples or len(examples) < 2:
            return None
        
        try:
            # Limit number of examples to prevent overfitting
            sample = examples[:5]
            
            # Find common prefix and suffix
            prefix = os.path.commonprefix(sample)
            
            # Find common suffix
            rev_examples = [ex[::-1] for ex in sample]
            rev_suffix = os.path.commonprefix(rev_examples)
            suffix = rev_suffix[::-1]
            
            # Extract variable parts
            variable_parts = []
            for ex in sample:
                if prefix and suffix:
                    middle = ex[len(prefix):-len(suffix) if suffix else None]
                elif prefix:
                    middle = ex[len(prefix):]
                elif suffix:
                    middle = ex[:-len(suffix)]
                else:
                    middle = ex
                variable_parts.append(middle)
            
            # Analyze variable parts
            if all(part.isalnum() for part in variable_parts):
                if all(part.isalpha() for part in variable_parts):
                    var_pattern = r'[a-zA-Z]+'
                elif all(part.isdigit() for part in variable_parts):
                    var_pattern = r'\d+'
                else:
                    var_pattern = r'\w+'
            else:
                var_pattern = r'[^\\s]*'
            
            # Escape special regex characters
            prefix_re = re.escape(prefix)
            suffix_re = re.escape(suffix)
            
            # Build pattern
            pattern = f"{prefix_re}{var_pattern}{suffix_re}"
            
            # Verify pattern matches all examples
            if all(re.match(pattern, ex) for ex in examples):
                return pattern
        except Exception:
            pass
        
        return None
    
    async def _improve_regex_pattern(self, pattern: Union[AdaptivePattern, 'QueryPattern']) -> bool:
        """Apply regex pattern improvements.
        
        Args:
            pattern: Pattern to improve
            
        Returns:
            True if pattern was improved
        """
        # Check if pattern has regex_pattern attribute
        if not hasattr(pattern, 'regex_pattern'):
            return False
        
        # Get pattern variations
        variations = self.pattern_variations.get(pattern.name, [])
        if not variations:
            return False
        
        # Get current regex pattern
        current_regex = getattr(pattern, 'regex_pattern', '')
        
        # Select best variation
        best_variation = None
        best_score = 0
        
        for variation in variations:
            # Skip if variation is identical to current
            if variation == current_regex:
                continue
                
            # Score based on pattern complexity
            score = len(variation) + variation.count('(') + variation.count('[') + variation.count('|')
            if score > best_score:
                best_score = score
                best_variation = variation
        
        if not best_variation:
            return False
        
        # Create or update regex pattern
        if not current_regex:
            pattern.regex_pattern = best_variation
            improved = True
        else:
            # Merge patterns
            merged_pattern = self._merge_regex_patterns(current_regex, best_variation)
            improved = merged_pattern != current_regex
            
            if improved:
                pattern.regex_pattern = merged_pattern
        
        if improved:
            # Record improvement
            self.pattern_improvements[pattern.name].append({
                "type": "regex",
                "original": current_regex,
                "improved": pattern.regex_pattern,
                "timestamp": time.time()
            })
            
            await log(
                f"Applied regex improvement to {pattern.name}", 
                level="info",
                context={
                    "pattern": pattern.name,
                    "original_length": len(current_regex) if current_regex else 0,
                    "improved_length": len(pattern.regex_pattern)
                }
            )
        
        return improved
    
    def _merge_regex_patterns(self, original: str, variation: str) -> str:
        """Merge two regex patterns.
        
        Args:
            original: Original pattern
            variation: Variation to merge
            
        Returns:
            Merged pattern
        """
        # If patterns are identical, return original
        if original == variation:
            return original
            
        # If original is empty, use variation
        if not original:
            return variation
            
        # Combine patterns with alternation
        return f"(?:{original}|{variation})"
    
    def _get_language_id(self, file_path: str) -> str:
        """Get language ID from file path.
        
        Args:
            file_path: Path to source file
            
        Returns:
            Language identifier
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        # Map extensions to language IDs
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'c_sharp',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.html': 'html',
            '.css': 'css',
            '.rs': 'rust',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.ini': 'ini',
            '.editorconfig': 'editorconfig',
            '.adoc': 'asciidoc',
            '.txt': 'plaintext',
            '.co': 'cobalt'
        }
        
        return ext_map.get(ext, 'unknown')
    
    def _get_file_type(self, file_path: str) -> FileType:
        """Get file type from file path.
        
        Args:
            file_path: Path to source file
            
        Returns:
            File type
        """
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path).lower()
        
        # Determine file type
        if ext in ['.py', '.js', '.ts', '.java', '.c', '.cpp', '.cs', '.go', '.rb', '.php', '.rs', '.swift', '.kt']:
            return FileType.SOURCE
        elif ext in ['.h', '.hpp', '.hxx']:
            return FileType.HEADER
        elif ext in ['.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.editorconfig']:
            return FileType.CONFIG
        elif ext in ['.md', '.rst', '.txt', '.adoc']:
            return FileType.DOCUMENTATION
        elif ext in ['.html', '.css']:
            return FileType.MARKUP
        elif filename in ['makefile', 'dockerfile', 'jenkinsfile'] or ext in ['.sh', '.bat', '.ps1']:
            return FileType.BUILD
        elif ext in ['.test.js', '.spec.js', '.test.py', '.spec.py']:
            return FileType.TEST
        else:
            return FileType.OTHER
    
    async def _load_insights(self) -> None:
        """Load previously saved insights."""
        try:
            insights_path = os.path.join(DATA_DIR, "custom_pattern_learner_insights.json")
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
                    "Loaded custom pattern learner insights", 
                    level="info",
                    context={
                        "projects": len(self.project_insights),
                        "improvements": sum(len(imps) for imps in self.pattern_improvements.values())
                    }
                )
        except Exception as e:
            await log(
                f"Could not load custom pattern learner insights: {e}",
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
            insights_path = os.path.join(DATA_DIR, "custom_pattern_learner_insights.json")
            with open(insights_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            await log(
                "Saved custom pattern learner insights",
                level="info"
            )
        except Exception as e:
            await log(
                f"Error saving custom pattern learner insights: {e}",
                level="error"
            )

# Export enhanced pattern types
__all__ = [
    'PatternContext',
    'PatternPerformanceMetrics',
    'AdaptivePattern',
    'CrossProjectPatternLearner',
    'QueryPattern'
] 