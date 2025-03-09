"""
Query patterns for Julia files.

This module provides Julia-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Set, Union
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, ParserType
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
from parsers.pattern_processor import pattern_processor
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import BaseFeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# Language identifier
LANGUAGE = "julia"

# Julia capabilities (extends common capabilities)
JULIA_CAPABILITIES = {
    AICapability.SCIENTIFIC_COMPUTING,
    AICapability.MULTIPLE_DISPATCH,
    AICapability.METAPROGRAMMING
}

@dataclass
class JuliaPatternContext(PatternContext):
    """Julia-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    type_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    macro_names: Set[str] = field(default_factory=set)
    has_multiple_dispatch: bool = False
    has_metaprogramming: bool = False
    has_type_params: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{self.has_multiple_dispatch}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "struct": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics(),
    "macro": PatternPerformanceMetrics(),
    "type": PatternPerformanceMetrics()
}

JULIA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params
                        body: (block) @syntax.function.body) @syntax.function.def,
                    (short_function_definition
                        name: (identifier) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params
                        body: (_) @syntax.function.body) @syntax.function.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.function.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["type"]
                    }
                },
                name="function",
                description="Matches function definitions",
                examples=["function foo(x::Int) end", "foo(x) = x + 1"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_!]*$'
                    }
                }
            ),
            "struct": ResilientPattern(
                pattern="""
                (struct_definition
                    name: (identifier) @syntax.struct.name
                    body: (field_list) @syntax.struct.body) @syntax.struct.def
                """,
                extract=lambda node: {
                    "type": "struct",
                    "name": node["captures"].get("syntax.struct.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.struct.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["field"],
                        PatternRelationType.DEPENDS_ON: ["type"]
                    }
                },
                name="struct",
                description="Matches struct definitions",
                examples=["struct Point\n    x::Float64\n    y::Float64\nend"],
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
            "module": ResilientPattern(
                pattern="""
                [
                    (module_definition
                        name: (identifier) @syntax.module.name
                        body: (block) @syntax.module.body) @syntax.module.def,
                    (baremodule_definition
                        name: (identifier) @syntax.module.bare.name
                        body: (block) @syntax.module.bare.body) @syntax.module.bare.def
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "name": (
                        node["captures"].get("syntax.module.name", {}).get("text", "") or
                        node["captures"].get("syntax.module.bare.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.module.def", {}).get("start_point", [0])[0],
                    "is_bare": "syntax.module.bare.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["function", "struct", "type", "macro"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="module",
                description="Matches module definitions",
                examples=["module MyModule\nend", "baremodule MyModule\nend"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["module"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (assignment
                        left: (identifier) @semantics.variable.name
                        right: (_) @semantics.variable.value) @semantics.variable.def,
                    (const_statement
                        name: (identifier) @semantics.variable.const.name
                        value: (_) @semantics.variable.const.value) @semantics.variable.const
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("semantics.variable.name", {}).get("text", "") or
                        node["captures"].get("semantics.variable.const.name", {}).get("text", "")
                    ),
                    "type": "variable",
                    "is_const": "semantics.variable.const" in node["captures"]
                }
            ),
            "type": QueryPattern(
                pattern="""
                [
                    (type_definition
                        name: (identifier) @semantics.type.name
                        value: (_) @semantics.type.value) @semantics.type.def,
                    (primitive_definition
                        type: (type_head) @semantics.type.primitive.head) @semantics.type.primitive
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                    "type": "type",
                    "is_primitive": "semantics.type.primitive" in node["captures"]
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (line_comment) @documentation.comment.line,
                    (block_comment) @documentation.comment.block
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment.line", {}).get("text", "") or
                        node["captures"].get("documentation.comment.block", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_block": "documentation.comment.block" in node["captures"]
                }
            ),
            "docstring": QueryPattern(
                pattern="""
                (string_literal) @documentation.docstring {
                    match: "^\\"\\"\\""
                }
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.docstring", {}).get("text", ""),
                    "type": "docstring"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "import": QueryPattern(
                pattern="""
                [
                    (import_statement
                        path: (identifier) @structure.import.path) @structure.import.def,
                    (using_statement
                        path: (identifier) @structure.import.using.path) @structure.import.using
                ]
                """,
                extract=lambda node: {
                    "path": (
                        node["captures"].get("structure.import.path", {}).get("text", "") or
                        node["captures"].get("structure.import.using.path", {}).get("text", "")
                    ),
                    "type": "import",
                    "is_using": "structure.import.using" in node["captures"]
                }
            ),
            "export": QueryPattern(
                pattern="""
                (export_statement
                    names: (_) @structure.export.names) @structure.export.def
                """,
                extract=lambda node: {
                    "names": node["captures"].get("structure.export.names", {}).get("text", ""),
                    "type": "export"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.MULTIPLE_DISPATCH: {
            "multiple_dispatch": AdaptivePattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @dispatch.func.name
                        parameters: (parameter_list
                            (parameter
                                type: (_) @dispatch.param.type)*) @dispatch.func.params) @dispatch.func,
                        
                    (short_function_definition
                        name: (identifier) @dispatch.short.name
                        parameters: (parameter_list
                            (parameter
                                type: (_) @dispatch.short.type)*) @dispatch.short.params) @dispatch.short
                ]
                """,
                extract=lambda node: {
                    "type": "multiple_dispatch",
                    "function_name": (
                        node["captures"].get("dispatch.func.name", {}).get("text", "") or
                        node["captures"].get("dispatch.short.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("dispatch.func", {}).get("start_point", [0])[0],
                    "has_typed_parameters": (
                        "dispatch.param.type" in node["captures"] or
                        "dispatch.short.type" in node["captures"]
                    ),
                    "parameter_count": len((
                        node["captures"].get("dispatch.func.params", {}).get("text", "") or
                        node["captures"].get("dispatch.short.params", {}).get("text", "") or ","
                    ).split(",")),
                    "is_specialized_method": True,
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["type"],
                        PatternRelationType.REFERENCES: ["function"]
                    }
                },
                name="multiple_dispatch",
                description="Matches multiple dispatch function definitions",
                examples=["f(x::Int) = x + 1", "function f(x::Float64)\n    x * 2\nend"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.MULTIPLE_DISPATCH,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["function_name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_!]*$'
                    }
                }
            )
        },
        PatternPurpose.METAPROGRAMMING: {
            "metaprogramming": AdaptivePattern(
                pattern="""
                [
                    (macro_definition
                        name: (identifier) @meta.macro.name
                        parameters: (parameter_list) @meta.macro.params
                        body: (block) @meta.macro.body) @meta.macro,
                        
                    (quote_expression
                        body: (_) @meta.quote.body) @meta.quote,
                        
                    (macro_expression
                        name: (identifier) @meta.expr.name
                        arguments: (_)* @meta.expr.args) @meta.expr
                ]
                """,
                extract=lambda node: {
                    "type": "metaprogramming",
                    "line_number": node["captures"].get("meta.macro", {}).get("start_point", [0])[0],
                    "uses_macro_definition": "meta.macro" in node["captures"],
                    "uses_quote_expression": "meta.quote" in node["captures"],
                    "uses_macro_call": "meta.expr" in node["captures"],
                    "macro_name": (
                        node["captures"].get("meta.macro.name", {}).get("text", "") or
                        node["captures"].get("meta.expr.name", {}).get("text", "")
                    ),
                    "code_generation_style": (
                        "macro_definition" if "meta.macro" in node["captures"] else
                        "quoting" if "meta.quote" in node["captures"] else
                        "macro_invocation" if "meta.expr" in node["captures"] else
                        "other"
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["block"],
                        PatternRelationType.REFERENCES: ["macro"]
                    }
                },
                name="metaprogramming",
                description="Matches metaprogramming constructs",
                examples=["macro m(x) end", ":(1 + 2)", "@m(x)"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.METAPROGRAMMING,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["macro"],
                    "validation": {
                        "required_fields": ["macro_name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_!]*$'
                    }
                }
            )
        },
        PatternPurpose.TYPE_SAFETY: {
            "type_parameterization": QueryPattern(
                pattern="""
                [
                    (parametric_type_expression
                        name: (_) @type.param.name
                        parameters: (type_parameter_list) @type.param.params) @type.param,
                        
                    (struct_definition
                        name: (_) @type.struct.name
                        parameters: (type_parameter_list)? @type.struct.params) @type.struct,
                        
                    (abstract_definition
                        name: (_) @type.abstract.name
                        parameters: (type_parameter_list)? @type.abstract.params) @type.abstract
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "type_parameterization",
                    "uses_parametric_type": "type.param" in node["captures"],
                    "uses_parametric_struct": "type.struct" in node["captures"] and node["captures"].get("type.struct.params", {}).get("text", ""),
                    "uses_parametric_abstract": "type.abstract" in node["captures"] and node["captures"].get("type.abstract.params", {}).get("text", ""),
                    "type_name": (
                        node["captures"].get("type.param.name", {}).get("text", "") or
                        node["captures"].get("type.struct.name", {}).get("text", "") or
                        node["captures"].get("type.abstract.name", {}).get("text", "")
                    ),
                    "parameter_list": (
                        node["captures"].get("type.param.params", {}).get("text", "") or
                        node["captures"].get("type.struct.params", {}).get("text", "") or
                        node["captures"].get("type.abstract.params", {}).get("text", "")
                    ),
                    "is_generic_programming": True
                }
            )
        },
        PatternPurpose.FUNCTIONAL: {
            "functional_patterns": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (identifier) @func.call.name
                        (#match? @func.call.name "^(map|filter|reduce|fold|broadcast|comprehension)") 
                        arguments: (_)* @func.call.args) @func.call,
                        
                    (comprehension_expression
                        generators: (_) @func.comp.gens
                        body: (_) @func.comp.body) @func.comp,
                        
                    (lambda_expression
                        parameters: (_)? @func.lambda.params
                        body: (_) @func.lambda.body) @func.lambda,
                        
                    (binary_expression
                        operator: (operator) @func.pipe.op
                        (#eq? @func.pipe.op "|>")
                        left: (_) @func.pipe.left
                        right: (_) @func.pipe.right) @func.pipe
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "functional_patterns",
                    "uses_higher_order_function": "func.call" in node["captures"],
                    "uses_comprehension": "func.comp" in node["captures"],
                    "uses_lambda": "func.lambda" in node["captures"],
                    "uses_pipe_operator": "func.pipe" in node["captures"],
                    "higher_order_function": node["captures"].get("func.call.name", {}).get("text", ""),
                    "functional_pattern_type": (
                        "higher_order_function" if "func.call" in node["captures"] else
                        "comprehension" if "func.comp" in node["captures"] else
                        "lambda" if "func.lambda" in node["captures"] else
                        "pipe_operator" if "func.pipe" in node["captures"] else
                        "other"
                    )
                }
            )
        }
    }
}

class JuliaPatternLearner(CrossProjectPatternLearner):
    """Enhanced Julia pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Julia-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("julia", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Julia patterns
        await self._pattern_processor.register_language_patterns(
            "julia", 
            JULIA_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "julia_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(JULIA_PATTERNS),
                "capabilities": list(JULIA_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="julia",
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
            
            # Finally add Julia-specific patterns
            async with AsyncErrorBoundary("julia_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "julia",
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
                julia_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(julia_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "julia_pattern_learner",
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
                "julia_pattern_learner",
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
                "julia_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "julia_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_julia_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Julia pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Julia-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("julia", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "julia", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_julia_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"julia_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "julia",
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
        await update_julia_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "julia_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_julia_pattern_context(
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
            language_id="julia",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "julia"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(JULIA_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_julia_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_julia_pattern_match_result(
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
        metadata={"language": "julia"}
    )

# Initialize pattern learner
pattern_learner = JuliaPatternLearner()

async def initialize_julia_patterns():
    """Initialize Julia patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Julia patterns
    await pattern_processor.register_language_patterns(
        "julia",
        JULIA_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": JULIA_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await JuliaPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "julia",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "julia_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(JULIA_PATTERNS),
            "capabilities": list(JULIA_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["type"]
    },
    "struct": {
        PatternRelationType.CONTAINS: ["field"],
        PatternRelationType.DEPENDS_ON: ["type"]
    },
    "module": {
        PatternRelationType.CONTAINS: ["function", "struct", "type", "macro"],
        PatternRelationType.DEPENDS_ON: []
    },
    "macro": {
        PatternRelationType.CONTAINS: ["block"],
        PatternRelationType.REFERENCES: ["macro"]
    },
    "type": {
        PatternRelationType.REFERENCED_BY: ["function", "struct"],
        PatternRelationType.DEPENDS_ON: []
    }
}

# Export public interfaces
__all__ = [
    'JULIA_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_julia_pattern_match_result',
    'update_julia_pattern_metrics',
    'JuliaPatternContext',
    'pattern_learner'
] 