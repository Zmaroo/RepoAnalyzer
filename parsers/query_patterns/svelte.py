"""Query patterns for Svelte files.

This module provides Svelte-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "svelte"

# Svelte capabilities (extends common capabilities)
SVELTE_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.COMPONENT_BASED,
    AICapability.REACTIVITY,
    AICapability.TEMPLATE_PROCESSING
}

@dataclass
class SveltePatternContext(PatternContext):
    """Svelte-specific pattern context."""
    component_names: Set[str] = field(default_factory=set)
    store_names: Set[str] = field(default_factory=set)
    action_names: Set[str] = field(default_factory=set)
    event_names: Set[str] = field(default_factory=set)
    has_typescript: bool = False
    has_stores: bool = False
    has_actions: bool = False
    has_transitions: bool = False
    has_animations: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.component_names)}:{self.has_stores}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "component": PatternPerformanceMetrics(),
    "script": PatternPerformanceMetrics(),
    "style": PatternPerformanceMetrics(),
    "store": PatternPerformanceMetrics(),
    "action": PatternPerformanceMetrics()
}

SVELTE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "component": ResilientPattern(
                pattern="""
                [
                    (script_element
                        attribute: (attribute)* @syntax.script.attrs
                        content: [(javascript_program) (typescript_program)]? @syntax.script.content) @syntax.script,
                    (style_element
                        attribute: (attribute)* @syntax.style.attrs
                        content: (_)? @syntax.style.content) @syntax.style,
                    (element
                        name: (tag_name) @syntax.custom.name {
                            match: "^[A-Z].*"
                        }
                        attribute: (attribute)* @syntax.custom.attrs
                        body: (_)* @syntax.custom.body) @syntax.custom
                ]
                """,
                extract=lambda node: {
                    "type": "component",
                    "line_number": (
                        node["captures"].get("syntax.script", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.style", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.custom", {}).get("start_point", [0])[0]
                    ),
                    "name": node["captures"].get("syntax.custom.name", {}).get("text", ""),
                    "has_script": "syntax.script" in node["captures"],
                    "has_style": "syntax.style" in node["captures"],
                    "has_typescript": "typescript_program" in (node["captures"].get("syntax.script.content", {}).get("type", "") or ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["script", "style", "element"],
                        PatternRelationType.DEPENDS_ON: ["component"]
                    }
                },
                name="component",
                description="Matches Svelte component declarations",
                examples=["<script>...</script>", "<style>...</style>", "<CustomComponent/>"],
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
            "store": ResilientPattern(
                pattern="""
                [
                    (lexical_declaration
                        declarator: (variable_declarator
                            name: (identifier) @syntax.store.name
                            value: (call_expression
                                function: (identifier) @syntax.store.func {
                                    match: "^(writable|readable|derived)$"
                                }
                                arguments: (arguments) @syntax.store.args) @syntax.store.init) @syntax.store.decl) @syntax.store,
                    (assignment_expression
                        left: (member_expression
                            object: (_) @syntax.update.obj
                            property: (property_identifier) @syntax.update.prop {
                                match: "^(set|update)$"
                            }) @syntax.update.target
                        right: (_) @syntax.update.value) @syntax.update
                ]
                """,
                extract=lambda node: {
                    "type": "store",
                    "line_number": (
                        node["captures"].get("syntax.store", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.update", {}).get("start_point", [0])[0]
                    ),
                    "name": node["captures"].get("syntax.store.name", {}).get("text", ""),
                    "store_type": node["captures"].get("syntax.store.func", {}).get("text", ""),
                    "is_update": "syntax.update" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["component", "script"],
                        PatternRelationType.DEPENDS_ON: ["store"]
                    }
                },
                name="store",
                description="Matches Svelte store declarations",
                examples=["const count = writable(0)", "count.set(1)"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["store"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_$][a-zA-Z0-9_$]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.EVENTS: {
            "event_handling": AdaptivePattern(
                pattern="""
                [
                    (attribute
                        name: (attribute_name) @event.attr.name {
                            match: "^(on:[a-zA-Z]+)$"
                        }
                        value: (attribute_value) @event.attr.value) @event.attr,
                    (attribute
                        name: (attribute_name) @event.action.name {
                            match: "^(use:[a-zA-Z]+)$"
                        }
                        value: (attribute_value) @event.action.value) @event.action,
                    (lexical_declaration
                        declarator: (variable_declarator
                            name: (identifier) @event.dispatcher.name
                            value: (call_expression
                                function: (identifier) @event.dispatcher.func {
                                    match: "^(createEventDispatcher)$"
                                }) @event.dispatcher.init) @event.dispatcher.decl) @event.dispatcher,
                    (call_expression
                        function: (identifier) @event.dispatch.func {
                            match: "^(dispatch)$"
                        }
                        arguments: (arguments
                            (string) @event.dispatch.name) @event.dispatch.args) @event.dispatch
                ]
                """,
                extract=lambda node: {
                    "type": "event_handling",
                    "line_number": (
                        node["captures"].get("event.attr", {}).get("start_point", [0])[0] or
                        node["captures"].get("event.action", {}).get("start_point", [0])[0] or
                        node["captures"].get("event.dispatcher", {}).get("start_point", [0])[0] or
                        node["captures"].get("event.dispatch", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("event.attr.name", {}).get("text", "") or
                        node["captures"].get("event.action.name", {}).get("text", "") or
                        node["captures"].get("event.dispatcher.name", {}).get("text", "") or
                        node["captures"].get("event.dispatch.name", {}).get("text", "")
                    ),
                    "is_action": "event.action" in node["captures"],
                    "is_dispatcher": "event.dispatcher" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["component", "element"],
                        PatternRelationType.DEPENDS_ON: ["script"]
                    }
                },
                name="event_handling",
                description="Matches Svelte event handling patterns",
                examples=["on:click={handleClick}", "use:action", "dispatch('event')"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.EVENTS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["action"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_$][a-zA-Z0-9_$]*$'
                    }
                }
            )
        }
    }
}

class SveltePatternLearner(CrossProjectPatternLearner):
    """Enhanced Svelte pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Svelte-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("svelte", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Svelte patterns
        await self._pattern_processor.register_language_patterns(
            "svelte", 
            SVELTE_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "svelte_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(SVELTE_PATTERNS),
                "capabilities": list(SVELTE_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="svelte",
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
            
            # Finally add Svelte-specific patterns
            async with AsyncErrorBoundary("svelte_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "svelte",
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
                svelte_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(svelte_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "svelte_pattern_learner",
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
                "svelte_pattern_learner",
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
                "svelte_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "svelte_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_svelte_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Svelte pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Svelte-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("svelte", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "svelte", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_svelte_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"svelte_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "svelte",
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
        await update_svelte_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "svelte_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_svelte_pattern_context(
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
            language_id="svelte",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "svelte"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(SVELTE_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_svelte_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_svelte_pattern_match_result(
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
        metadata={"language": "svelte"}
    )

# Initialize pattern learner
pattern_learner = SveltePatternLearner()

async def initialize_svelte_patterns():
    """Initialize Svelte patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Svelte patterns
    await pattern_processor.register_language_patterns(
        "svelte",
        SVELTE_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": SVELTE_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await SveltePatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "svelte",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "svelte_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(SVELTE_PATTERNS),
            "capabilities": list(SVELTE_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "component": {
        PatternRelationType.CONTAINS: ["script", "style", "element"],
        PatternRelationType.DEPENDS_ON: ["component"]
    },
    "store": {
        PatternRelationType.REFERENCED_BY: ["component", "script"],
        PatternRelationType.DEPENDS_ON: ["store"]
    },
    "event_handling": {
        PatternRelationType.CONTAINED_BY: ["component", "element"],
        PatternRelationType.DEPENDS_ON: ["script"]
    }
}

# Export public interfaces
__all__ = [
    'SVELTE_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_svelte_pattern_match_result',
    'update_svelte_pattern_metrics',
    'SveltePatternContext',
    'pattern_learner'
] 