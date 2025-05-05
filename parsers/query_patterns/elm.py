"""Elm-specific patterns with enhanced type system and relationships.

This module provides Elm-specific patterns that integrate with the enhanced
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
from .enhanced_patterns import TreeSitterAdaptivePattern, TreeSitterResilientPattern, TreeSitterCrossProjectPatternLearner
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
import asyncio
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import FeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# Elm capabilities (extends common capabilities)
ELM_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.FUNCTIONAL_PROGRAMMING,
    AICapability.TYPE_INFERENCE,
    AICapability.WEB_DEVELOPMENT
}

# Pattern relationships for Elm
ELM_PATTERN_RELATIONSHIPS = {
    "function": [
        PatternRelationship(
            source_pattern="function",
            target_pattern="type",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"type_annotation": True}
        ),
        PatternRelationship(
            source_pattern="function",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "type": [
        PatternRelationship(
            source_pattern="type",
            target_pattern="type_variable",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"type_variables": True}
        ),
        PatternRelationship(
            source_pattern="type",
            target_pattern="constructor",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"constructors": True}
        )
    ],
    "module": [
        PatternRelationship(
            source_pattern="module",
            target_pattern="import",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"imports": True}
        ),
        PatternRelationship(
            source_pattern="module",
            target_pattern="export",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"exports": True}
        )
    ]
}

# Performance metrics tracking for Elm patterns
ELM_PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "type": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "module": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced Elm patterns with proper typing and relationships
ELM_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": TreeSitterResilientPattern(
                name="function",
                pattern="""
                (value_declaration
                  pattern: (lower_pattern) @syntax.function.name
                  type_annotation: (type_annotation)? @syntax.function.type
                  value: (value_expr) @syntax.function.body) @syntax.function.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
                confidence=0.95,
                metadata={
                    "relationships": ELM_PATTERN_RELATIONSHIPS["function"],
                    "metrics": ELM_PATTERN_METRICS["function"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "type": TreeSitterResilientPattern(
                name="type",
                pattern="""
                [
                    (type_declaration
                        name: (upper_case_identifier) @syntax.type.name
                        type_variables: (lower_pattern)* @syntax.type.type_vars
                        constructors: (union_variant)+ @syntax.type.constructors) @syntax.type.def,
                    (type_alias_declaration
                        name: (upper_case_identifier) @syntax.type.name
                        type_variables: (lower_pattern)* @syntax.type.type_vars
                        type_expression: (_) @syntax.type.type) @syntax.type.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
                confidence=0.95,
                metadata={
                    "relationships": ELM_PATTERN_RELATIONSHIPS["type"],
                    "metrics": ELM_PATTERN_METRICS["type"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "module": TreeSitterResilientPattern(
                name="module",
                pattern="""
                (module_declaration
                    name: (upper_case_qid) @structure.module.name
                    exposing: (exposed_values)? @structure.module.exports) @structure.module.def
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
                confidence=0.95,
                metadata={
                    "relationships": ELM_PATTERN_RELATIONSHIPS["module"],
                    "metrics": ELM_PATTERN_METRICS["module"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "import": TreeSitterAdaptivePattern(
                name="import",
                pattern="""
                (import_declaration
                    module_name: (upper_case_qid) @structure.import.module
                    as_name: (upper_case_identifier)? @structure.import.alias
                    exposing: (exposed_values)? @structure.import.exposed) @structure.import.def
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
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
            "comments": TreeSitterAdaptivePattern(
                name="comments",
                pattern="""
                [
                    (line_comment) @documentation.comment.line,
                    (block_comment) @documentation.comment.block
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="function",
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
            ),
            
            "docstring": TreeSitterAdaptivePattern(
                name="docstring",
                pattern="""
                (block_comment
                    content: (_) @documentation.docstring.content
                    (#match? @documentation.docstring.content "^\\|\\s*@docs")) @documentation.docstring.def
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elm",
                confidence=0.9,
                metadata={
                    "relationships": [],
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
    """Create pattern context for Elm files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "elm"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(ELM_PATTERNS.keys())
    )

def get_elm_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return ELM_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_elm_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in ELM_PATTERN_METRICS:
        pattern_metrics = ELM_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_elm_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_elm_pattern_relationships(pattern_name),
        performance=ELM_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "elm"}
    )

class ElmPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced Elm pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        super().__init__()
        self._feature_extractor = None
        from parsers.pattern_processor import pattern_processor
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
        """Initialize with Elm-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = FeatureExtractor("elm")
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Elm patterns
        await self._pattern_processor.register_language_patterns(
            "elm", 
            ELM_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "elm_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(ELM_PATTERNS),
                "capabilities": list(ELM_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="elm",
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
            
            # Finally add Elm-specific patterns
            async with AsyncErrorBoundary("elm_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "elm",
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
                elm_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(elm_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "elm_pattern_learner",
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
                "elm_pattern_learner",
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
                "elm_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "elm_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_elm_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process an Elm pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Elm-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = FeatureExtractor("elm")
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "elm", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_elm_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"elm_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "elm",
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
        await update_elm_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "elm_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_elm_pattern_context(
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
            language_id="elm",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "elm"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(ELM_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

async def initialize_elm_patterns():
    """Initialize Elm patterns during app startup."""
    # Move import here to break circular import
    from parsers.pattern_processor import pattern_processor
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Elm patterns
    await pattern_processor.register_language_patterns(
        "elm",
        ELM_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": ELM_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    elm_pattern_learner = await ElmPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "elm",
        elm_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "elm_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(ELM_PATTERNS),
            "capabilities": list(ELM_CAPABILITIES)
        }
    )

# Export public interfaces
__all__ = [
    'ELM_PATTERNS',
    'ELM_PATTERN_RELATIONSHIPS',
    'ELM_PATTERN_METRICS',
    'create_pattern_context',
    'get_elm_pattern_relationships',
    'update_elm_pattern_metrics',
    'get_elm_pattern_match_result'
]

# Module identification
LANGUAGE = "elm" 