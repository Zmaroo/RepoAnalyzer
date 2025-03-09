"""Query patterns for Rust files.

This module provides Rust-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "rust"

# Rust capabilities (extends common capabilities)
RUST_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.MEMORY_SAFETY,
    AICapability.CONCURRENCY,
    AICapability.TRAITS
}

@dataclass
class RustPatternContext(PatternContext):
    """Rust-specific pattern context."""
    struct_names: Set[str] = field(default_factory=set)
    enum_names: Set[str] = field(default_factory=set)
    trait_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    has_generics: bool = False
    has_lifetimes: bool = False
    has_unsafe: bool = False
    has_async: bool = False
    has_macros: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.struct_names)}:{self.has_generics}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "struct": PatternPerformanceMetrics(),
    "enum": PatternPerformanceMetrics(),
    "trait": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics()
}

RUST_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "struct": ResilientPattern(
                pattern="""
                [
                    (struct_item
                        name: (type_identifier) @syntax.struct.name
                        type_parameters: (type_parameters)? @syntax.struct.generics
                        fields: (field_declaration_list)? @syntax.struct.fields) @syntax.struct.def,
                    (struct_item
                        name: (type_identifier) @syntax.tuple.struct.name
                        type_parameters: (type_parameters)? @syntax.tuple.struct.generics
                        fields: (tuple_field_declaration_list)? @syntax.tuple.struct.fields) @syntax.tuple.struct.def
                ]
                """,
                extract=lambda node: {
                    "type": "struct",
                    "name": (
                        node["captures"].get("syntax.struct.name", {}).get("text", "") or
                        node["captures"].get("syntax.tuple.struct.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.struct.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.tuple.struct.def", {}).get("start_point", [0])[0]
                    ),
                    "has_generics": (
                        "syntax.struct.generics" in node["captures"] or
                        "syntax.tuple.struct.generics" in node["captures"]
                    ),
                    "is_tuple": "syntax.tuple.struct.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["field", "impl", "trait"],
                        PatternRelationType.DEPENDS_ON: ["type", "module"]
                    }
                },
                name="struct",
                description="Matches Rust struct declarations",
                examples=["struct Point<T> { x: T, y: T }", "struct Tuple(i32, String);"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["struct"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "enum": ResilientPattern(
                pattern="""
                [
                    (enum_item
                        name: (type_identifier) @syntax.enum.name
                        type_parameters: (type_parameters)? @syntax.enum.generics
                        variants: (enum_variant_list)? @syntax.enum.variants) @syntax.enum.def
                ]
                """,
                extract=lambda node: {
                    "type": "enum",
                    "name": node["captures"].get("syntax.enum.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.enum.def", {}).get("start_point", [0])[0],
                    "has_generics": "syntax.enum.generics" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["variant", "impl", "trait"],
                        PatternRelationType.DEPENDS_ON: ["type", "module"]
                    }
                },
                name="enum",
                description="Matches Rust enum declarations",
                examples=["enum Option<T> { Some(T), None }", "enum Color { Red, Green, Blue }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["enum"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "trait": ResilientPattern(
                pattern="""
                [
                    (trait_item
                        name: (type_identifier) @syntax.trait.name
                        type_parameters: (type_parameters)? @syntax.trait.generics
                        bounds: (trait_bounds)? @syntax.trait.bounds
                        body: (declaration_list)? @syntax.trait.body) @syntax.trait.def,
                    (impl_item
                        trait: (type_identifier) @syntax.impl.trait.name
                        type: (type_identifier) @syntax.impl.type
                        body: (declaration_list)? @syntax.impl.body) @syntax.impl.def
                ]
                """,
                extract=lambda node: {
                    "type": "trait",
                    "name": (
                        node["captures"].get("syntax.trait.name", {}).get("text", "") or
                        node["captures"].get("syntax.impl.trait.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.trait.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.impl.def", {}).get("start_point", [0])[0]
                    ),
                    "has_generics": "syntax.trait.generics" in node["captures"],
                    "has_bounds": "syntax.trait.bounds" in node["captures"],
                    "is_impl": "syntax.impl.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["function", "type", "const"],
                        PatternRelationType.DEPENDS_ON: ["trait", "module"]
                    }
                },
                name="trait",
                description="Matches Rust trait declarations and implementations",
                examples=["trait Display { fn fmt(&self) -> String; }", "impl Debug for Point"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["trait"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.FUNCTIONS: {
            "function": AdaptivePattern(
                pattern="""
                [
                    (function_item
                        name: (identifier) @syntax.func.name
                        parameters: (parameters)? @syntax.func.params
                        return_type: (type_identifier)? @syntax.func.return
                        body: (block)? @syntax.func.body) @syntax.func.def,
                    (function_item
                        attributes: (attribute_item)* @syntax.async.func.attrs
                        name: (identifier) @syntax.async.func.name
                        parameters: (parameters)? @syntax.async.func.params
                        return_type: (type_identifier)? @syntax.async.func.return
                        body: (block)? @syntax.async.func.body) @syntax.async.func.def
                        (#match? @syntax.async.func.attrs "async")
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.async.func.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.async.func.def", {}).get("start_point", [0])[0]
                    ),
                    "is_async": "syntax.async.func.def" in node["captures"],
                    "has_params": (
                        "syntax.func.params" in node["captures"] or
                        "syntax.async.func.params" in node["captures"]
                    ),
                    "has_return_type": (
                        "syntax.func.return" in node["captures"] or
                        "syntax.async.func.return" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["block", "statement"],
                        PatternRelationType.DEPENDS_ON: ["type", "module"]
                    }
                },
                name="function",
                description="Matches Rust function declarations",
                examples=["fn process(data: &str) -> Result<(), Error>", "async fn handle() -> String"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.FUNCTIONS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        },
        PatternPurpose.MODULES: {
            "module": AdaptivePattern(
                pattern="""
                [
                    (mod_item
                        name: (identifier) @syntax.mod.name
                        body: (declaration_list)? @syntax.mod.body) @syntax.mod.def,
                    (use_declaration
                        path: (scoped_identifier
                            path: (identifier) @syntax.use.path
                            name: (identifier) @syntax.use.name)) @syntax.use.def
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "name": (
                        node["captures"].get("syntax.mod.name", {}).get("text", "") or
                        node["captures"].get("syntax.use.path", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.mod.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.use.def", {}).get("start_point", [0])[0]
                    ),
                    "is_use": "syntax.use.def" in node["captures"],
                    "imported_name": node["captures"].get("syntax.use.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["struct", "enum", "trait", "function"],
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="module",
                description="Matches Rust module declarations and imports",
                examples=["mod config;", "use std::io::Result;"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.MODULES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["module"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

class RustPatternLearner(CrossProjectPatternLearner):
    """Enhanced Rust pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Rust-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("rust", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Rust patterns
        await self._pattern_processor.register_language_patterns(
            "rust", 
            RUST_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "rust_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(RUST_PATTERNS),
                "capabilities": list(RUST_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="rust",
                file_type=FileType.CODE,
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
            
            # Finally add Rust-specific patterns
            async with AsyncErrorBoundary("rust_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "rust",
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
                rust_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(rust_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "rust_pattern_learner",
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
                "rust_pattern_learner",
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
                "rust_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "rust_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_rust_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Rust pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Rust-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("rust", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "rust", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_rust_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"rust_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "rust",
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
        await update_rust_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "rust_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_rust_pattern_context(
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
            language_id="rust",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "rust"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(RUST_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_rust_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_rust_pattern_match_result(
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
        metadata={"language": "rust"}
    )

# Initialize pattern learner
pattern_learner = RustPatternLearner()

async def initialize_rust_patterns():
    """Initialize Rust patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Rust patterns
    await pattern_processor.register_language_patterns(
        "rust",
        RUST_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": RUST_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await RustPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "rust",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "rust_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(RUST_PATTERNS),
            "capabilities": list(RUST_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "struct": {
        PatternRelationType.CONTAINS: ["field", "impl", "trait"],
        PatternRelationType.DEPENDS_ON: ["type", "module"]
    },
    "enum": {
        PatternRelationType.CONTAINS: ["variant", "impl", "trait"],
        PatternRelationType.DEPENDS_ON: ["type", "module"]
    },
    "trait": {
        PatternRelationType.CONTAINS: ["function", "type", "const"],
        PatternRelationType.DEPENDS_ON: ["trait", "module"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["block", "statement"],
        PatternRelationType.DEPENDS_ON: ["type", "module"]
    },
    "module": {
        PatternRelationType.CONTAINS: ["struct", "enum", "trait", "function"],
        PatternRelationType.DEPENDS_ON: ["module"]
    }
}

# Export public interfaces
__all__ = [
    'RUST_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_rust_pattern_match_result',
    'update_rust_pattern_metrics',
    'RustPatternContext',
    'pattern_learner'
] 