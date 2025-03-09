"""Query patterns for Vue files.

This module provides Vue-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "vue"

# Vue capabilities (extends common capabilities)
VUE_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.COMPONENT_BASED,
    AICapability.REACTIVITY,
    AICapability.TEMPLATE_PROCESSING
}

@dataclass
class VuePatternContext(PatternContext):
    """Vue-specific pattern context."""
    component_names: Set[str] = field(default_factory=set)
    directive_names: Set[str] = field(default_factory=set)
    prop_names: Set[str] = field(default_factory=set)
    event_names: Set[str] = field(default_factory=set)
    has_composition_api: bool = False
    has_options_api: bool = False
    has_typescript: bool = False
    has_setup: bool = False
    has_jsx: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.component_names)}:{self.has_composition_api}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "component": PatternPerformanceMetrics(),
    "template": PatternPerformanceMetrics(),
    "script": PatternPerformanceMetrics(),
    "style": PatternPerformanceMetrics(),
    "directive": PatternPerformanceMetrics()
}

VUE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "component": ResilientPattern(
                pattern="""
                [
                    (component
                        (template_element
                            (start_tag) @syntax.template.start
                            (_)* @syntax.template.content
                            (end_tag) @syntax.template.end) @syntax.template
                        (script_element
                            (start_tag) @syntax.script.start
                            (raw_text) @syntax.script.content
                            (end_tag) @syntax.script.end) @syntax.script
                        (style_element
                            (start_tag) @syntax.style.start
                            (_)? @syntax.style.content
                            (end_tag) @syntax.style.end)? @syntax.style) @syntax.component,
                    (element
                        (start_tag
                            name: (_) @syntax.element.name
                            attributes: (attribute
                                name: (attribute_name) @syntax.element.attr.name
                                value: (attribute_value) @syntax.element.attr.value)* @syntax.element.attrs) @syntax.element.start
                        (_)* @syntax.element.children
                        (end_tag) @syntax.element.end) @syntax.element
                ]
                """,
                extract=lambda node: {
                    "type": "component",
                    "line_number": node["captures"].get("syntax.component", {}).get("start_point", [0])[0],
                    "has_template": "syntax.template" in node["captures"],
                    "has_script": "syntax.script" in node["captures"],
                    "has_style": "syntax.style" in node["captures"],
                    "element_name": node["captures"].get("syntax.element.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["template", "script", "style"],
                        PatternRelationType.DEPENDS_ON: ["component"]
                    }
                },
                name="component",
                description="Matches Vue component declarations",
                examples=["<template>...</template>", "<script>...</script>"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["component"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            ),
            "directive": ResilientPattern(
                pattern="""
                [
                    (directive_attribute
                        name: (directive_name) @syntax.directive.name {
                            match: "^v-if$"
                        }
                        value: (attribute_value) @syntax.directive.if.value) @syntax.directive.if,
                    (directive_attribute
                        name: (directive_name) @syntax.directive.name {
                            match: "^v-else-if$"
                        }
                        value: (attribute_value) @syntax.directive.else_if.value) @syntax.directive.else_if,
                    (directive_attribute
                        name: (directive_name) @syntax.directive.name {
                            match: "^v-else$"
                        }) @syntax.directive.else,
                    (directive_attribute
                        name: (directive_name) @syntax.directive.name {
                            match: "^v-for$"
                        }
                        value: (attribute_value) @syntax.directive.for.value) @syntax.directive.for
                ]
                """,
                extract=lambda node: {
                    "type": "directive",
                    "line_number": (
                        node["captures"].get("syntax.directive.if", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.directive.else_if", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.directive.else", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.directive.for", {}).get("start_point", [0])[0]
                    ),
                    "name": node["captures"].get("syntax.directive.name", {}).get("text", ""),
                    "value": (
                        node["captures"].get("syntax.directive.if.value", {}).get("text", "") or
                        node["captures"].get("syntax.directive.else_if.value", {}).get("text", "") or
                        node["captures"].get("syntax.directive.for.value", {}).get("text", "")
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["template"],
                        PatternRelationType.DEPENDS_ON: ["script"]
                    }
                },
                name="directive",
                description="Matches Vue directive attributes",
                examples=["v-if='condition'", "v-for='item in items'"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["directive"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^v-[a-z][a-z0-9-]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.COMPOSITION: {
            "script_setup": AdaptivePattern(
                pattern="""
                [
                    (script_element
                        (start_tag
                            attributes: [(attribute
                                name: (attribute_name) @script.attr.name {
                                    match: "^lang$"
                                }
                                value: (attribute_value) @script.attr.lang)
                            (attribute
                                name: (attribute_name) @script.attr.name {
                                    match: "^setup$"
                                })]) @script.start
                        (raw_text) @script.content
                        (end_tag)) @script.setup,
                    (raw_text) @script.composition.api {
                        match: "\\b(ref|reactive|computed|watch|watchEffect|onMounted|onUpdated|onUnmounted|provide|inject)\\b"
                    }
                ]
                """,
                extract=lambda node: {
                    "type": "script_setup",
                    "line_number": node["captures"].get("script.setup", {}).get("start_point", [0])[0],
                    "lang": next((lang.get("text", "").strip('"\'') for lang in node["captures"].get("script.attr.lang", [])), "js"),
                    "has_composition_api": "script.composition.api" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["import", "function", "variable"],
                        PatternRelationType.DEPENDS_ON: ["component"]
                    }
                },
                name="script_setup",
                description="Matches Vue script setup blocks",
                examples=["<script setup>", "<script setup lang='ts'>"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.COMPOSITION,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["script"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        },
        PatternPurpose.REACTIVITY: {
            "template_expressions": AdaptivePattern(
                pattern="""
                [
                    (interpolation
                        (raw_text) @expr.interpolation.text) @expr.interpolation,
                    (directive_attribute
                        name: (directive_name) @expr.directive.name
                        value: (attribute_value) @expr.directive.value) @expr.directive,
                    (directive_attribute
                        name: (directive_name) @expr.binding.name {
                            match: "^v-bind$|^:"
                        }
                        argument: (directive_argument) @expr.binding.arg
                        value: (attribute_value) @expr.binding.value) @expr.binding
                ]
                """,
                extract=lambda node: {
                    "type": "template_expressions",
                    "line_number": (
                        node["captures"].get("expr.interpolation", {}).get("start_point", [0])[0] or
                        node["captures"].get("expr.directive", {}).get("start_point", [0])[0] or
                        node["captures"].get("expr.binding", {}).get("start_point", [0])[0]
                    ),
                    "expression": (
                        node["captures"].get("expr.interpolation.text", {}).get("text", "") or
                        node["captures"].get("expr.directive.value", {}).get("text", "") or
                        node["captures"].get("expr.binding.value", {}).get("text", "")
                    ),
                    "is_binding": "expr.binding" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCES: ["script"],
                        PatternRelationType.DEPENDS_ON: ["component"]
                    }
                },
                name="template_expressions",
                description="Matches Vue template expressions",
                examples=["{{ value }}", "v-bind:prop='expr'", ":prop='expr'"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REACTIVITY,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["template"],
                    "validation": {
                        "required_fields": ["expression"],
                        "name_format": None
                    }
                }
            )
        }
    }
}

class VuePatternLearner(CrossProjectPatternLearner):
    """Enhanced Vue pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Vue-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("vue", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Vue patterns
        await self._pattern_processor.register_language_patterns(
            "vue", 
            VUE_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "vue_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(VUE_PATTERNS),
                "capabilities": list(VUE_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="vue",
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
            
            # Finally add Vue-specific patterns
            async with AsyncErrorBoundary("vue_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "vue",
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
                vue_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(vue_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "vue_pattern_learner",
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
                "vue_pattern_learner",
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
                "vue_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "vue_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_vue_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Vue pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Vue-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("vue", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "vue", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_vue_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"vue_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "vue",
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
        await update_vue_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "vue_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_vue_pattern_context(
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
            language_id="vue",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "vue"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(VUE_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_vue_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_vue_pattern_match_result(
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
        metadata={"language": "vue"}
    )

# Initialize pattern learner
pattern_learner = VuePatternLearner()

async def initialize_vue_patterns():
    """Initialize Vue patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Vue patterns
    await pattern_processor.register_language_patterns(
        "vue",
        VUE_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": VUE_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await VuePatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "vue",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "vue_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(VUE_PATTERNS),
            "capabilities": list(VUE_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "component": {
        PatternRelationType.CONTAINS: ["template", "script", "style"],
        PatternRelationType.DEPENDS_ON: ["component"]
    },
    "directive": {
        PatternRelationType.CONTAINED_BY: ["template"],
        PatternRelationType.DEPENDS_ON: ["script"]
    },
    "script_setup": {
        PatternRelationType.CONTAINS: ["import", "function", "variable"],
        PatternRelationType.DEPENDS_ON: ["component"]
    },
    "template_expressions": {
        PatternRelationType.REFERENCES: ["script"],
        PatternRelationType.DEPENDS_ON: ["component"]
    }
}

# Export public interfaces
__all__ = [
    'VUE_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_vue_pattern_match_result',
    'update_vue_pattern_metrics',
    'VuePatternContext',
    'pattern_learner'
] 