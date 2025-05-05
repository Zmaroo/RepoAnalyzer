"""Elixir-specific patterns with enhanced type system and relationships.

This module provides Elixir-specific patterns that integrate with the enhanced
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
from parsers.feature_extractor import get_feature_extractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# Elixir capabilities (extends common capabilities)
ELIXIR_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.FUNCTIONAL_PROGRAMMING,
    AICapability.PATTERN_MATCHING,
    AICapability.CONCURRENCY
}

# Pattern relationships for Elixir
ELIXIR_PATTERN_RELATIONSHIPS = {
    "function": [
        PatternRelationship(
            source_pattern="function",
            target_pattern="module",
            relationship_type=PatternRelationType.DEPENDS_ON,
            confidence=0.95,
            metadata={"module_function": True}
        ),
        PatternRelationship(
            source_pattern="function",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "module": [
        PatternRelationship(
            source_pattern="module",
            target_pattern="function",
            relationship_type=PatternRelationType.DEPENDS_ON,
            confidence=0.95,
            metadata={"functions": True}
        ),
        PatternRelationship(
            source_pattern="module",
            target_pattern="behaviour",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.9,
            metadata={"behaviours": True}
        )
    ]
}

# Performance metrics tracking for Elixir patterns
ELIXIR_PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(
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

# Enhanced Elixir patterns with proper typing and relationships
ELIXIR_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": TreeSitterResilientPattern(
                name="function",
                pattern="""
                [
                    (stab_clause
                        left: (arguments
                            [
                                (identifier) @syntax.function.name
                                (binary_operator) @syntax.function.operator
                            ]) @syntax.function.params
                        right: (body) @syntax.function.body) @syntax.function.def,
                        
                    (call
                        target: (identifier) @syntax.macro.name
                        (#match? @syntax.macro.name "^(def|defp|defmacro|defmacrop)$")
                        (arguments
                            (identifier) @syntax.function.name
                            parameters: (_)? @syntax.function.params
                            body: (do_block)? @syntax.function.body)) @syntax.macro.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
                confidence=0.95,
                metadata={
                    "relationships": ELIXIR_PATTERN_RELATIONSHIPS["function"],
                    "metrics": ELIXIR_PATTERN_METRICS["function"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "module": TreeSitterResilientPattern(
                name="module",
                pattern="""
                [
                    (call
                        target: (identifier) @semantics.module.keyword
                        (#match? @semantics.module.keyword "^(defmodule)$")
                        (arguments
                            (alias) @semantics.module.name
                            (do_block)? @semantics.module.body)) @semantics.module.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
                confidence=0.95,
                metadata={
                    "relationships": ELIXIR_PATTERN_RELATIONSHIPS["module"],
                    "metrics": ELIXIR_PATTERN_METRICS["module"],
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
            "namespace": QueryPattern(
                name="namespace",
                pattern="""
                (block
                    (_)* @block.content) @namespace
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
                extract=lambda node: {
                    "type": "namespace",
                    "content": node["node"].text.decode('utf8')
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": TreeSitterAdaptivePattern(
                name="variable",
                pattern="""
                (string
                    quoted_content: (_)? @string.content
                    interpolation: (_)* @string.interpolation) @variable
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
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
            "module": QueryPattern(
                name="module",
                pattern="""
                [
                    (call
                        target: (identifier) @semantics.module.keyword
                        (#match? @semantics.module.keyword "^(defmodule)$")
                        (arguments
                            (alias) @semantics.module.name
                            (do_block)? @semantics.module.body)
                    ) @semantics.module.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
                extract=lambda node: {
                    "name": node["captures"].get("semantics.module.name", {}).get("text", ""),
                    "type": "module"
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
                    (comment) @documentation.comment
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
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
            )
        }
    },
    
    PatternCategory.CODE_PATTERNS: {
        PatternPurpose.UNDERSTANDING: {
            "naming_conventions": QueryPattern(
                name="naming_conventions",
                pattern="""
                [
                    (call
                        target: (identifier) @naming.module.keyword
                        (#match? @naming.module.keyword "^(defmodule)$")
                        (arguments
                            (alias) @naming.module.name
                            (_)* @naming.module.rest)
                    ) @naming.module
                    (call
                        target: (identifier) @naming.func.keyword
                        (#match? @naming.func.keyword "^(def|defp|defmacro|defmacrop)$")
                        (arguments
                            (identifier) @naming.func.name
                            (_)* @naming.func.rest)
                    ) @naming.func
                    (call
                        target: (identifier) @naming.struct.keyword
                        (#match? @naming.struct.keyword "^(defstruct)$")
                        (_)* @naming.struct.fields
                    ) @naming.struct
                    (call
                        target: (identifier) @naming.protocol.keyword
                        (#match? @naming.protocol.keyword "^(defprotocol)$")
                        (arguments
                            (alias) @naming.protocol.name
                            (_)* @naming.protocol.rest)
                    ) @naming.protocol
                ]
                """,
                category=PatternCategory.CODE_PATTERNS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
                extract=lambda node: {
                    "module_name": node["captures"].get("naming.module.name", {}).get("text", ""),
                    "function_name": node["captures"].get("naming.func.name", {}).get("text", ""),
                    "protocol_name": node["captures"].get("naming.protocol.name", {}).get("text", ""),
                    "uses_pascal_case_for_modules": bool(
                        name and name[0].isupper() and "_" not in name 
                        for name in [
                            node["captures"].get("naming.module.name", {}).get("text", ""),
                            node["captures"].get("naming.protocol.name", {}).get("text", "")
                        ] if name
                    ),
                    "uses_snake_case_for_functions": bool(
                        name and name[0].islower() and "_" in name and name == name.lower()
                        for name in [node["captures"].get("naming.func.name", {}).get("text", "")] 
                        if name
                    )
                }
            )
        },
        PatternPurpose.UNDERSTANDING: {
            "module_organization": QueryPattern(
                name="module_organization",
                pattern="""
                [
                    (call
                        target: (identifier) @org.module.keyword
                        (#match? @org.module.keyword "^(defmodule)$")
                        (arguments
                            (alias) @org.module.name
                            (do_block
                                (call
                                    target: (identifier) @org.use.keyword
                                    (#match? @org.use.keyword "^(use|import|alias|require)$")
                                    (arguments
                                        (_) @org.use.arg
                                        (_)* @org.use.opts
                                    )
                                ) @org.use
                            )*
                            @org.module.body
                        )
                    ) @org.module
                    (call
                        target: (identifier) @org.behaviour.keyword
                        (#match? @org.behaviour.keyword "^(@behaviour|@impl)$")
                        (arguments
                            (_) @org.behaviour.arg
                        )
                    ) @org.behaviour
                ]
                """,
                category=PatternCategory.CODE_PATTERNS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
                extract=lambda node: {
                    "has_use_declarations": bool(node["captures"].get("org.use.keyword", {}).get("text") == "use"),
                    "has_import_declarations": bool(node["captures"].get("org.use.keyword", {}).get("text") == "import"),
                    "has_alias_declarations": bool(node["captures"].get("org.use.keyword", {}).get("text") == "alias"),
                    "has_require_declarations": bool(node["captures"].get("org.use.keyword", {}).get("text") == "require"),
                    "implements_behaviour": bool(node["captures"].get("org.behaviour.keyword", {}).get("text") == "@behaviour"),
                    "has_impl_annotation": bool(node["captures"].get("org.behaviour.keyword", {}).get("text") == "@impl")
                }
            )
        },
        PatternPurpose.UNDERSTANDING: {
            "functional_patterns": QueryPattern(
                name="functional_patterns",
                pattern="""
                [
                    (call
                        target: (identifier) @fp.enum.module
                        (#match? @fp.enum.module "^(Enum|Stream)$")
                    ) @fp.enum
                    (call
                        target: (identifier) @fp.pattern.keyword
                        (#match? @fp.pattern.keyword "^(case|cond|with|for|if|unless)$")
                    ) @fp.pattern
                ]
                """,
                category=PatternCategory.CODE_PATTERNS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir",
                extract=lambda node: {
                    "uses_enum_functions": bool(node["captures"].get("fp.enum.module", {}).get("text", "")),
                    "enum_function": node["captures"].get("fp.enum.function", {}).get("text", ""),
                    "uses_pattern_matching": bool(node["captures"].get("fp.pattern.keyword", {}).get("text", "")),
                    "pattern_type": node["captures"].get("fp.pattern.keyword", {}).get("text", ""),
                    "uses_function_capture": bool(node["captures"].get("fp.capture.op", {}).get("text", "") == "&"),
                    "uses_pipe_operator": node.get("operator") == "|>"
                }
            )
        },
        PatternPurpose.UNDERSTANDING: {
            "concurrency_patterns": QueryPattern(
                name="concurrency_patterns",
                pattern="""
                [
                    (call
                        target: (identifier) @concurrency.process.keyword
                        (#match? @concurrency.process.keyword "^(spawn|spawn_link|spawn_monitor)$")
                        (arguments
                            (_) @concurrency.process.args
                        )
                    ) @concurrency.process
                    (call
                        target: (identifier) @concurrency.msg.keyword
                        (#match? @concurrency.msg.keyword "^(send|receive)$")
                        (arguments
                            (_) @concurrency.msg.args
                        )
                    ) @concurrency.msg
                    (call
                        target: (identifier) @concurrency.genserver.keyword
                        (#match? @concurrency.genserver.keyword "^(GenServer\\.(start_link|call|cast))$")
                        (arguments
                            (_) @concurrency.genserver.args
                        )
                    ) @concurrency.genserver
                    (call
                        target: (identifier) @concurrency.task.keyword
                        (#match? @concurrency.task.keyword "^(Task\\.(async|await|yield|start_link))$")
                        (arguments
                            (_) @concurrency.task.args
                        )
                    ) @concurrency.task
                ]
                """,
                extract=lambda node: {
                    "uses_spawn": bool(node["captures"].get("concurrency.process.keyword", {}).get("text", "") in ["spawn", "spawn_link", "spawn_monitor"]),
                    "uses_message_passing": bool(node["captures"].get("concurrency.msg.keyword", {}).get("text", "") in ["send", "receive"]),
                    "uses_genserver": bool(node["captures"].get("concurrency.genserver.keyword", {}).get("text", "")),
                    "uses_tasks": bool(node["captures"].get("concurrency.task.keyword", {}).get("text", "")),
                    "concurrency_paradigm": (
                        "genserver" if node["captures"].get("concurrency.genserver.keyword", {}).get("text", "") else
                        "task" if node["captures"].get("concurrency.task.keyword", {}).get("text", "") else
                        "process" if node["captures"].get("concurrency.process.keyword", {}).get("text", "") else
                        "message_passing" if node["captures"].get("concurrency.msg.keyword", {}).get("text", "") else
                        None
                    )
                },
                category=PatternCategory.CODE_PATTERNS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="elixir"
            )
        }
    }
}

def create_pattern_context(file_path: str, code_structure: Dict[str, Any]) -> PatternContext:
    """Create pattern context for Elixir files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "elixir"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(ELIXIR_PATTERNS.keys())
    )

def get_elixir_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return ELIXIR_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_elixir_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in ELIXIR_PATTERN_METRICS:
        pattern_metrics = ELIXIR_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_elixir_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_elixir_pattern_relationships(pattern_name),
        performance=ELIXIR_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "elixir"}
    )

class ElixirPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced Elixir pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Elixir-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await get_feature_extractor("elixir", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Elixir patterns
        from parsers.pattern_processor import pattern_processor
        self._pattern_processor = pattern_processor
        await self._pattern_processor.register_language_patterns(
            "elixir", 
            ELIXIR_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "elixir_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(ELIXIR_PATTERNS),
                "capabilities": list(ELIXIR_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="elixir",
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
            
            # Finally add Elixir-specific patterns
            async with AsyncErrorBoundary("elixir_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "elixir",
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
                elixir_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(elixir_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "elixir_pattern_learner",
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
                "elixir_pattern_learner",
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
                "elixir_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "elixir_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors()
async def process_elixir_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process an Elixir pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Elixir-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await get_feature_extractor("elixir", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "elixir", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_elixir_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"elixir_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "elixir",
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
        await update_elixir_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "elixir_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_elixir_pattern_context(
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
            language_id="elixir",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "elixir"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(ELIXIR_PATTERNS.keys())
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
elixir_pattern_learner = ElixirPatternLearner()

async def initialize_elixir_patterns():
    """Initialize Elixir patterns during app startup."""
    global elixir_pattern_learner
    
    # Initialize pattern processor first
    from parsers.pattern_processor import pattern_processor
    await pattern_processor.initialize()
    
    # Register Elixir patterns
    await pattern_processor.register_language_patterns(
        "elixir",
        ELIXIR_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": ELIXIR_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    elixir_pattern_learner = await ElixirPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "elixir",
        elixir_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "elixir_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(ELIXIR_PATTERNS),
            "capabilities": list(ELIXIR_CAPABILITIES)
        }
    )

# Export public interfaces
__all__ = [
    'ELIXIR_PATTERNS',
    'ELIXIR_PATTERN_RELATIONSHIPS',
    'ELIXIR_PATTERN_METRICS',
    'create_pattern_context',
    'get_elixir_pattern_relationships',
    'update_elixir_pattern_metrics',
    'get_elixir_pattern_match_result'
]

# Module identification
LANGUAGE = "elixir" 