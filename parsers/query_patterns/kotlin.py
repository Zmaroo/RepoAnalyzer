"""Query patterns for Kotlin files.

This module provides Kotlin-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "kotlin"

# Kotlin capabilities (extends common capabilities)
KOTLIN_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.OBJECT_ORIENTED,
    AICapability.COROUTINES,
    AICapability.FUNCTIONAL_PROGRAMMING
}

@dataclass
class KotlinPatternContext(PatternContext):
    """Kotlin-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    property_names: Set[str] = field(default_factory=set)
    interface_names: Set[str] = field(default_factory=set)
    has_coroutines: bool = False
    has_data_classes: bool = False
    has_sealed_classes: bool = False
    has_extension_functions: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_coroutines}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "property": PatternPerformanceMetrics(),
    "interface": PatternPerformanceMetrics(),
    "coroutine": PatternPerformanceMetrics()
}

KOTLIN_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_declaration
                        name: (type_identifier) @syntax.class.name
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                    (data_class_declaration
                        name: (type_identifier) @syntax.data.name
                        body: (class_body) @syntax.data.body) @syntax.data.def,
                    (sealed_class_declaration
                        name: (type_identifier) @syntax.sealed.name
                        body: (class_body) @syntax.sealed.body) @syntax.sealed.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.data.name", {}).get("text", "") or
                        node["captures"].get("syntax.sealed.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0],
                    "is_data_class": "syntax.data.def" in node["captures"],
                    "is_sealed_class": "syntax.sealed.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["property", "function"],
                        PatternRelationType.DEPENDS_ON: ["interface", "class"]
                    }
                },
                name="class",
                description="Matches class declarations",
                examples=["class MyClass", "data class User(val name: String)", "sealed class Result"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["class"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": ResilientPattern(
                pattern="""
                [
                    (function_declaration
                        name: (simple_identifier) @syntax.func.name
                        parameters: (parameter_list) @syntax.func.params
                        body: (function_body) @syntax.func.body) @syntax.func.def,
                    (extension_function_declaration
                        name: (simple_identifier) @syntax.ext.name
                        parameters: (parameter_list) @syntax.ext.params
                        body: (function_body) @syntax.ext.body) @syntax.ext.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.ext.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_extension": "syntax.ext.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["class", "interface"]
                    }
                },
                name="function",
                description="Matches function declarations",
                examples=["fun hello()", "fun String.addPrefix()"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.COROUTINES: {
            "coroutine": AdaptivePattern(
                pattern="""
                [
                    (function_declaration
                        modifiers: (modifiers
                            (suspend_modifier) @coroutine.suspend) @coroutine.mods
                        name: (simple_identifier) @coroutine.func.name
                        parameters: (parameter_list) @coroutine.func.params
                        body: (function_body) @coroutine.func.body) @coroutine.func,
                        
                    (call_expression
                        function: [
                            (simple_identifier) @coroutine.launch.name,
                            (navigation_expression
                                receiver: (simple_identifier) @coroutine.scope.name
                                name: (simple_identifier) @coroutine.launch.name)
                        ]
                        arguments: (call_suffix
                            (lambda_literal) @coroutine.launch.body)) @coroutine.launch
                ]
                """,
                extract=lambda node: {
                    "type": "coroutine",
                    "line_number": node["captures"].get("coroutine.func", {}).get("start_point", [0])[0],
                    "is_suspend_function": "coroutine.suspend" in node["captures"],
                    "is_coroutine_builder": (
                        node["captures"].get("coroutine.launch.name", {}).get("text", "") in
                        {"launch", "async", "runBlocking", "withContext"}
                    ),
                    "coroutine_scope": node["captures"].get("coroutine.scope.name", {}).get("text", ""),
                    "function_name": node["captures"].get("coroutine.func.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["block"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="coroutine",
                description="Matches coroutine-related code",
                examples=["suspend fun fetch()", "launch { delay(1000) }"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.COROUTINES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["coroutine"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-z][a-zA-Z0-9_]*$'
                    }
                }
            )
        },
        PatternPurpose.PROPERTIES: {
            "property": AdaptivePattern(
                pattern="""
                [
                    (property_declaration
                        modifiers: (modifiers)? @prop.mods
                        name: (simple_identifier) @prop.name
                        type: (type_reference)? @prop.type
                        (property_delegate)? @prop.delegate
                        (getter)? @prop.getter
                        (setter)? @prop.setter) @prop.decl,
                        
                    (class_parameter
                        modifiers: (modifiers)? @param.mods
                        name: (simple_identifier) @param.name
                        type: (type_reference) @param.type) @param.decl
                ]
                """,
                extract=lambda node: {
                    "type": "property",
                    "name": (
                        node["captures"].get("prop.name", {}).get("text", "") or
                        node["captures"].get("param.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("prop.decl", {}).get("start_point", [0])[0],
                    "has_custom_accessors": (
                        "prop.getter" in node["captures"] or
                        "prop.setter" in node["captures"]
                    ),
                    "is_delegated": "prop.delegate" in node["captures"],
                    "is_constructor_param": "param.decl" in node["captures"],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["class"],
                        PatternRelationType.REFERENCES: ["property"]
                    }
                },
                name="property",
                description="Matches property declarations",
                examples=["val name: String", "var count by Delegates.observable(0)"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PROPERTIES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["property"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

class KotlinPatternLearner(CrossProjectPatternLearner):
    """Enhanced Kotlin pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Kotlin-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("kotlin", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Kotlin patterns
        await self._pattern_processor.register_language_patterns(
            "kotlin", 
            KOTLIN_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "kotlin_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(KOTLIN_PATTERNS),
                "capabilities": list(KOTLIN_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="kotlin",
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
            
            # Finally add Kotlin-specific patterns
            async with AsyncErrorBoundary("kotlin_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "kotlin",
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
                kotlin_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(kotlin_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "kotlin_pattern_learner",
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
                "kotlin_pattern_learner",
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
                "kotlin_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "kotlin_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_kotlin_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Kotlin pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Kotlin-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("kotlin", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "kotlin", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_kotlin_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"kotlin_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "kotlin",
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
        await update_kotlin_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "kotlin_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_kotlin_pattern_context(
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
            language_id="kotlin",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "kotlin"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(KOTLIN_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_kotlin_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_kotlin_pattern_match_result(
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
        metadata={"language": "kotlin"}
    )

# Initialize pattern learner
pattern_learner = KotlinPatternLearner()

async def initialize_kotlin_patterns():
    """Initialize Kotlin patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Kotlin patterns
    await pattern_processor.register_language_patterns(
        "kotlin",
        KOTLIN_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": KOTLIN_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await KotlinPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "kotlin",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "kotlin_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(KOTLIN_PATTERNS),
            "capabilities": list(KOTLIN_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["property", "function"],
        PatternRelationType.DEPENDS_ON: ["interface", "class"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["class", "interface"]
    },
    "property": {
        PatternRelationType.DEPENDS_ON: ["class"],
        PatternRelationType.REFERENCES: ["property"]
    },
    "interface": {
        PatternRelationType.CONTAINS: ["function"],
        PatternRelationType.REFERENCED_BY: ["class"]
    },
    "coroutine": {
        PatternRelationType.CONTAINS: ["block"],
        PatternRelationType.DEPENDS_ON: ["function"]
    }
}

# Export public interfaces
__all__ = [
    'KOTLIN_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_kotlin_pattern_match_result',
    'update_kotlin_pattern_metrics',
    'KotlinPatternContext',
    'pattern_learner'
] 