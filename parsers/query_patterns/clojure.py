"""Clojure-specific patterns with enhanced type system and relationships.

This module provides Clojure-specific patterns that integrate with the enhanced
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
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
from parsers.feature_extractor import get_feature_extractor
import time

# Clojure capabilities (extends common capabilities)
CLOJURE_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.LISP_SUPPORT,
    AICapability.MACRO_SUPPORT
}

# Pattern relationships for Clojure
CLOJURE_PATTERN_RELATIONSHIPS = {
    "function_definition": [
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="docstring",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "class_definition": [
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="function_definition",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.9,
            metadata={"methods": True}
        ),
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="docstring",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "namespace": [
        PatternRelationship(
            source_pattern="namespace",
            target_pattern="function_definition",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"namespace_members": True}
        ),
        PatternRelationship(
            source_pattern="namespace",
            target_pattern="class_definition",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"namespace_members": True}
        )
    ]
}

# Performance metrics tracking for Clojure patterns
CLOJURE_PATTERN_METRICS = {
    "function_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "class_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "namespace": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced Clojure patterns with proper typing and relationships
CLOJURE_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function_definition": TreeSitterResilientPattern(
                name="function_definition",
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @syntax.function.type
                        (#match? @syntax.function.type "^(defn|defn-|fn)$")
                        .
                        (sym_lit) @syntax.function.name
                        .
                        (vec_lit)? @syntax.function.params
                        .
                        (_)* @syntax.function.body) @syntax.function.def,
                    
                    (list_lit
                        .
                        (sym_lit) @syntax.macro.type
                        (#match? @syntax.macro.type "^defmacro$")
                        .
                        (sym_lit) @syntax.macro.name
                        .
                        (vec_lit)? @syntax.macro.params
                        .
                        (_)* @syntax.macro.body) @syntax.macro.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
                confidence=0.95,
                metadata={
                    "relationships": CLOJURE_PATTERN_RELATIONSHIPS["function_definition"],
                    "metrics": CLOJURE_PATTERN_METRICS["function_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "class_definition": TreeSitterResilientPattern(
                name="class_definition",
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @syntax.class.type
                        (#match? @syntax.class.type "^(defrecord|defprotocol|deftype)$")
                        .
                        (sym_lit) @syntax.class.name
                        .
                        [(vec_lit) @syntax.class.fields
                         (_)* @syntax.class.body]) @syntax.class.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
                confidence=0.95,
                metadata={
                    "relationships": CLOJURE_PATTERN_RELATIONSHIPS["class_definition"],
                    "metrics": CLOJURE_PATTERN_METRICS["class_definition"],
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
            "variable": TreeSitterAdaptivePattern(
                name="variable",
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @semantics.var.type
                        (#match? @semantics.var.type "^(def|defonce)$")
                        .
                        (sym_lit) @semantics.var.name
                        .
                        (_)? @semantics.var.value) @semantics.var.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
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
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "namespace": TreeSitterResilientPattern(
                name="namespace",
                pattern="""
                [
                    (list_lit
                        .
                        (sym_lit) @structure.ns.type
                        (#match? @structure.ns.type "^(ns|in-ns)$")
                        .
                        [(sym_lit) @structure.ns.name
                         (quote) @structure.ns.quoted]
                        .
                        (_)* @structure.ns.body) @structure.ns.def
                ]
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
                confidence=0.95,
                metadata={
                    "relationships": CLOJURE_PATTERN_RELATIONSHIPS["namespace"],
                    "metrics": CLOJURE_PATTERN_METRICS["namespace"],
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
                    (comment) @documentation.comment,
                    (dis_expr) @documentation.disabled
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="clojure",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="function_definition",
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
    """Create pattern context for Clojure files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "clojure", "version": "1.11+"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CLOJURE_PATTERNS.keys())
    )

def get_clojure_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return CLOJURE_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_clojure_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in CLOJURE_PATTERN_METRICS:
        pattern_metrics = CLOJURE_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_clojure_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_clojure_pattern_relationships(pattern_name),
        performance=CLOJURE_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "clojure"}
    )

class ClojurePatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced Clojure pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        super().__init__()
        self._feature_extractor = None
        self._pattern_processor = None
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
        """Initialize with Clojure-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await get_feature_extractor("clojure")
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Clojure patterns
        from parsers.pattern_processor import pattern_processor
        await self._pattern_processor.register_language_patterns(
            "clojure", 
            CLOJURE_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "clojure_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(CLOJURE_PATTERNS),
                "capabilities": list(CLOJURE_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="clojure",
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
            
            # Finally add Clojure-specific patterns
            async with AsyncErrorBoundary("clojure_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "clojure",
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
                clojure_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(clojure_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "clojure_pattern_learner",
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
                "clojure_pattern_learner",
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
                "clojure_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "clojure_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_clojure_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Clojure pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Clojure-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await get_feature_extractor("clojure")
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "clojure", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_clojure_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"clojure_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "clojure",
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
        await update_clojure_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "clojure_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_clojure_pattern_context(
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
            language_id="clojure",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "clojure", "version": "1.11+"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CLOJURE_PATTERNS.keys())
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
clojure_pattern_learner = ClojurePatternLearner()

async def initialize_clojure_patterns():
    """Initialize Clojure patterns during app startup."""
    global clojure_pattern_learner
    from parsers.pattern_processor import pattern_processor
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Clojure patterns
    await pattern_processor.register_language_patterns(
        "clojure",
        CLOJURE_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": CLOJURE_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    clojure_pattern_learner = await ClojurePatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "clojure",
        clojure_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "clojure_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(CLOJURE_PATTERNS),
            "capabilities": list(CLOJURE_CAPABILITIES)
        }
    )

# Export public interfaces
__all__ = [
    'CLOJURE_PATTERNS',
    'CLOJURE_PATTERN_RELATIONSHIPS',
    'CLOJURE_PATTERN_METRICS',
    'create_pattern_context',
    'get_clojure_pattern_relationships',
    'update_clojure_pattern_metrics',
    'get_clojure_pattern_match_result',
    'ClojurePatternLearner',
    'process_clojure_pattern',
    'create_clojure_pattern_context',
    'initialize_clojure_patterns'
]

# Module identification
LANGUAGE = "clojure" 