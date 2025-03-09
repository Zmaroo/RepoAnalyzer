"""Dart-specific patterns with enhanced type system and relationships.

This module provides Dart-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType
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

# Dart capabilities (extends common capabilities)
DART_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.FLUTTER_SUPPORT,
    AICapability.MOBILE_DEVELOPMENT,
    AICapability.ASYNC_SUPPORT
}

# Pattern relationships for Dart
DART_PATTERN_RELATIONSHIPS = {
    "class_definition": [
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="method_definition",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.95,
            metadata={"methods": True}
        ),
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "method_definition": [
        PatternRelationship(
            source_pattern="method_definition",
            target_pattern="type_annotation",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"types": True}
        )
    ],
    "widget": [
        PatternRelationship(
            source_pattern="widget",
            target_pattern="build_method",
            relationship_type=PatternRelationType.REQUIRES,
            confidence=0.95,
            metadata={"flutter": True}
        )
    ]
}

# Performance metrics tracking for Dart patterns
DART_PATTERN_METRICS = {
    "class_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "method_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "widget": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced Dart patterns with proper typing and relationships
DART_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class_definition": ResilientPattern(
                name="class_definition",
                pattern="""
                [
                    (class_declaration
                        metadata: (metadata)* @syntax.class.metadata
                        modifiers: [(abstract)]* @syntax.class.modifier
                        name: (identifier) @syntax.class.name
                        type_parameters: (type_parameters)? @syntax.class.type_params
                        superclass: (superclass)? @syntax.class.extends
                        interfaces: (interfaces)? @syntax.class.implements
                        mixins: (mixins)? @syntax.class.with
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                        
                    (mixin_declaration
                        metadata: (metadata)* @syntax.mixin.metadata
                        name: (identifier) @syntax.mixin.name
                        on: (on_clause)? @syntax.mixin.on
                        interfaces: (interfaces)? @syntax.mixin.implements
                        body: (class_body) @syntax.mixin.body) @syntax.mixin.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
                confidence=0.95,
                metadata={
                    "relationships": DART_PATTERN_RELATIONSHIPS["class_definition"],
                    "metrics": DART_PATTERN_METRICS["class_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "method_definition": ResilientPattern(
                name="method_definition",
                pattern="""
                [
                    (method_declaration
                        metadata: (metadata)* @syntax.method.metadata
                        modifiers: [(static) (abstract) (external)]* @syntax.method.modifier
                        return_type: (_)? @syntax.method.return_type
                        name: (identifier) @syntax.method.name
                        parameters: (formal_parameter_list) @syntax.method.params
                        body: [(block) (arrow_body)]? @syntax.method.body) @syntax.method.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
                confidence=0.95,
                metadata={
                    "relationships": DART_PATTERN_RELATIONSHIPS["method_definition"],
                    "metrics": DART_PATTERN_METRICS["method_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "async": AdaptivePattern(
                name="async",
                pattern="""
                [
                    (function_declaration
                        body: (block
                            (async_marker) @semantics.async.marker)) @semantics.async.function,
                            
                    (method_declaration
                        body: (block
                            (async_marker) @semantics.async.method.marker)) @semantics.async.method,
                            
                    (await_expression
                        expression: (_) @semantics.async.await.expr) @semantics.async.await,
                        
                    (yield_statement
                        expression: (_)? @semantics.async.yield.expr) @semantics.async.yield
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "widget": ResilientPattern(
                name="widget",
                pattern="""
                [
                    (class_declaration
                        metadata: (metadata
                            (identifier) @semantics.widget.annotation
                            (#match? @semantics.widget.annotation "^Widget$")) @semantics.widget.metadata
                        name: (identifier) @semantics.widget.name) @semantics.widget.class,
                        
                    (method_declaration
                        name: (identifier) @semantics.widget.build
                        (#match? @semantics.widget.build "^build$")
                        body: (block
                            (return_statement
                                expression: (_) @semantics.widget.build.return))) @semantics.widget.build_method
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
                confidence=0.95,
                metadata={
                    "relationships": DART_PATTERN_RELATIONSHIPS["widget"],
                    "metrics": DART_PATTERN_METRICS["widget"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comments": AdaptivePattern(
                name="comments",
                pattern="""
                [
                    (comment) @documentation.comment,
                    (documentation_comment
                        content: (_)* @documentation.doc.content) @documentation.doc,
                    (documentation_comment
                        reference: (identifier) @documentation.doc.reference) @documentation.doc.ref
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dart",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="class_definition",
                            relationship_type=PatternRelationType.COMPLEMENTS,
                            confidence=0.8
                        )
                    ],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    }
}

def create_pattern_context(file_path: str, code_structure: Dict[str, Any]) -> PatternContext:
    """Create pattern context for Dart files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "dart", "version": "2.19+"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(DART_PATTERNS.keys())
    )

def get_dart_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return DART_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_dart_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in DART_PATTERN_METRICS:
        pattern_metrics = DART_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_dart_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_dart_pattern_relationships(pattern_name),
        performance=DART_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "dart"}
    )

class DartPatternLearner(CrossProjectPatternLearner):
    """Enhanced Dart pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Dart-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("dart", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Dart patterns
        await self._pattern_processor.register_language_patterns(
            "dart", 
            DART_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "dart_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(DART_PATTERNS),
                "capabilities": list(DART_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="dart",
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
            
            # Finally add Dart-specific patterns
            async with AsyncErrorBoundary("dart_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "dart",
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
                dart_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(dart_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "dart_pattern_learner",
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
                "dart_pattern_learner",
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
                "dart_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "dart_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_dart_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Dart pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Dart-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("dart", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "dart", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_dart_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"dart_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "dart",
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
        await update_dart_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "dart_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_dart_pattern_context(
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
            language_id="dart",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "dart", "version": "2.19+"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(DART_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

# Initialize pattern learner
dart_pattern_learner = DartPatternLearner()

async def initialize_dart_patterns():
    """Initialize Dart patterns during app startup."""
    global dart_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Dart patterns
    await pattern_processor.register_language_patterns(
        "dart",
        DART_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": DART_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    dart_pattern_learner = await DartPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "dart",
        dart_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "dart_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(DART_PATTERNS),
            "capabilities": list(DART_CAPABILITIES)
        }
    )

# Export public interfaces
__all__ = [
    'DART_PATTERNS',
    'DART_PATTERN_RELATIONSHIPS',
    'DART_PATTERN_METRICS',
    'create_pattern_context',
    'get_dart_pattern_relationships',
    'update_dart_pattern_metrics',
    'get_dart_pattern_match_result'
] 