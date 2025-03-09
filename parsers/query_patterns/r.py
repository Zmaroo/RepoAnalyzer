"""
Query patterns for R files.

This module provides R-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "r"

# R capabilities (extends common capabilities)
R_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.DATA_ANALYSIS,
    AICapability.STATISTICAL_COMPUTING,
    AICapability.VISUALIZATION
}

@dataclass
class RPatternContext(PatternContext):
    """R-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    package_names: Set[str] = field(default_factory=set)
    class_names: Set[str] = field(default_factory=set)
    has_s3_classes: bool = False
    has_s4_classes: bool = False
    has_r6_classes: bool = False
    has_tidyverse: bool = False
    has_data_table: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{self.has_tidyverse}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "class": PatternPerformanceMetrics(),
    "package": PatternPerformanceMetrics(),
    "pipe": PatternPerformanceMetrics(),
    "data": PatternPerformanceMetrics()
}

R_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @syntax.func.name
                        parameters: (formal_parameters) @syntax.func.params
                        body: (brace_list) @syntax.func.body) @syntax.func.def,
                    (left_assignment
                        name: (identifier) @syntax.func.assign.name
                        value: (function_definition
                            parameters: (formal_parameters) @syntax.func.assign.params
                            body: (brace_list) @syntax.func.assign.body)) @syntax.func.assign.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.func.assign.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_assigned": "syntax.func.assign.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["package", "function"]
                    }
                },
                name="function",
                description="Matches R function declarations",
                examples=["function(x) { x * 2 }", "my_func <- function(data) { }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_.][a-zA-Z0-9_.]*$'
                    }
                }
            ),
            "class": ResilientPattern(
                pattern="""
                [
                    (function_call
                        function: (identifier) @syntax.class.s3.name
                        arguments: (arguments
                            (identifier) @syntax.class.s3.class) @syntax.class.s3.args) @syntax.class.s3.def
                        (#match? @syntax.class.s3.name "^class$"),
                    (function_call
                        function: (identifier) @syntax.class.s4.name
                        arguments: (arguments) @syntax.class.s4.args) @syntax.class.s4.def
                        (#match? @syntax.class.s4.name "^setClass$"),
                    (function_call
                        function: (identifier) @syntax.class.r6.name
                        arguments: (arguments) @syntax.class.r6.args) @syntax.class.r6.def
                        (#match? @syntax.class.r6.name "^R6Class$")
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "line_number": (
                        node["captures"].get("syntax.class.s3.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.class.s4.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.class.r6.def", {}).get("start_point", [0])[0]
                    ),
                    "class_type": (
                        "s3" if "syntax.class.s3.def" in node["captures"] else
                        "s4" if "syntax.class.s4.def" in node["captures"] else
                        "r6" if "syntax.class.r6.def" in node["captures"] else
                        "unknown"
                    ),
                    "name": (
                        node["captures"].get("syntax.class.s3.class", {}).get("text", "") or
                        node["captures"].get("syntax.class.s4.args", {}).get("text", "") or
                        node["captures"].get("syntax.class.r6.args", {}).get("text", "")
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "field"],
                        PatternRelationType.DEPENDS_ON: ["package", "class"]
                    }
                },
                name="class",
                description="Matches R class declarations (S3, S4, R6)",
                examples=[
                    "class(obj) <- 'MyClass'",
                    "setClass('Person', slots = c(name = 'character'))",
                    "MyClass <- R6Class('MyClass')"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["class"],
                    "validation": {
                        "required_fields": ["name", "class_type"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.PACKAGES: {
            "package": AdaptivePattern(
                pattern="""
                [
                    (function_call
                        function: (identifier) @pkg.lib.name
                        arguments: (arguments
                            (string) @pkg.lib.arg) @pkg.lib.args) @pkg.lib.def
                        (#match? @pkg.lib.name "^library|require$"),
                    (namespace_get
                        namespace: (identifier) @pkg.ns.name
                        function: (identifier) @pkg.ns.func) @pkg.ns.def
                ]
                """,
                extract=lambda node: {
                    "type": "package",
                    "line_number": (
                        node["captures"].get("pkg.lib.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("pkg.ns.def", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("pkg.lib.arg", {}).get("text", "") or
                        node["captures"].get("pkg.ns.name", {}).get("text", "")
                    ),
                    "is_namespace": "pkg.ns.def" in node["captures"],
                    "function": node["captures"].get("pkg.ns.func", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.PROVIDES: ["function", "class", "data"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="package",
                description="Matches R package imports and namespace usage",
                examples=["library(dplyr)", "require('data.table')", "dplyr::filter"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PACKAGES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["package"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z][a-zA-Z0-9.]*$'
                    }
                }
            )
        },
        PatternPurpose.DATA_MANIPULATION: {
            "pipe": AdaptivePattern(
                pattern="""
                [
                    (pipe
                        left: (_) @pipe.left
                        right: (_) @pipe.right) @pipe.def,
                    (native_pipe
                        left: (_) @pipe.native.left
                        right: (_) @pipe.native.right) @pipe.native.def
                ]
                """,
                extract=lambda node: {
                    "type": "pipe",
                    "line_number": (
                        node["captures"].get("pipe.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("pipe.native.def", {}).get("start_point", [0])[0]
                    ),
                    "is_native": "pipe.native.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONNECTS: ["function", "data"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="pipe",
                description="Matches R pipe operators",
                examples=["data %>% filter()", "data |> select()"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.DATA_MANIPULATION,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["pipe"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    }
}

class RPatternLearner(CrossProjectPatternLearner):
    """Enhanced R pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with R-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("r", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register R patterns
        await self._pattern_processor.register_language_patterns(
            "r", 
            R_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "r_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(R_PATTERNS),
                "capabilities": list(R_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="r",
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
            
            # Finally add R-specific patterns
            async with AsyncErrorBoundary("r_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "r",
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
                r_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(r_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "r_pattern_learner",
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
                "r_pattern_learner",
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
                "r_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "r_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_r_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process an R pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to R-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("r", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "r", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_r_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"r_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "r",
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
        await update_r_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "r_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_r_pattern_context(
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
            language_id="r",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "r"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(R_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_r_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_r_pattern_match_result(
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
        metadata={"language": "r"}
    )

# Initialize pattern learner
pattern_learner = RPatternLearner()

async def initialize_r_patterns():
    """Initialize R patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register R patterns
    await pattern_processor.register_language_patterns(
        "r",
        R_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": R_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await RPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "r",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "r_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(R_PATTERNS),
            "capabilities": list(R_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["package", "function"]
    },
    "class": {
        PatternRelationType.CONTAINS: ["method", "field"],
        PatternRelationType.DEPENDS_ON: ["package", "class"]
    },
    "package": {
        PatternRelationType.PROVIDES: ["function", "class", "data"],
        PatternRelationType.DEPENDS_ON: ["package"]
    },
    "pipe": {
        PatternRelationType.CONNECTS: ["function", "data"],
        PatternRelationType.DEPENDS_ON: ["package"]
    }
}

# Export public interfaces
__all__ = [
    'R_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_r_pattern_match_result',
    'update_r_pattern_metrics',
    'RPatternContext',
    'pattern_learner'
] 