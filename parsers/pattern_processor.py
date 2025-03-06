"""[6.0] Pattern processing and validation.

This module provides pattern processing capabilities for code analysis and manipulation,
including AI-assisted pattern processing and validation.
"""

from typing import Dict, Any, List, Union, Callable, Optional, Set
from dataclasses import dataclass, field
import asyncio
from parsers.language_mapping import TREE_SITTER_LANGUAGES, CUSTOM_PARSER_LANGUAGES, normalize_language_name
import re
import time
from parsers.types import (
    ParserType, PatternCategory, PatternPurpose, FileType, 
    PatternDefinition, QueryPattern, AICapability, AIContext, 
    AIProcessingResult, InteractionType, ConfidenceLevel, 
    PatternType, PatternInfo, ExtractedFeatures
)
from parsers.models import PatternMatch, PATTERN_CATEGORIES, ProcessedPattern, QueryResult, AIPatternResult
from parsers.parser_interfaces import AIParserInterface
from utils.logger import log
import os
import importlib
from parsers.language_mapping import is_supported_language
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    ProcessingError,
    AsyncErrorBoundary,
    ErrorSeverity
)
from utils.cache import cache_coordinator, UnifiedCache
from utils.shutdown import register_shutdown_handler
from utils.async_runner import submit_async_task
from db.transaction import transaction_scope
from db.upsert_ops import UpsertCoordinator
from utils.health_monitor import global_health_monitor
from enum import Enum
import numpy as np
from parsers.ai_pattern_processor import get_processor as get_ai_processor
from embedding.embedding_models import code_embedder, doc_embedder, arch_embedder
from custom_parsers.base_imports import *
from .models import PatternRelationship
from db.pattern_storage import PatternStorageMetrics
from db.retry_utils import RetryManager, RetryConfig
from db.transaction import transaction_scope
from ai_tools.pattern_integration import PatternLearningMetrics

# Create coordinator instance
coordinator = None

@dataclass
class FileClassification:
    """Classification information for a file."""
    language_id: str
    parser_type: ParserType
    file_type: FileType
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

class AnalyticsType(Enum):
    """Types of pattern analytics."""
    PERFORMANCE = "performance"
    USAGE = "usage"
    OPTIMIZATION = "optimization"
    TRENDS = "trends"

@dataclass
class PatternAnalytics:
    """Pattern analytics data."""
    pattern_id: str
    language: str
    execution_times: List[float] = field(default_factory=list)
    memory_usage: List[int] = field(default_factory=list)
    usage_count: int = 0
    match_rates: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    
    def add_execution(self, execution_time: float, memory_bytes: int, matches: int):
        """Add execution data."""
        self.execution_times.append(execution_time)
        self.memory_usage.append(memory_bytes)
        self.match_rates.append(matches / max(1, self.usage_count))
        self.timestamps.append(time.time())
        self.usage_count += 1
        
        # Keep history manageable
        max_history = 1000
        if len(self.execution_times) > max_history:
            self.execution_times = self.execution_times[-max_history:]
            self.memory_usage = self.memory_usage[-max_history:]
            self.match_rates = self.match_rates[-max_history:]
            self.timestamps = self.timestamps[-max_history:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get analytics metrics."""
        if not self.execution_times:
            return {}
            
        return {
            'avg_execution_time': np.mean(self.execution_times),
            'max_execution_time': max(self.execution_times),
            'avg_memory_usage': np.mean(self.memory_usage),
            'avg_match_rate': np.mean(self.match_rates),
            'usage_frequency': self.usage_count / (time.time() - min(self.timestamps))
        }

@dataclass
class CompiledPattern:
    """Holds compiled versions (tree-sitter and regex) of a pattern."""
    tree_sitter: Optional[str] = None
    regex: Optional[Union[str, re.Pattern]] = None
    extract: Optional[Callable] = None
    definition: Optional[PatternDefinition] = None
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize pattern resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("pattern initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing pattern: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up pattern resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up pattern: {e}", level="error")

def compile_patterns(pattern_defs: Dict[str, Any]) -> Dict[str, Any]:
    """Compile regex patterns from a pattern definitions dictionary."""
    compiled = {}
    for category, patterns in pattern_defs.items():
        for name, pattern_obj in patterns.items():
            try:
                compiled[name] = re.compile(pattern_obj.pattern, re.DOTALL)
            except Exception as e:
                log(f"Error compiling pattern {name}: {e}", level="error")
    return compiled

@dataclass
class ProcessedPattern:
    """Result of pattern processing with purpose information."""
    pattern_name: str
    category: PatternCategory
    purpose: PatternPurpose
    matches: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

class PatternProcessor(AIParserInterface):
    """[6.1] Pattern processing system with AI capabilities."""
    
    def __init__(self):
        """Initialize pattern processor."""
        super().__init__(
            language_id="pattern_processor",
            file_type=FileType.CODE,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.LEARNING
            }
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._patterns: Dict[str, Dict[str, Any]] = {}
        self._cache = None
        self._lock = asyncio.Lock()
        self._ai_processor = None
        self._metrics = PatternStorageMetrics()
        self._learning_metrics = PatternLearningMetrics()
        self._retry_manager = RetryManager(RetryConfig())
        self._processing_stats = {
            "total_patterns": 0,
            "matched_patterns": 0,
            "failed_patterns": 0
        }
    
    async def ensure_initialized(self):
        """Ensure the processor is initialized."""
        if not self._initialized:
            raise ProcessingError("Pattern processor not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'PatternProcessor':
        """[6.1.1] Create and initialize a pattern processor instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("pattern processor initialization"):
                # Initialize cache
                instance._cache = UnifiedCache("pattern_processor")
                await cache_coordinator.register_cache(instance._cache)
                
                # Load patterns
                await instance._load_patterns()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize AI processor
                instance._ai_processor = await get_ai_processor()
                
                # Initialize embedders
                await code_embedder.initialize()
                await doc_embedder.initialize()
                await arch_embedder.initialize()
                
                instance._initialized = True
                log("Pattern processor initialized with AI integration", level="info")
                return instance
        except Exception as e:
            log(f"Error initializing pattern processor: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize pattern processor: {e}")
    
    async def process_pattern(
        self,
        pattern_name: str,
        source_code: str,
        language_id: str
    ) -> ProcessedPattern:
        """[6.1.2] Process a pattern on source code."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary(f"process_pattern_{pattern_name}"):
            try:
                # Check cache first
                cache_key = f"pattern:{pattern_name}:{hash(source_code)}"
                cached_result = await self._cache.get(cache_key)
                if cached_result:
                    return ProcessedPattern(**cached_result)
                
                # Get pattern definition
                pattern = self._patterns.get(pattern_name)
                if not pattern:
                    raise ProcessingError(f"Pattern {pattern_name} not found")
                
                # Process pattern
                matches = await self._process_pattern_matches(pattern, source_code, language_id)
                
                # Create result
                result = ProcessedPattern(
                    pattern_name=pattern_name,
                    matches=matches,
                    metadata=pattern.get("metadata", {}),
                    error=None
                )
                
                # Cache result
                await self._cache.set(cache_key, result.__dict__)
                
                return result
            except Exception as e:
                log(f"Error processing pattern {pattern_name}: {e}", level="error")
                return ProcessedPattern(
                    pattern_name=pattern_name,
                    matches=[],
                    metadata={},
                    error=str(e)
                )
    
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """[6.1.3] Process patterns with AI assistance."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("pattern processor AI processing"):
            try:
                results = AIProcessingResult(success=True)
                
                # Process with understanding capability
                if AICapability.CODE_UNDERSTANDING in self.capabilities:
                    understanding = await self._process_with_understanding(source_code, context)
                    results.context_info.update(understanding)
                
                # Process with generation capability
                if AICapability.CODE_GENERATION in self.capabilities:
                    generation = await self._process_with_generation(source_code, context)
                    results.suggestions.extend(generation)
                
                # Process with modification capability
                if AICapability.CODE_MODIFICATION in self.capabilities:
                    modification = await self._process_with_modification(source_code, context)
                    results.ai_insights.update(modification)
                
                # Process with review capability
                if AICapability.CODE_REVIEW in self.capabilities:
                    review = await self._process_with_review(source_code, context)
                    results.ai_insights.update(review)
                
                # Process with learning capability
                if AICapability.LEARNING in self.capabilities:
                    learning = await self._process_with_learning(source_code, context)
                    results.learned_patterns.extend(learning)
                
                return results
            except Exception as e:
                log(f"Error in pattern processor AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )
    
    async def _process_with_understanding(
        self,
        source_code: str,
        context: AIContext
    ) -> Dict[str, Any]:
        """[6.1.4] Process with code understanding capability."""
        understanding = {}
        
        # Process patterns by category
        for category in PatternCategory:
            category_patterns = await self._get_patterns_for_category(
                category,
                context.project.file_type
            )
            if category_patterns:
                understanding[category.value] = await self._process_category_patterns(
                    category_patterns,
                    source_code,
                    context
                )
        
        return understanding
    
    async def _process_with_generation(
        self,
        source_code: str,
        context: AIContext
    ) -> List[str]:
        """[6.1.5] Process with code generation capability."""
        suggestions = []
        
        # Get generation patterns
        generation_patterns = await self._get_patterns_for_purpose(
            PatternPurpose.GENERATION,
            context.project.file_type
        )
        
        # Process each pattern
        for pattern in generation_patterns:
            pattern_result = await self.process_pattern(
                pattern["name"],
                source_code,
                context.project.language_id
            )
            if pattern_result.matches:
                suggestions.extend(self._generate_suggestions(pattern_result, context))
        
        return suggestions
    
    async def _process_with_modification(
        self,
        source_code: str,
        context: AIContext
    ) -> Dict[str, Any]:
        """[6.1.6] Process with code modification capability."""
        insights = {}
        
        # Get modification patterns
        modification_patterns = await self._get_patterns_for_purpose(
            PatternPurpose.MODIFICATION,
            context.project.file_type
        )
        
        # Process each pattern
        for pattern in modification_patterns:
            pattern_result = await self.process_pattern(
                pattern["name"],
                source_code,
                context.project.language_id
            )
            if pattern_result.matches:
                insights[pattern["name"]] = await self._analyze_modification_impact(
                    pattern_result,
                    context
                )
        
        return insights
    
    async def _process_with_review(
        self,
        source_code: str,
        context: AIContext
    ) -> Dict[str, Any]:
        """[6.1.7] Process with code review capability."""
        review = {}
        
        # Get review patterns
        review_patterns = await self._get_patterns_for_purpose(
            PatternPurpose.VALIDATION,
            context.project.file_type
        )
        
        # Process each pattern
        for pattern in review_patterns:
            pattern_result = await self.process_pattern(
                pattern["name"],
                source_code,
                context.project.language_id
            )
            if pattern_result.matches:
                review[pattern["name"]] = await self._analyze_review_findings(
                    pattern_result,
                    context
                )
        
        return review
    
    async def _process_with_learning(
        self,
        source_code: str,
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """[6.1.8] Process with learning capability."""
        patterns = []
        
        # Get learning patterns
        learning_patterns = await self._get_patterns_for_purpose(
            PatternPurpose.LEARNING,
            context.project.file_type
        )
        
        # Process each pattern
        for pattern in learning_patterns:
            pattern_result = await self.process_pattern(
                pattern["name"],
                source_code,
                context.project.language_id
            )
            if pattern_result.matches:
                learned = await self._learn_from_pattern(pattern_result, context)
                if learned:
                    patterns.append(learned)
        
        return patterns
    
    async def _load_patterns(self):
        """[6.1.9] Load pattern definitions."""
        try:
            # Load patterns from pattern categories
            for category in PatternCategory:
                for file_type in PATTERN_CATEGORIES.get(category, {}):
                    for purpose, patterns in PATTERN_CATEGORIES[category][file_type].items():
                        for pattern_name in patterns:
                            self._patterns[pattern_name] = {
                                "name": pattern_name,
                                "category": category,
                                "purpose": purpose,
                                "file_type": file_type
                            }
            
            log(f"Loaded {len(self._patterns)} patterns", level="info")
        except Exception as e:
            log(f"Error loading patterns: {e}", level="error")
            raise ProcessingError(f"Failed to load patterns: {e}")
    
    async def cleanup(self):
        """[6.1.10] Clean up processor resources."""
        try:
            if not self._initialized:
                return
                
            # Clear patterns
            self._patterns.clear()
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache(self._cache)
                self._cache = None
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Cleanup AI processor
            self._ai_processor = None
            
            self._initialized = False
            log("Pattern processor cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up pattern processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup pattern processor: {e}")

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return self._processing_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self._processing_stats = {
            "total_patterns": 0,
            "matched_patterns": 0,
            "failed_patterns": 0
        }

    async def process_deep_learning(
        self,
        source_code: str,
        context: AIContext,
        repositories: List[int]
    ) -> AIProcessingResult:
        """Process with deep learning capabilities."""
        results = await self._ai_processor.deep_learn_from_multiple_repositories(
            repositories,
            source_code=source_code,
            context=context
        )
        return AIProcessingResult(
            success=True,
            ai_insights=results
        )

    async def analyze_pattern_relationships(
        self,
        patterns: List[Dict[str, Any]]
    ) -> List[PatternRelationship]:
        """Analyze relationships between patterns."""
        relationships = []
        for i, pattern1 in enumerate(patterns):
            for pattern2 in patterns[i+1:]:
                relationship = await self._analyze_pattern_relationship(
                    pattern1,
                    pattern2
                )
                if relationship:
                    relationships.append(relationship)
        return relationships

    async def track_pattern_execution(self, pattern_id: int, execution_time: float, success: bool) -> None:
        """Track pattern execution metrics."""
        async with transaction_scope() as txn:
            if success:
                self._metrics.total_patterns += 1
                if pattern_id in self._patterns:
                    pattern = self._patterns[pattern_id]
                    if pattern.get("type") == "code":
                        self._metrics.code_patterns += 1
                    elif pattern.get("type") == "doc":
                        self._metrics.doc_patterns += 1
                    elif pattern.get("type") == "arch":
                        self._metrics.arch_patterns += 1
            
            # Track retry statistics if needed
            retry_stats = await self._retry_manager.get_stats()
            if retry_stats["total_retries"] > 0:
                await txn.track_pattern_change(pattern_id, "retry", retry_stats["successful_retries"])

    async def track_learning_progress(self, pattern_type: str, count: int) -> None:
        """Track pattern learning progress."""
        self._learning_metrics.total_patterns_learned += count
        if pattern_type == "code":
            self._learning_metrics.code_patterns_learned += count
        elif pattern_type == "doc":
            self._learning_metrics.doc_patterns_learned += count
        elif pattern_type == "arch":
            self._learning_metrics.arch_patterns_learned += count
        self._learning_metrics.last_update = time.time()

    def get_metrics(self) -> Dict[str, Any]:
        """Get combined pattern metrics."""
        return {
            "storage": self._metrics.__dict__,
            "learning": self._learning_metrics.__dict__,
            "retry": self._retry_manager.get_stats(),
            "processing": self._processing_stats
        }

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics = PatternStorageMetrics()
        self._learning_metrics = PatternLearningMetrics()
        self._retry_manager.reset_stats()
        self._processing_stats = {
            "total_patterns": 0,
            "matched_patterns": 0,
            "failed_patterns": 0
        }

# Global instance
pattern_processor = None

async def get_pattern_processor() -> PatternProcessor:
    """[6.2] Get the global pattern processor instance."""
    global pattern_processor
    if not pattern_processor:
        pattern_processor = await PatternProcessor.create()
    return pattern_processor

async def process_pattern(
    pattern_name: str,
    source_code: str,
    language_id: str
) -> ProcessedPattern:
    """[6.3] Process a pattern on source code."""
    processor = await get_pattern_processor()
    return await processor.process_pattern(pattern_name, source_code, language_id)

async def validate_pattern(
    pattern_name: str,
    source_code: str,
    language_id: str
) -> bool:
    """[6.4] Validate a pattern definition."""
    processor = await get_pattern_processor()
    try:
        result = await processor.process_pattern(pattern_name, source_code, language_id)
        return result.error is None
    except Exception:
        return False

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
    categories = categories or list(PatternCategory)
    
    for category in categories:
        # Get patterns for this category and purpose
        patterns = self._patterns[category][purpose]
        
        # Get valid pattern types for this category/file_type/purpose combo
        valid_types = PATTERN_CATEGORIES.get(category, {}).get(file_type, {}).get(purpose, [])
        
        for pattern_name, pattern in patterns.items():
            if pattern_name in valid_types:
                matches = await self._process_pattern(source_code, pattern)
                if matches:
                    results.append(ProcessedPattern(
                        pattern_name=pattern_name,
                        category=category,
                        purpose=purpose,
                        matches=matches
                    ))
    
    return results

async def _process_pattern(self, source_code: str, pattern: QueryPattern) -> List[Dict[str, Any]]:
    """Process a single pattern against source code."""
    start_time = time.time()
    matches = []
    
    try:
        if isinstance(pattern.pattern, str):
            # Check pattern cache first
            cache_key = f"{pattern.pattern}:{hash(source_code)}"
            if cache_key in self._pattern_cache:
                matches = self._pattern_cache[cache_key]
            else:
                # Regex pattern
                for match in re.finditer(pattern.pattern, source_code, re.MULTILINE | re.DOTALL):
                    result = {
                        'text': match.group(0),
                        'start': match.start(),
                        'end': match.end(),
                        'groups': match.groups(),
                        'named_groups': match.groupdict()
                    }
                    
                    if pattern.extract:
                        try:
                            extracted = pattern.extract(result)
                            if extracted:
                                result.update(extracted)
                        except Exception as e:
                            log(f"Error in pattern extraction: {e}", level="error")
                    
                    matches.append(result)
                
                # Cache the results
                self._pattern_cache[cache_key] = matches
                
                # Keep cache size manageable
                if len(self._pattern_cache) > 1000:  # Arbitrary limit
                    # Remove oldest entries
                    sorted_keys = sorted(
                        self._pattern_cache.keys(),
                        key=lambda k: self._metrics.get(k, {}).get('last_used', 0)
                    )
                    for key in sorted_keys[:100]:  # Remove oldest 100 entries
                        del self._pattern_cache[key]
    finally:
        # Track metrics
        execution_time = time.time() - start_time
        self._track_metrics(pattern.pattern_name, execution_time, len(matches))
    
    return matches

async def suggest_modifications(
    self,
    source_code: str,
    file_type: FileType = FileType.CODE
) -> List[ProcessedPattern]:
    """Find patterns suggesting possible code modifications."""
    return await self.process_for_purpose(
        source_code,
        PatternPurpose.MODIFICATION,
        file_type,
        [PatternCategory.SYNTAX, PatternCategory.CODE_PATTERNS]
    )

async def validate_code(
    self,
    source_code: str,
    file_type: FileType = FileType.CODE
) -> List[ProcessedPattern]:
    """Find patterns related to code validation."""
    return await self.process_for_purpose(
        source_code,
        PatternPurpose.VALIDATION,
        file_type
    )

async def learn_patterns(
    self,
    source_code: str,
    file_type: FileType = FileType.CODE
) -> List[ProcessedPattern]:
    """Extract learning patterns from code."""
    return await self.process_for_purpose(
        source_code,
        PatternPurpose.LEARNING,
        file_type,
        [PatternCategory.LEARNING, PatternCategory.CODE_PATTERNS]
    )

async def understand_code(
    self,
    source_code: str,
    file_type: FileType = FileType.CODE
) -> Dict[PatternCategory, List[ProcessedPattern]]:
    """Analyze code for understanding across all relevant categories."""
    understanding = {}
    
    for category in PatternCategory:
        patterns = await self.process_for_purpose(
            source_code,
            PatternPurpose.UNDERSTANDING,
            file_type,
            [category]
        )
        if patterns:
            understanding[category] = patterns
    
    return understanding

@handle_async_errors(error_types=(Exception,))
async def _ensure_patterns_loaded(self, language: str):
    """Ensure patterns for a language are loaded."""
    if not self._initialized:
        await self.initialize()

    normalized_lang = normalize_language_name(language)
    
    # Check cache only for custom parser patterns
    # Tree-sitter patterns are managed by tree-sitter-language-pack
    if normalized_lang in CUSTOM_PARSER_LANGUAGES:
        cache_key = f"patterns_{normalized_lang}"
        if self._cache:
            cached_patterns = await self._cache.get(cache_key)
            if cached_patterns:
                self._regex_patterns[normalized_lang] = cached_patterns
                self._loaded_languages.add(normalized_lang)
                return
    
    # Skip if already loaded
    if normalized_lang in self._loaded_languages:
        return
        
    # Load the patterns based on parser type
    async with AsyncErrorBoundary(f"load_patterns_{normalized_lang}", error_types=(Exception,)):
        if normalized_lang in TREE_SITTER_LANGUAGES:
            await self._load_tree_sitter_patterns(normalized_lang)
        elif normalized_lang in CUSTOM_PARSER_LANGUAGES:
            await self._load_custom_patterns(normalized_lang)
            
            # Cache only custom parser patterns
            if self._cache and normalized_lang in CUSTOM_PARSER_LANGUAGES:
                await self._cache.set(f"patterns_{normalized_lang}", 
                                    self._regex_patterns[normalized_lang])
        
        # Mark as loaded
        self._loaded_languages.add(normalized_lang)

@handle_async_errors(error_types=(Exception,))
async def _load_tree_sitter_patterns(self, language: str):
    """Load tree-sitter specific patterns for a language."""
    from parsers.query_patterns import get_patterns_for_language
    
    async with AsyncErrorBoundary(f"load_tree_sitter_patterns_{language}"):
        task = asyncio.create_task(get_patterns_for_language(language))
        self._pending_tasks.add(task)
        try:
            patterns = await task
            if patterns:
                # Compile and initialize each pattern
                for pattern_name, pattern in patterns.items():
                    compiled = CompiledPattern(
                        tree_sitter=pattern.get('pattern'),
                        extract=pattern.get('extract'),
                        definition=pattern.get('definition')
                    )
                    await compiled.initialize()
                    patterns[pattern_name] = compiled
                
                self._tree_sitter_patterns[language] = patterns
                log(f"Loaded {len(patterns)} tree-sitter patterns for {language}", level="debug")
        finally:
            self._pending_tasks.remove(task)

@handle_async_errors(error_types=(Exception,))
async def _load_custom_patterns(self, language: str):
    """Load custom parser patterns for a language."""
    from parsers.query_patterns import get_patterns_for_language
    
    async with AsyncErrorBoundary(f"load_custom_patterns_{language}"):
        task = asyncio.create_task(get_patterns_for_language(language))
        self._pending_tasks.add(task)
        try:
            patterns = await task
            if patterns:
                # Compile and initialize each pattern
                for pattern_name, pattern in patterns.items():
                    compiled = CompiledPattern(
                        regex=re.compile(pattern['pattern'], re.DOTALL),
                        extract=pattern.get('extract'),
                        definition=pattern.get('definition')
                    )
                    await compiled.initialize()
                    patterns[pattern_name] = compiled
                
                self._regex_patterns[language] = patterns
                log(f"Loaded {len(patterns)} regex patterns for {language}", level="debug")
        finally:
            self._pending_tasks.remove(task)

@handle_async_errors(error_types=(Exception,))
async def get_patterns_for_file(self, classification: FileClassification) -> dict:
    """
    Get patterns based on parser type and language.
    Ensures patterns are loaded before returning them.
    
    Args:
        classification: File classification containing language and parser type
        
    Returns:
        Dictionary of patterns for the specified language
    """
    if not self._initialized:
        await self.initialize()
        
        async with AsyncErrorBoundary(f"get_patterns_{classification.language_id}"):
            # Make sure patterns are loaded for this language
            await self._ensure_patterns_loaded(classification.language_id)
            
            # Return the appropriate pattern set
            patterns = (self._tree_sitter_patterns if classification.parser_type == ParserType.TREE_SITTER 
                       else self._regex_patterns)
            return patterns.get(classification.language_id, {})
    
    def validate_pattern(self, pattern: CompiledPattern, language: str) -> bool:
        """Validate pattern matches parser type."""
        is_tree_sitter = language in TREE_SITTER_LANGUAGES
        return is_tree_sitter == (pattern.definition.pattern_type == "tree-sitter")

@handle_async_errors(error_types=(Exception,))
async def process_node(self, source_code: str, pattern: CompiledPattern) -> List[PatternMatch]:
    """Process a node using appropriate pattern type."""
    start_time = time.time()
    compilation_time = 0
    matches = []
    
    try:
        # Track compilation time if available
        if hasattr(pattern, 'compilation_time_ms'):
            compilation_time = pattern.compilation_time_ms
        
        if pattern.tree_sitter:
            matches = await self._process_tree_sitter_pattern(source_code, pattern)
        elif pattern.regex:
            matches = await self._process_regex_pattern(source_code, pattern)
        
        # Track pattern execution metrics
        if hasattr(pattern, 'definition') and pattern.definition:
            execution_time_ms = (time.time() - start_time) * 1000
            pattern_id = getattr(pattern.definition, 'id', pattern.definition.name if hasattr(pattern.definition, 'name') else 'unknown')
            await self.track_pattern_execution(
                pattern_id=pattern_id,
                execution_time=execution_time_ms,
                success=len(matches) > 0
            )
    except Exception as e:
        log(f"Error processing pattern: {str(e)}", level="error")
    
    return matches

    @handle_async_errors(error_types=(Exception,))
    async def _process_regex_pattern(self, source_code: str, pattern: CompiledPattern) -> List[PatternMatch]:
        """Process using regex pattern."""
        start_time = time.time()
        matches = []
        
        # Submit regex processing as an async task
        task = asyncio.create_task(self._process_regex_matches(source_code, pattern, start_time))
        self._pending_tasks.add(task)
        try:
            matches = await task
        finally:
            self._pending_tasks.remove(task)
            
        return matches
        
    async def _process_regex_matches(self, source_code: str, pattern: CompiledPattern, start_time: float) -> List[PatternMatch]:
        """Helper method to process regex matches in a separate task."""
        matches = []
        for match in pattern.regex.finditer(source_code):
            result = PatternMatch(
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                metadata={
                    "groups": match.groups(),
                    "named_groups": match.groupdict(),
                    "execution_time_ms": (time.time() - start_time) * 1000
                }
            )
            if pattern.extract:
                async with AsyncErrorBoundary("regex pattern extraction"):
                    result.metadata.update(pattern.extract(result))
            matches.append(result)
        return matches

    @handle_async_errors(error_types=(Exception,))
    async def _process_tree_sitter_pattern(self, source_code: str, pattern: CompiledPattern) -> List[PatternMatch]:
        """Process using tree-sitter pattern."""
        # Pre-import required modules outside the error boundary
        from tree_sitter_language_pack import get_parser
        from parsers.models import PatternMatch
        
        start_time = time.time()
        matches = []
        
        async with AsyncErrorBoundary(f"tree_sitter_pattern_{pattern.language_id if hasattr(pattern, 'language_id') else 'unknown'}"):
            # Get the tree-sitter parser for this language
            parser = get_parser(pattern.language_id)
            if not parser:
                return []
            
            # Parse the source code - tree-sitter-language-pack handles caching
            task = asyncio.create_task(parser.parse(bytes(source_code, "utf8")))
            self._pending_tasks.add(task)
            try:
                tree = await task
            finally:
                self._pending_tasks.remove(task)
                
            if not tree:
                return []
            
            # Execute the tree-sitter query
            query = parser.language.query(pattern.tree_sitter)
            
            # Process matches in a separate task
            task = asyncio.create_task(self._process_tree_sitter_matches(query, tree.root_node, pattern, start_time))
            self._pending_tasks.add(task)
            try:
                matches = await task
            finally:
                self._pending_tasks.remove(task)
            
        return matches
        
    async def _process_tree_sitter_matches(self, query, root_node, pattern: CompiledPattern, start_time: float) -> List[PatternMatch]:
        """Helper method to process tree-sitter matches in a separate task."""
        matches = []
        for match in query.matches(root_node):
            captures = {capture.name: capture.node for capture in match.captures}
            
            # Create a pattern match result
            result = PatternMatch(
                text=match.pattern_node.text.decode('utf8'),
                start=match.pattern_node.start_point,
                end=match.pattern_node.end_point,
                metadata={
                    "captures": captures,
                    "execution_time_ms": (time.time() - start_time) * 1000
                }
            )
            
            # Apply custom extraction if available
            if pattern.extract:
                async with AsyncErrorBoundary("pattern extraction"):
                    extracted = pattern.extract(result)
                    if extracted:
                        result.metadata.update(extracted)
            
            matches.append(result)
            
        return matches

    @handle_async_errors(error_types=(Exception,))
    async def _convert_tree_to_dict(self, node) -> Dict[str, Any]:
        """Convert tree-sitter node to dict asynchronously."""
        if not node:
            return {}
        
        # Process children asynchronously
        children = []
        if node.children:
            tasks = []
            for child in node.children:
                task = asyncio.create_task(self._convert_tree_to_dict(child))
                self._pending_tasks.add(task)
                tasks.append(task)
            
            try:
                children = await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    self._pending_tasks.remove(task)
        
        return {
            'type': node.type,
            'start': node.start_point,
            'end': node.end_point,
            'text': node.text.decode('utf8') if len(node.children) == 0 else None,
            'children': children
        }

    @handle_async_errors(error_types=(Exception,))
    async def compile_patterns(self, pattern_defs: Dict[str, Any]) -> Dict[str, Any]:
        """Compile regex patterns from a pattern definitions dictionary asynchronously."""
        compiled = {}
        tasks = []
        
        for category, patterns in pattern_defs.items():
            for name, pattern_obj in patterns.items():
                task = asyncio.create_task(self._compile_single_pattern(name, pattern_obj))
                self._pending_tasks.add(task)
                tasks.append((name, task))
        
        try:
            for name, task in tasks:
                try:
                    pattern = await task
                    if pattern:
                        compiled[name] = pattern
                except Exception as e:
                    log(f"Error compiling pattern {name}: {str(e)}", level="error")
        finally:
            for _, task in tasks:
                self._pending_tasks.remove(task)
                
        return compiled
        
    async def _compile_single_pattern(self, name: str, pattern_obj: Any) -> Optional[re.Pattern]:
        """Helper method to compile a single pattern in a separate task."""
        async with AsyncErrorBoundary(f"compile_pattern_{name}", error_types=(Exception,)):
            return re.compile(pattern_obj.pattern, re.DOTALL)

    @handle_async_errors(error_types=(Exception,))
    async def extract_repository_patterns(self, file_path: str, source_code: str, language: str) -> List[Dict[str, Any]]:
        """
        Extract patterns from source code for repository learning.
        
        Args:
            file_path: Path to the file (used for language detection if not specified)
            source_code: Source code content
            language: Programming language
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        async with AsyncErrorBoundary("extract_repository_patterns", error_types=(Exception,)):
            # Load the appropriate pattern set based on language
            from parsers.language_mapping import REPOSITORY_LEARNING_PATTERNS
            
            language_rules = REPOSITORY_LEARNING_PATTERNS.get(language, {})
            if not language_rules:
                log(f"No repository learning patterns defined for {language}", level="debug")
                return patterns
                
            # Extract different types of patterns
            structure_patterns = await self._extract_code_structure_patterns(
                source_code, language_rules, language)
            naming_patterns = await self._extract_naming_convention_patterns(
                source_code, language_rules)
            error_patterns = await self._extract_error_handling_patterns(
                source_code, language_rules, language)
            
            # Combine all patterns
            patterns.extend(structure_patterns)
            patterns.extend(naming_patterns)
            patterns.extend(error_patterns)
            
            # Try to extract patterns using tree-sitter if available
            if language in self.tree_sitter_languages:
                try:
                    from tree_sitter_language_pack import get_parser
                    import importlib
                    
                    # Check if we have REPOSITORY_LEARNING section in language patterns
                    pattern_module_name = f"parsers.query_patterns.{language}"
                    learning_patterns = None
                    
                    try:
                        pattern_module = importlib.import_module(pattern_module_name)
                        if hasattr(pattern_module, f"{language.upper()}_PATTERNS"):
                            pattern_dict = getattr(pattern_module, f"{language.upper()}_PATTERNS")
                            learning_patterns = pattern_dict.get("REPOSITORY_LEARNING", {})
                    except (ImportError, AttributeError):
                        pass
                    
                    if learning_patterns:
                        parser = get_parser(language)
                        future = submit_async_task(parser.parse(source_code.encode("utf8")))
                        self._pending_tasks.add(future)
                        try:
                            tree = await asyncio.wrap_future(future)
                        finally:
                            self._pending_tasks.remove(future)
                            
                        root_node = tree.root_node
                        
                        # Process each tree-sitter pattern for learning
                        for pattern_name, pattern_def in learning_patterns.items():
                            if 'pattern' in pattern_def and 'extract' in pattern_def:
                                try:
                                    query = parser.query(pattern_def['pattern'])
                                    
                                    # Process captures using our improved block extractor
                                    future = submit_async_task(self._process_tree_sitter_captures(
                                        query, root_node, pattern_name, pattern_def, language, source_code))
                                    self._pending_tasks.add(future)
                                    try:
                                        capture_patterns = await asyncio.wrap_future(future)
                                        patterns.extend(capture_patterns)
                                    finally:
                                        self._pending_tasks.remove(future)
                                except Exception as e:
                                    log(f"Error processing tree-sitter query for {pattern_name}: {str(e)}", level="error")
                except Exception as e:
                    log(f"Error using tree-sitter for pattern extraction: {str(e)}", level="error")
            
        return patterns
        
    def _process_tree_sitter_captures(self, query, root_node, pattern_name: str, pattern_def: dict, 
                                    language: str, source_code: str) -> List[Dict[str, Any]]:
        """Process tree-sitter captures in a separate task."""
        patterns = []
        for capture in query.captures(root_node):
            capture_name, node = capture
            
            # Extract the pattern content using the block extractor
            block = self.block_extractor.extract_block(language, source_code, node)
            if block and block.content:
                # Create a mock capture result to pass to the extract function
                capture_result = {
                    'node': node,
                    'captures': {capture_name: node},
                    'text': block.content
                }
                
                # Apply the extract function to get metadata
                try:
                    metadata = pattern_def['extract'](capture_result)
                    
                    if metadata:
                        patterns.append({
                            'name': pattern_name,
                            'content': block.content,
                            'pattern_type': metadata.get('type', PatternType.CUSTOM),
                            'language': language,
                            'confidence': 0.95,  # Higher confidence with tree-sitter
                            'metadata': metadata
                        })
                except Exception as e:
                    log(f"Error in extract function for {pattern_name}: {str(e)}", level="error")
        return patterns
        
    @handle_async_errors(error_types=(Exception,))
    async def _extract_code_structure_patterns(self, source_code: str, language_rules: Dict[str, Any], language_id: str = None) -> List[Dict[str, Any]]:
        """Extract code structure patterns from source using regex or tree-sitter queries."""
        patterns = []
        
        async with AsyncErrorBoundary("extract_code_structure", error_types=(Exception,)):
            # Extract classes first
            class_pattern = language_rules.get('class_pattern')
            if class_pattern:
                future = submit_async_task(self._process_class_patterns(source_code, class_pattern, language_id))
                self._pending_tasks.add(future)
                try:
                    class_patterns = await asyncio.wrap_future(future)
                    patterns.extend(class_patterns)
                finally:
                    self._pending_tasks.remove(future)
            
            # Extract functions/methods
            function_pattern = language_rules.get('function_pattern')
            if function_pattern:
                future = submit_async_task(self._process_function_patterns(source_code, function_pattern, language_id))
                self._pending_tasks.add(future)
                try:
                    func_patterns = await asyncio.wrap_future(future)
                    patterns.extend(func_patterns)
                finally:
                    self._pending_tasks.remove(future)
        
        return patterns
    
    def _process_class_patterns(self, source_code: str, class_pattern: str, language_id: str) -> List[Dict[str, Any]]:
        """Process class patterns in a separate task."""
        patterns = []
        class_matches = re.finditer(class_pattern, source_code)
        for match in class_matches:
            class_name = match.group('class_name') if 'class_name' in match.groupdict() else ""
            class_start = match.start()
            
            # Use improved block extraction with language awareness
            class_content = self._extract_block_content(source_code, class_start, language_id)
            
            if class_content:
                patterns.append({
                    'name': f'class_{class_name}',
                    'content': class_content,
                    'pattern_type': PatternType.CLASS_DEFINITION,
                    'language': language_id or 'unknown',
                    'confidence': 0.9,
                    'metadata': {
                        'type': 'class',
                        'name': class_name
                    }
                })
        return patterns
        
    def _process_function_patterns(self, source_code: str, function_pattern: str, language_id: str) -> List[Dict[str, Any]]:
        """Process function patterns in a separate task."""
        patterns = []
        func_matches = re.finditer(function_pattern, source_code)
        for match in func_matches:
            func_name = match.group('func_name') if 'func_name' in match.groupdict() else ""
            func_start = match.start()
            
            # Use improved block extraction with language awareness
            func_content = self._extract_block_content(source_code, func_start, language_id)
            
            if func_content:
                patterns.append({
                    'name': f'function_{func_name}',
                    'content': func_content,
                    'pattern_type': PatternType.FUNCTION_DEFINITION,
                    'language': language_id or 'unknown',
                    'confidence': 0.85,
                    'metadata': {
                        'type': 'function',
                        'name': func_name
                    }
                })
        return patterns
    
    @handle_async_errors(error_types=(Exception,))
    async def _extract_naming_convention_patterns(self, source_code: str, language_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract naming convention patterns."""
        patterns = []
        naming_conventions = language_rules.get('naming_conventions', {})
        
        # Extract variable naming patterns
        if 'variable' in naming_conventions:
            var_pattern = naming_conventions['variable']
            future = submit_async_task(self._process_variable_patterns(source_code, var_pattern, language_rules))
            self._pending_tasks.add(future)
            try:
                var_patterns = await asyncio.wrap_future(future)
                patterns.extend(var_patterns)
            finally:
                self._pending_tasks.remove(future)
        
        return patterns
        
    def _process_variable_patterns(self, source_code: str, var_pattern: str, language_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process variable patterns in a separate task."""
        patterns = []
        var_matches = re.finditer(r'(?<!def\s)(?<!class\s)(?<!import\s)(\b' + var_pattern + r')\s*=', source_code)
        
        var_names = set()
        for match in var_matches:
            var_name = match.group(1)
            if var_name not in var_names:
                var_names.add(var_name)
                patterns.append({
                    'name': f'variable_naming',
                    'content': var_name,
                    'language': language_rules.get('language', 'unknown'),
                    'confidence': 0.7,
                    'metadata': {
                        'type': 'naming_convention',
                        'subtype': 'variable'
                    }
                })
        return patterns
    
    @handle_async_errors(error_types=(Exception,))
    async def _extract_error_handling_patterns(self, source_code: str, language_rules: Dict[str, Any], language_id: str = None) -> List[Dict[str, Any]]:
        """Extract error handling patterns from source."""
        patterns = []
        
        async with AsyncErrorBoundary("extract_error_handling", error_types=(Exception,)):
            # Extract try/catch blocks
            try_pattern = language_rules.get('try_pattern')
            if try_pattern:
                future = submit_async_task(self._process_try_catch_patterns(source_code, try_pattern, language_id))
                self._pending_tasks.add(future)
                try:
                    try_patterns = await asyncio.wrap_future(future)
                    patterns.extend(try_patterns)
                finally:
                    self._pending_tasks.remove(future)
        
        return patterns
        
    def _process_try_catch_patterns(self, source_code: str, try_pattern: str, language_id: str) -> List[Dict[str, Any]]:
        """Process try/catch patterns in a separate task."""
        patterns = []
        try_matches = re.finditer(try_pattern, source_code)
        for match in try_matches:
            try_start = match.start()
            
            # Use improved block extraction with language awareness
            try_block = self._extract_block_content(source_code, try_start, language_id)
            
            if try_block:
                patterns.append({
                    'name': 'error_handling',
                    'content': try_block,
                    'pattern_type': PatternType.ERROR_HANDLING,
                    'language': language_id or 'unknown',
                    'confidence': 0.8,
                    'metadata': {
                        'type': 'try_catch',
                        'has_finally': 'finally' in try_block.lower(),
                        'has_multiple_catches': try_block.lower().count('catch') > 1
                    }
                })
        return patterns

    @handle_async_errors(error_types=(Exception,))
    async def _extract_block_content(self, source_code: str, start_pos: int, language_id: str = None) -> Optional[str]:
        """
        Extract a code block (like function/class body) starting from a position.
        Uses tree-sitter block extraction if available, otherwise falls back to heuristic approach.
        
        Args:
            source_code: The complete source code
            start_pos: Position where the block starts
            language_id: Optional language identifier for language-specific extraction
            
        Returns:
            Extracted block content or None if extraction failed
        """
        async with AsyncErrorBoundary("extract_block_content", error_types=(Exception,)):
            # If we have a language ID and it's supported by tree-sitter, use the block extractor
            if language_id and language_id in self.tree_sitter_languages:
                try:
                    # Use tree-sitter to parse the source and find the node at the position
                    from tree_sitter_language_pack import get_parser
                    parser = get_parser(language_id)
                    if parser:
                        # Parse the source code asynchronously
                        future = submit_async_task(parser.parse(source_code.encode("utf8")))
                        self._pending_tasks.add(future)
                        try:
                            tree = await asyncio.wrap_future(future)
                        finally:
                            self._pending_tasks.remove(future)
                        
                        if not tree:
                            return None
                        
                        # Find the block containing the starting position
                        # Convert start_pos to line and column
                        lines = source_code[:start_pos].splitlines()
                        if not lines:
                            line = 0
                            col = start_pos
                        else:
                            line = len(lines) - 1
                            col = len(lines[-1])
                        
                        # Get the node at the position
                        cursor = tree.root_node.walk()
                        cursor.goto_first_child_for_point((line, col))
                        
                        # Try to extract the block
                        if cursor.node:
                            # Extract block asynchronously
                            future = submit_async_task(self.block_extractor.extract_block(language_id, source_code, cursor.node))
                            self._pending_tasks.add(future)
                            try:
                                block = await asyncio.wrap_future(future)
                                if block and block.content:
                                    return block.content
                            finally:
                                self._pending_tasks.remove(future)
                except Exception as e:
                    log(f"Tree-sitter block extraction failed, falling back to heuristic: {str(e)}", level="debug")
            
            # Fallback to the heuristic approach
            # Submit the heuristic extraction as a task to avoid blocking
            future = submit_async_task(self._extract_block_heuristic(source_code, start_pos))
            self._pending_tasks.add(future)
            try:
                return await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
        
        return None

    def _extract_block_heuristic(self, source_code: str, start_pos: int) -> Optional[str]:
        """Helper method to extract block content using heuristic approach in a separate task."""
        # Find the opening brace or colon
        block_start = source_code.find(':', start_pos)
        if block_start == -1:
            block_start = source_code.find('{', start_pos)
            if block_start == -1:
                return None
                
        # Simple approach to find block end - this is a heuristic
        # and would be better with actual parsing
        lines = source_code[block_start:].splitlines()
        
        if not lines:
            return None
            
        # Handle Python indentation-based blocks
        if source_code[block_start] == ':':
            block_content = [lines[0]]
            initial_indent = len(lines[1]) - len(lines[1].lstrip()) if len(lines) > 1 else 0
            
            for i, line in enumerate(lines[1:], 1):
                if line.strip() and len(line) - len(line.lstrip()) <= initial_indent:
                    break
                block_content.append(line)
                
            return '\n'.join(block_content)
        
        # Handle brace-based blocks
        else:
            brace_count = 1
            block_content = [lines[0]]
            
            for i, line in enumerate(lines[1:], 1):
                block_content.append(line)
                brace_count += line.count('{') - line.count('}')
                
                if brace_count <= 0:
                    break
                    
            return '\n'.join(block_content)

    async def cleanup(self):
        """Clean up processor resources."""
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
            
            # Cleanup cache
            if self._cache:
                await cache_coordinator.unregister_cache(self._cache)
                self._cache = None
            
            # Unregister from health monitoring
            global_health_monitor.unregister_component("pattern_processor")
            
            # Clear pattern dictionaries
            self._tree_sitter_patterns.clear()
            self._regex_patterns.clear()
            self._loaded_languages.clear()
            
            self._initialized = False
            await log("Pattern processor cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up pattern processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup pattern processor: {e}")

    def extract_regex_patterns(self, content: str) -> List[Dict[str, Any]]:
        """Extract regex patterns from content."""
        try:
            patterns = []
            for line in content.splitlines():
                if "re.compile" in line or "regex.compile" in line:
                    pattern = self._extract_pattern_from_line(line)
                    if pattern:
                        patterns.append(pattern)
            return patterns
        except Exception as e:
            log(f"Error extracting regex patterns: {e}", level="error")
            return []

    def extract_patterns(self, content: str) -> List[Dict[str, Any]]:
        """Extract patterns from content."""
        try:
            patterns = []
            # Extract regex patterns
            regex_patterns = self.extract_regex_patterns(content)
            if regex_patterns:
                patterns.extend(regex_patterns)
            
            # Extract other pattern types
            ast_patterns = self._extract_ast_patterns(content)
            if ast_patterns:
                patterns.extend(ast_patterns)
            
            return patterns
        except Exception as e:
            log(f"Error extracting patterns: {e}", level="error")
            return []

    def compile_pattern(self, name: str, pattern: str) -> CompiledPattern:
        """Compile a pattern string into a CompiledPattern object."""
        try:
            return CompiledPattern(
                regex=re.compile(pattern, re.DOTALL),
                definition=PatternDefinition(pattern=pattern)
            )
        except Exception as e:
            log(f"Error compiling pattern {name}: {e}", level="error")
            return None

    async def explain_code(
        self,
        source_code: str,
        file_type: FileType = FileType.CODE
    ) -> List[ProcessedPattern]:
        """Find patterns useful for explaining code to users."""
        return await self.process_for_purpose(
            source_code,
            PatternPurpose.EXPLANATION,
            file_type,
            [PatternCategory.SYNTAX, PatternCategory.SEMANTICS, PatternCategory.CONTEXT]
        )

    async def suggest_improvements(
        self,
        source_code: str,
        file_type: FileType = FileType.CODE
    ) -> List[ProcessedPattern]:
        """Find patterns suggesting possible improvements."""
        return await self.process_for_purpose(
            source_code,
            PatternPurpose.SUGGESTION,
            file_type,
            [PatternCategory.BEST_PRACTICES, PatternCategory.COMMON_ISSUES]
        )

    async def debug_code(
        self,
        source_code: str,
        file_type: FileType = FileType.CODE
    ) -> List[ProcessedPattern]:
        """Find patterns related to potential bugs."""
        return await self.process_for_purpose(
            source_code,
            PatternPurpose.DEBUGGING,
            file_type,
            [PatternCategory.COMMON_ISSUES, PatternCategory.SYNTAX]
        )

    async def complete_code(
        self,
        source_code: str,
        cursor_position: int,
        file_type: FileType = FileType.CODE
    ) -> List[ProcessedPattern]:
        """Find patterns for code completion at cursor position."""
        return await self.process_for_purpose(
            source_code,
            PatternPurpose.COMPLETION,
            file_type,
            [PatternCategory.USER_PATTERNS, PatternCategory.CODE_PATTERNS]
        )

    async def analyze_user_style(
        self,
        source_code: str,
        file_type: FileType = FileType.CODE
    ) -> Dict[str, Any]:
        """Analyze user's coding style and preferences."""
        patterns = await self.process_for_purpose(
            source_code,
            PatternPurpose.UNDERSTANDING,
            file_type,
            [PatternCategory.USER_PATTERNS]
        )
        
        style_info = {
            "naming_conventions": {},
            "formatting_preferences": {},
            "common_patterns": [],
            "documentation_style": {},
            "error_handling_style": {}
        }
        
        for pattern in patterns:
            if "naming" in pattern.pattern_name:
                style_info["naming_conventions"].update(pattern.metadata)
            elif "format" in pattern.pattern_name:
                style_info["formatting_preferences"].update(pattern.metadata)
            elif "pattern" in pattern.pattern_name:
                style_info["common_patterns"].append(pattern.metadata)
            elif "doc" in pattern.pattern_name:
                style_info["documentation_style"].update(pattern.metadata)
            elif "error" in pattern.pattern_name:
                style_info["error_handling_style"].update(pattern.metadata)
        
        return style_info

    async def generate_documentation(
        self,
        source_code: str,
        file_type: FileType = FileType.CODE
    ) -> Dict[str, Any]:
        """Generate documentation based on code patterns."""
        patterns = await self.process_for_purpose(
            source_code,
            PatternPurpose.DOCUMENTATION,
            file_type
        )
        
        docs = {
            "overview": "",
            "functions": [],
            "classes": [],
            "usage_examples": [],
            "dependencies": [],
            "notes": []
        }
        
        for pattern in patterns:
            if pattern.category == PatternCategory.DOCUMENTATION:
                if "overview" in pattern.pattern_name:
                    docs["overview"] = pattern.matches[0]["text"]
                elif "example" in pattern.pattern_name:
                    docs["usage_examples"].extend(
                        match["text"] for match in pattern.matches
                    )
            elif pattern.category == PatternCategory.DEPENDENCIES:
                docs["dependencies"].extend(
                    match["text"] for match in pattern.matches
                )
            elif pattern.category == PatternCategory.SYNTAX:
                if "function" in pattern.pattern_name:
                    docs["functions"].extend(pattern.matches)
                elif "class" in pattern.pattern_name:
                    docs["classes"].extend(pattern.matches)
        
        return docs

    @classmethod
    async def create(cls) -> 'PatternProcessor':
        """Create a pattern processor instance."""
        instance = cls()
        instance._initialized = True
        
        # Create AI-specific processor
        from parsers.ai_pattern_processor import AIPatternProcessor
        instance.ai_processor = AIPatternProcessor(instance)
        
        return instance

    async def process_with_ai(
        self,
        source_code: str,
        context: 'AIAssistantContext'
    ) -> Dict[str, Any]:
        """Process patterns with AI assistance."""
        return await self.ai_processor.process_interaction(source_code, context)

# Global instance
_pattern_processor = None

async def get_pattern_processor() -> PatternProcessor:
    """Get the global pattern processor instance."""
    global _pattern_processor
    if not _pattern_processor:
        _pattern_processor = await PatternProcessor.create()
    return _pattern_processor 