"""
Query patterns for Scala files.

This module provides Scala-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "scala"

# Scala capabilities (extends common capabilities)
SCALA_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.OBJECT_ORIENTED,
    AICapability.FUNCTIONAL_PROGRAMMING,
    AICapability.TYPE_CLASSES
}

@dataclass
class ScalaPatternContext(PatternContext):
    """Scala-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    trait_names: Set[str] = field(default_factory=set)
    object_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    package_names: Set[str] = field(default_factory=set)
    has_implicits: bool = False
    has_case_classes: bool = False
    has_type_classes: bool = False
    has_for_comprehension: bool = False
    has_pattern_matching: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_implicits}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "trait": PatternPerformanceMetrics(),
    "object": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "package": PatternPerformanceMetrics()
}

SCALA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_definition
                        modifiers: [(case) (abstract)]* @syntax.class.modifier
                        name: (identifier) @syntax.class.name
                        type_parameters: (type_parameters)? @syntax.class.type_params
                        parameters: (parameters)? @syntax.class.params
                        extends: (extends_clause)? @syntax.class.extends
                        body: (template_body)? @syntax.class.body) @syntax.class.def,
                    (object_definition
                        name: (identifier) @syntax.object.name
                        extends: (extends_clause)? @syntax.object.extends
                        body: (template_body)? @syntax.object.body) @syntax.object.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.object.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.object.def", {}).get("start_point", [0])[0]
                    ),
                    "is_case": "case" in (node["captures"].get("syntax.class.modifier", {}).get("text", "") or ""),
                    "is_abstract": "abstract" in (node["captures"].get("syntax.class.modifier", {}).get("text", "") or ""),
                    "is_object": "syntax.object.def" in node["captures"],
                    "has_type_params": "syntax.class.type_params" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "field", "type"],
                        PatternRelationType.DEPENDS_ON: ["trait", "class"]
                    }
                },
                name="class",
                description="Matches Scala class and object declarations",
                examples=["class Point[T](x: T, y: T)", "case class Person(name: String)", "object Main"],
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
            "trait": ResilientPattern(
                pattern="""
                [
                    (trait_definition
                        name: (identifier) @syntax.trait.name
                        type_parameters: (type_parameters)? @syntax.trait.type_params
                        extends: (extends_clause)? @syntax.trait.extends
                        body: (template_body)? @syntax.trait.body) @syntax.trait.def
                ]
                """,
                extract=lambda node: {
                    "type": "trait",
                    "name": node["captures"].get("syntax.trait.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.trait.def", {}).get("start_point", [0])[0],
                    "has_type_params": "syntax.trait.type_params" in node["captures"],
                    "has_extends": "syntax.trait.extends" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "type", "abstract"],
                        PatternRelationType.DEPENDS_ON: ["trait"]
                    }
                },
                name="trait",
                description="Matches Scala trait declarations",
                examples=["trait Printable[T]", "trait Monad[F[_]] extends Functor[F]"],
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
            ),
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        modifiers: [(implicit) (override)]* @syntax.func.modifier
                        name: (identifier) @syntax.func.name
                        type_parameters: (type_parameters)? @syntax.func.type_params
                        parameters: (parameters)? @syntax.func.params
                        return_type: (type_annotation)? @syntax.func.return
                        body: (_)? @syntax.func.body) @syntax.func.def,
                    (val_definition
                        pattern: (identifier) @syntax.val.name
                        type_annotation: (type_annotation)? @syntax.val.type
                        value: (_)? @syntax.val.value) @syntax.val.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.val.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.val.def", {}).get("start_point", [0])[0]
                    ),
                    "is_implicit": "implicit" in (node["captures"].get("syntax.func.modifier", {}).get("text", "") or ""),
                    "is_override": "override" in (node["captures"].get("syntax.func.modifier", {}).get("text", "") or ""),
                    "is_val": "syntax.val.def" in node["captures"],
                    "has_type_params": "syntax.func.type_params" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "expression"],
                        PatternRelationType.DEPENDS_ON: ["type", "class"]
                    }
                },
                name="function",
                description="Matches Scala function and value declarations",
                examples=["def process[T](data: T): Option[T]", "implicit val ordering: Ordering[Int]"],
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
        PatternPurpose.PACKAGES: {
            "package": AdaptivePattern(
                pattern="""
                [
                    (package_clause
                        name: (identifier) @pkg.name) @pkg.def,
                    (import_declaration
                        path: (identifier) @pkg.import.path
                        selectors: (import_selectors)? @pkg.import.selectors) @pkg.import.def
                ]
                """,
                extract=lambda node: {
                    "type": "package",
                    "name": (
                        node["captures"].get("pkg.name", {}).get("text", "") or
                        node["captures"].get("pkg.import.path", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("pkg.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("pkg.import.def", {}).get("start_point", [0])[0]
                    ),
                    "is_import": "pkg.import.def" in node["captures"],
                    "has_selectors": "pkg.import.selectors" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["class", "trait", "object"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="package",
                description="Matches Scala package declarations and imports",
                examples=["package com.example", "import scala.collection.mutable"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PACKAGES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["package"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-zA-Z0-9_.]*$'
                    }
                }
            )
        }
    }
}

class ScalaPatternLearner(CrossProjectPatternLearner):
    """Enhanced Scala pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Scala-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("scala", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Scala patterns
        await self._pattern_processor.register_language_patterns(
            "scala", 
            SCALA_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "scala_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(SCALA_PATTERNS),
                "capabilities": list(SCALA_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="scala",
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
            
            # Finally add Scala-specific patterns
            async with AsyncErrorBoundary("scala_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "scala",
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
                scala_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(scala_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "scala_pattern_learner",
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
                "scala_pattern_learner",
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
                "scala_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "scala_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_scala_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Scala pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Scala-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("scala", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "scala", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_scala_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"scala_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "scala",
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
        await update_scala_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "scala_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_scala_pattern_context(
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
            language_id="scala",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "scala"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(SCALA_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_scala_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_scala_pattern_match_result(
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
        metadata={"language": "scala"}
    )

# Initialize pattern learner
pattern_learner = ScalaPatternLearner()

async def initialize_scala_patterns():
    """Initialize Scala patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Scala patterns
    await pattern_processor.register_language_patterns(
        "scala",
        SCALA_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": SCALA_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await ScalaPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "scala",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "scala_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(SCALA_PATTERNS),
            "capabilities": list(SCALA_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "field", "type"],
        PatternRelationType.DEPENDS_ON: ["trait", "class"]
    },
    "trait": {
        PatternRelationType.CONTAINS: ["method", "type", "abstract"],
        PatternRelationType.DEPENDS_ON: ["trait"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "expression"],
        PatternRelationType.DEPENDS_ON: ["type", "class"]
    },
    "package": {
        PatternRelationType.CONTAINS: ["class", "trait", "object"],
        PatternRelationType.DEPENDS_ON: ["package"]
    }
}

# Export public interfaces
__all__ = [
    'SCALA_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_scala_pattern_match_result',
    'update_scala_pattern_metrics',
    'ScalaPatternContext',
    'pattern_learner'
] 