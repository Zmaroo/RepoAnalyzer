"""Query patterns for TOML files.

This module provides TOML-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Union, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from .common import COMMON_PATTERNS, COMMON_CAPABILITIES, process_common_pattern
from .enhanced_patterns import AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
import asyncio
from parsers.pattern_processor import pattern_processor
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import BaseFeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# Language identifier
LANGUAGE = "toml"

# TOML capabilities (extends common capabilities)
TOML_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.CONFIGURATION,
    AICapability.DATA_SERIALIZATION,
    AICapability.STRUCTURED_DATA
}

@dataclass
class TOMLPatternContext(PatternContext):
    """TOML-specific pattern context."""
    table_names: Set[str] = field(default_factory=set)
    key_names: Set[str] = field(default_factory=set)
    array_names: Set[str] = field(default_factory=set)
    has_arrays: bool = False
    has_inline_tables: bool = False
    has_dotted_keys: bool = False
    has_multiline_strings: bool = False
    has_dates: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.table_names)}:{self.has_arrays}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "table": PatternPerformanceMetrics(),
    "key_value": PatternPerformanceMetrics(),
    "array": PatternPerformanceMetrics(),
    "inline_table": PatternPerformanceMetrics(),
    "string": PatternPerformanceMetrics()
}

TOML_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "table": ResilientPattern(
                pattern="""
                [
                    (table
                        name: (_) @syntax.table.name
                        body: (_)* @syntax.table.body) @syntax.table.def,
                    (array_table
                        name: (_) @syntax.array.table.name
                        body: (_)* @syntax.array.table.body) @syntax.array.table.def
                ]
                """,
                extract=lambda node: {
                    "type": "table",
                    "name": (
                        node["captures"].get("syntax.table.name", {}).get("text", "") or
                        node["captures"].get("syntax.array.table.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.table.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.array.table.def", {}).get("start_point", [0])[0]
                    ),
                    "is_array": "syntax.array.table.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["key_value", "array", "inline_table"],
                        PatternRelationType.DEPENDS_ON: ["table"]
                    }
                },
                name="table",
                description="Matches TOML table declarations",
                examples=["[table]", "[[array_table]]"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["table"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_.-]+$'
                    }
                }
            ),
            "key_value": ResilientPattern(
                pattern="""
                [
                    (pair
                        name: (_) @syntax.pair.name
                        value: (_) @syntax.pair.value) @syntax.pair.def,
                    (dotted_key
                        parts: (_)+ @syntax.dotted.parts
                        value: (_) @syntax.dotted.value) @syntax.dotted.def
                ]
                """,
                extract=lambda node: {
                    "type": "key_value",
                    "name": (
                        node["captures"].get("syntax.pair.name", {}).get("text", "") or
                        ".".join(part.get("text", "") for part in node["captures"].get("syntax.dotted.parts", []))
                    ),
                    "line_number": (
                        node["captures"].get("syntax.pair.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.dotted.def", {}).get("start_point", [0])[0]
                    ),
                    "is_dotted": "syntax.dotted.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["table"],
                        PatternRelationType.DEPENDS_ON: ["value"]
                    }
                },
                name="key_value",
                description="Matches TOML key-value pairs",
                examples=["key = value", "server.host = 'localhost'"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["key_value"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_.-]+$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.VALUES: {
            "array": AdaptivePattern(
                pattern="""
                [
                    (array
                        values: (_)* @value.array.items) @value.array.def,
                    (array_table
                        name: (_) @value.array.table.name
                        body: (_)* @value.array.table.body) @value.array.table.def
                ]
                """,
                extract=lambda node: {
                    "type": "array",
                    "line_number": (
                        node["captures"].get("value.array.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("value.array.table.def", {}).get("start_point", [0])[0]
                    ),
                    "is_table": "value.array.table.def" in node["captures"],
                    "table_name": node["captures"].get("value.array.table.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["value"],
                        PatternRelationType.DEPENDS_ON: ["table"]
                    }
                },
                name="array",
                description="Matches TOML array values",
                examples=["values = [1, 2, 3]", "[[products]]"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.VALUES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["array"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            ),
            "inline_table": AdaptivePattern(
                pattern="""
                [
                    (inline_table
                        pairs: (pair
                            name: (_) @value.table.pair.name
                            value: (_) @value.table.pair.value)* @value.table.pairs) @value.table.def
                ]
                """,
                extract=lambda node: {
                    "type": "inline_table",
                    "line_number": node["captures"].get("value.table.def", {}).get("start_point", [0])[0],
                    "pairs": [
                        {
                            "name": name.get("text", ""),
                            "value": value.get("text", "")
                        }
                        for name, value in zip(
                            node["captures"].get("value.table.pair.name", []),
                            node["captures"].get("value.table.pair.value", [])
                        )
                    ],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["key_value"],
                        PatternRelationType.DEPENDS_ON: ["value"]
                    }
                },
                name="inline_table",
                description="Matches TOML inline tables",
                examples=["point = { x = 1, y = 2 }"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.VALUES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["inline_table"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    }
}

class TOMLPatternLearner(CrossProjectPatternLearner):
    """Enhanced TOML pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        super().__init__()
        self._feature_extractor = None
        self._pattern_processor = pattern_processor
        self._ai_processor = None
        self._block_extractor = None
        self._unified_parser = None
        self._metrics = {
            "total_patterns": 0,
            "learned_patterns": 0,
            "failed_patterns": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "learning_times": []
        }
        register_shutdown_handler(self.cleanup)

    async def initialize(self):
        """Initialize with TOML-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("toml", FileType.CONFIG)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register TOML patterns
        await self._pattern_processor.register_language_patterns(
            "toml", 
            TOML_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "toml_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(TOML_PATTERNS),
                "capabilities": list(TOML_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="toml",
                file_type=FileType.CONFIG,
                interaction_type=InteractionType.LEARNING,
                repository_id=None,
                file_path=project_path
            )
            
            ai_result = await self._ai_processor.process_with_ai(
                source_code="",  # Will be filled by processor
                context=ai_context
            )
            
            learned_patterns = []
            if ai_result.success:
                learned_patterns.extend(ai_result.learned_patterns)
                self._metrics["learned_patterns"] += len(ai_result.learned_patterns)
            
            # Then do cross-project learning through base class
            project_patterns = await self._extract_project_patterns(project_path)
            await self._integrate_patterns(project_patterns, project_path)
            learned_patterns.extend(project_patterns)
            
            # Finally add TOML-specific patterns
            async with AsyncErrorBoundary("toml_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "toml",
                    "",  # Will be filled from files
                    None
                )
                
                # Extract features with metrics
                features = []
                for block in blocks:
                    block_features = await self._feature_extractor.extract_features(
                        block.content,
                        block.metadata
                    )
                    features.append(block_features)
                
                # Learn patterns from features
                toml_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(toml_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "toml_pattern_learner",
                ComponentStatus.HEALTHY,
                details={
                    "learned_patterns": len(learned_patterns),
                    "learning_time": learning_time
                }
            )
            
            return learned_patterns
            
        except Exception as e:
            self._metrics["failed_patterns"] += 1
            await log(f"Error learning patterns: {e}", level="error")
            
            # Update health status
            await global_health_monitor.update_component_status(
                "toml_pattern_learner",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": str(e)}
            )
            
            return []

    async def cleanup(self):
        """Clean up pattern learner resources."""
        try:
            # Clean up base class resources
            await super().cleanup()
            
            # Clean up specific components
            if self._feature_extractor:
                await self._feature_extractor.cleanup()
            if self._block_extractor:
                await self._block_extractor.cleanup()
            if self._unified_parser:
                await self._unified_parser.cleanup()
            if self._ai_processor:
                await self._ai_processor.cleanup()
            
            # Update final status
            await global_health_monitor.update_component_status(
                "toml_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "toml_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_toml_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a TOML pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to TOML-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("toml", FileType.CONFIG)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "toml", FileType.CONFIG)
            if parse_result and parse_result.ast:
                context = await create_toml_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"toml_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "toml",
            source_code,
            context.code_structure if context else None
        )
        
        # Process blocks and extract features
        matches = []
        start_time = time.time()
        
        for block in blocks:
            block_matches = await pattern.matches(block.content)
            if block_matches:
                # Extract features for each match
                for match in block_matches:
                    features = await feature_extractor.extract_features(
                        block.content,
                        match
                    )
                    match["features"] = features
                    match["block"] = block.__dict__
                matches.extend(block_matches)
        
        # Cache the result
        await get_current_request_cache().set(cache_key, matches)
        
        # Update pattern metrics
        await update_toml_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "toml_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_toml_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create pattern context with full system integration."""
    # Get unified parser
    unified_parser = await get_unified_parser()
    
    # Parse the code structure if needed
    if not code_structure:
        parse_result = await unified_parser.parse(
            file_path,
            language_id="toml",
            file_type=FileType.CONFIG
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "toml"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(TOML_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_toml_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in PATTERN_METRICS:
        pattern_metrics = PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_toml_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=PATTERN_RELATIONSHIPS.get(pattern_name, []),
        performance=PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "toml"}
    )

# Initialize pattern learner
pattern_learner = TOMLPatternLearner()

async def initialize_toml_patterns():
    """Initialize TOML patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register TOML patterns
    await pattern_processor.register_language_patterns(
        "toml",
        TOML_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": TOML_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await TOMLPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "toml",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "toml_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(TOML_PATTERNS),
            "capabilities": list(TOML_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "table": {
        PatternRelationType.CONTAINS: ["key_value", "array", "inline_table"],
        PatternRelationType.DEPENDS_ON: ["table"]
    },
    "key_value": {
        PatternRelationType.CONTAINED_BY: ["table"],
        PatternRelationType.DEPENDS_ON: ["value"]
    },
    "array": {
        PatternRelationType.CONTAINS: ["value"],
        PatternRelationType.DEPENDS_ON: ["table"]
    },
    "inline_table": {
        PatternRelationType.CONTAINS: ["key_value"],
        PatternRelationType.DEPENDS_ON: ["value"]
    }
}

# Export public interfaces
__all__ = [
    'TOML_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_toml_pattern_match_result',
    'update_toml_pattern_metrics',
    'TOMLPatternContext',
    'pattern_learner'
] 