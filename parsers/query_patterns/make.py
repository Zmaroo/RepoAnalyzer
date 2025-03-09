"""Query patterns for Make files.

This module provides Make-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "make"

# Make capabilities (extends common capabilities)
MAKE_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.BUILD_SYSTEM,
    AICapability.PATTERN_RULES,
    AICapability.DEPENDENCY_MANAGEMENT
}

@dataclass
class MakePatternContext(PatternContext):
    """Make-specific pattern context."""
    target_names: Set[str] = field(default_factory=set)
    variable_names: Set[str] = field(default_factory=set)
    include_paths: Set[str] = field(default_factory=set)
    has_phony_targets: bool = False
    has_pattern_rules: bool = False
    has_conditionals: bool = False
    has_functions: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.target_names)}:{self.has_pattern_rules}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "target": PatternPerformanceMetrics(),
    "variable": PatternPerformanceMetrics(),
    "include": PatternPerformanceMetrics(),
    "rule": PatternPerformanceMetrics()
}

MAKE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "target": ResilientPattern(
                pattern="""
                [
                    (rule
                        targets: (targets
                            (word) @syntax.target.name)
                        prerequisites: (prerequisites
                            (word)* @syntax.target.prereq)
                        recipe: (recipe
                            (shell_command)* @syntax.target.recipe)) @syntax.target.def,
                    (phony_declaration
                        targets: (word) @syntax.phony.name) @syntax.phony.def
                ]
                """,
                extract=lambda node: {
                    "type": "target",
                    "name": (
                        node["captures"].get("syntax.target.name", {}).get("text", "") or
                        node["captures"].get("syntax.phony.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.target.def", {}).get("start_point", [0])[0],
                    "is_phony": "syntax.phony.def" in node["captures"],
                    "prerequisite_count": len(node["captures"].get("syntax.target.prereq", [])),
                    "recipe_count": len(node["captures"].get("syntax.target.recipe", [])),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["target"],
                        PatternRelationType.REFERENCES: ["variable"]
                    }
                },
                name="target",
                description="Matches Make targets and rules",
                examples=["target: deps\n\tcommand", ".PHONY: clean"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["target"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_\-.]+$'
                    }
                }
            ),
            "variable": ResilientPattern(
                pattern="""
                [
                    (variable_assignment
                        name: (word) @syntax.var.name
                        value: (text) @syntax.var.value) @syntax.var.def,
                    (conditional_variable_assignment
                        name: (word) @syntax.cond.name
                        value: (text) @syntax.cond.value) @syntax.cond.def
                ]
                """,
                extract=lambda node: {
                    "type": "variable",
                    "name": (
                        node["captures"].get("syntax.var.name", {}).get("text", "") or
                        node["captures"].get("syntax.cond.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.var.def", {}).get("start_point", [0])[0],
                    "is_conditional": "syntax.cond.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["target", "variable"],
                        PatternRelationType.DEPENDS_ON: ["variable"]
                    }
                },
                name="variable",
                description="Matches Make variable assignments",
                examples=["VAR = value", "VAR ?= default"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["variable"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Za-z_][A-Za-z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.PATTERN_RULES: {
            "pattern_rule": AdaptivePattern(
                pattern="""
                [
                    (rule
                        targets: (targets
                            (word) @pattern.target.name
                            (#match? @pattern.target.name "%"))
                        prerequisites: (prerequisites
                            (word)* @pattern.target.prereq)
                        recipe: (recipe
                            (shell_command)* @pattern.target.recipe)) @pattern.target.def,
                        
                    (variable_reference
                        name: (word) @pattern.var.name
                        (#match? @pattern.var.name "\\$[@%<]")) @pattern.var.ref
                ]
                """,
                extract=lambda node: {
                    "type": "pattern_rule",
                    "line_number": node["captures"].get("pattern.target.def", {}).get("start_point", [0])[0],
                    "uses_pattern_target": "%" in (node["captures"].get("pattern.target.name", {}).get("text", "") or ""),
                    "uses_automatic_var": "pattern.var.ref" in node["captures"],
                    "automatic_var": node["captures"].get("pattern.var.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["target"],
                        PatternRelationType.REFERENCES: ["variable"]
                    }
                },
                name="pattern_rule",
                description="Matches pattern rules and automatic variables",
                examples=["%.o: %.c\n\t$(CC) -c $<", "%.pdf: %.tex\n\t$(TEX) $<"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PATTERN_RULES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["rule"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z0-9_\-.%]+$'
                    }
                }
            )
        },
        PatternPurpose.INCLUDES: {
            "include": AdaptivePattern(
                pattern="""
                [
                    (include_statement
                        files: (word)* @include.file.name) @include.def,
                        
                    (conditional_include_statement
                        files: (word)* @include.cond.name) @include.cond.def,
                        
                    (sinclude_statement
                        files: (word)* @include.silent.name) @include.silent.def
                ]
                """,
                extract=lambda node: {
                    "type": "include",
                    "line_number": node["captures"].get("include.def", {}).get("start_point", [0])[0],
                    "is_conditional": "include.cond.def" in node["captures"],
                    "is_silent": "include.silent.def" in node["captures"],
                    "included_files": [
                        file.get("text", "") for file in (
                            node["captures"].get("include.file.name", []) or
                            node["captures"].get("include.cond.name", []) or
                            node["captures"].get("include.silent.name", [])
                        )
                    ],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["variable"],
                        PatternRelationType.REFERENCES: ["include"]
                    }
                },
                name="include",
                description="Matches include statements",
                examples=["include config.mk", "-include *.d", "sinclude common.mk"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.INCLUDES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["include"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z0-9_\-.*]+\.mk$'
                    }
                }
            )
        }
    }
}

class MakePatternLearner(CrossProjectPatternLearner):
    """Enhanced Make pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Make-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("make", FileType.BUILD)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Make patterns
        await self._pattern_processor.register_language_patterns(
            "make", 
            MAKE_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "make_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(MAKE_PATTERNS),
                "capabilities": list(MAKE_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="make",
                file_type=FileType.BUILD,
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
            
            # Finally add Make-specific patterns
            async with AsyncErrorBoundary("make_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "make",
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
                make_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(make_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "make_pattern_learner",
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
                "make_pattern_learner",
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
                "make_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "make_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_make_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Make pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Make-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("make", FileType.BUILD)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "make", FileType.BUILD)
            if parse_result and parse_result.ast:
                context = await create_make_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"make_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "make",
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
        await update_make_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "make_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_make_pattern_context(
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
            language_id="make",
            file_type=FileType.BUILD
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "make"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(MAKE_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_make_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_make_pattern_match_result(
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
        metadata={"language": "make"}
    )

# Initialize pattern learner
pattern_learner = MakePatternLearner()

async def initialize_make_patterns():
    """Initialize Make patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Make patterns
    await pattern_processor.register_language_patterns(
        "make",
        MAKE_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": MAKE_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await MakePatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "make",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "make_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(MAKE_PATTERNS),
            "capabilities": list(MAKE_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "target": {
        PatternRelationType.DEPENDS_ON: ["target"],
        PatternRelationType.REFERENCES: ["variable"]
    },
    "variable": {
        PatternRelationType.REFERENCED_BY: ["target", "variable"],
        PatternRelationType.DEPENDS_ON: ["variable"]
    },
    "pattern_rule": {
        PatternRelationType.DEPENDS_ON: ["target"],
        PatternRelationType.REFERENCES: ["variable"]
    },
    "include": {
        PatternRelationType.DEPENDS_ON: ["variable"],
        PatternRelationType.REFERENCES: ["include"]
    }
}

# Export public interfaces
__all__ = [
    'MAKE_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_make_pattern_match_result',
    'update_make_pattern_metrics',
    'MakePatternContext',
    'pattern_learner'
]