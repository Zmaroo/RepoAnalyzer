"""CMake-specific patterns with enhanced type system and relationships.

This module provides CMake-specific patterns that integrate with the enhanced
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

# Module identification
LANGUAGE = "cmake"

# CMake capabilities (extends common capabilities)
CMAKE_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.BUILD_SYSTEM,
    AICapability.CONFIGURATION
}

# Pattern relationships for CMake
CMAKE_PATTERN_RELATIONSHIPS = {
    "function_definition": [
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="command",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.9,
            metadata={"commands": True}
        ),
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "control_flow": [
        PatternRelationship(
            source_pattern="control_flow",
            target_pattern="command",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"flow_control": True}
        )
    ],
    "variable": [
        PatternRelationship(
            source_pattern="variable",
            target_pattern="command",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"variable_usage": True}
        )
    ]
}

# Performance metrics tracking for CMake patterns
CMAKE_PATTERN_METRICS = {
    "function_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "control_flow": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "variable": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced CMake patterns with proper typing and relationships
CMAKE_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function_definition": TreeSitterResilientPattern(
                name="function_definition",
                pattern="""
                [
                    (function_def
                        (function_command
                            (argument_list) @syntax.function.args) @syntax.function.header
                        (body) @syntax.function.body
                        (endfunction_command) @syntax.function.end) @syntax.function.def,
                    
                    (macro_def
                        (macro_command
                            (argument_list) @syntax.macro.args) @syntax.macro.header
                        (body) @syntax.macro.body
                        (endmacro_command) @syntax.macro.end) @syntax.macro.def,
                    
                    (normal_command
                        (identifier) @syntax.command.name
                        (argument_list) @syntax.command.args) @syntax.command.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
                confidence=0.95,
                metadata={
                    "relationships": CMAKE_PATTERN_RELATIONSHIPS["function_definition"],
                    "metrics": CMAKE_PATTERN_METRICS["function_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "control_flow": TreeSitterResilientPattern(
                name="control_flow",
                pattern="""
                [
                    (if_condition
                        (if_command
                            (argument_list) @syntax.if.condition) @syntax.if.start
                        (body) @syntax.if.body
                        [(elseif_command
                            (argument_list) @syntax.if.elseif.condition) @syntax.if.elseif
                         (else_command) @syntax.if.else]*
                        (endif_command) @syntax.if.end) @syntax.if.def,
                    
                    (foreach_loop
                        (foreach_command
                            (argument_list) @syntax.foreach.args) @syntax.foreach.start
                        (body) @syntax.foreach.body
                        (endforeach_command) @syntax.foreach.end) @syntax.foreach.def,
                    
                    (while_loop
                        (while_command
                            (argument_list) @syntax.while.condition) @syntax.while.start
                        (body) @syntax.while.body
                        (endwhile_command) @syntax.while.end) @syntax.while.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
                confidence=0.95,
                metadata={
                    "relationships": CMAKE_PATTERN_RELATIONSHIPS["control_flow"],
                    "metrics": CMAKE_PATTERN_METRICS["control_flow"],
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
            "variable": QueryPattern(
                name="variable",
                pattern="""
                [
                    (variable_ref
                        [(normal_var
                            (variable) @semantics.var.name) @semantics.var.normal
                         (env_var
                            (variable) @semantics.var.env.name) @semantics.var.env
                         (cache_var
                            (variable) @semantics.var.cache.name) @semantics.var.cache]) @semantics.var.ref
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
                confidence=0.95,
                metadata={
                    "relationships": CMAKE_PATTERN_RELATIONSHIPS["variable"],
                    "metrics": CMAKE_PATTERN_METRICS["variable"],
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
            "block": TreeSitterAdaptivePattern(
                name="block",
                pattern="""
                [
                    (block_def
                        (block_command
                            (argument_list) @structure.block.args) @structure.block.start
                            (body) @structure.block.body
                            (endblock_command) @structure.block.end) @structure.block.def
                ]
                """,
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
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
                    (bracket_comment) @documentation.comment.bracket
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cmake",
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
    },

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        # The following patterns were using regexes, which is not allowed for CMake (tree-sitter only). Commented out for correctness.
        # "invalid_target": QueryPattern(
        #     name="invalid_target",
        #     pattern=r'add_(?:executable|library)\s*\(\s*([^\s)]+)',
        #     extract=lambda m: {
        #         "type": "invalid_target",
        #         "target": m.group(1),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "needs_verification": True
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id=LANGUAGE,
        #     metadata={"description": "Detects potentially invalid targets", "examples": ["add_executable(target)"]}
        # ),
        # "missing_dependency": QueryPattern(
        #     name="missing_dependency",
        #     pattern=r'target_link_libraries\s*\(\s*([^\s)]+)\s+([^)]+)\)',
        #     extract=lambda m: {
        #         "type": "missing_dependency",
        #         "target": m.group(1),
        #         "dependencies": m.group(2),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "needs_verification": True
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id=LANGUAGE,
        #     metadata={"description": "Detects potentially missing dependencies", "examples": ["target_link_libraries(target dep)"]}
        # ),
        # "undefined_variable": QueryPattern(
        #     name="undefined_variable",
        #     pattern=r'\${([^}]+)}',
        #     extract=lambda m: {
        #         "type": "undefined_variable",
        #         "variable": m.group(1),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "needs_verification": True
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id=LANGUAGE,
        #     metadata={"description": "Detects potentially undefined variables", "examples": ["${UNDEFINED_VAR}"]}
        # ),
        # "circular_dependency": QueryPattern(
        #     name="circular_dependency",
        #     pattern=r'target_link_libraries\s*\(\s*([^\s)]+)[^)]*\1[^)]*\)',
        #     extract=lambda m: {
        #         "type": "circular_dependency",
        #         "target": m.group(1),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "confidence": 0.9
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id=LANGUAGE,
        #     metadata={"description": "Detects potential circular dependencies", "examples": ["target_link_libraries(target target)"]}
        # ),
        # "invalid_command": QueryPattern(
        #     name="invalid_command",
        #     pattern=r'^([a-z_]+)\s*\(',
        #     extract=lambda m: {
        #         "type": "invalid_command",
        #         "command": m.group(1),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "needs_verification": True
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id=LANGUAGE,
        #     metadata={"description": "Detects potentially invalid commands", "examples": ["invalid_command()"]}
        # ),
    }
}

def create_pattern_context(file_path: str, code_structure: Dict[str, Any]) -> PatternContext:
    """Create pattern context for CMake files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "cmake", "version": "3.0+"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CMAKE_PATTERNS.keys())
    )

def get_cmake_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return CMAKE_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_cmake_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in CMAKE_PATTERN_METRICS:
        pattern_metrics = CMAKE_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_cmake_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_cmake_pattern_relationships(pattern_name),
        performance=CMAKE_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "cmake"}
    )

# Export public interfaces
__all__ = [
    'CMAKE_PATTERNS',
    'CMAKE_PATTERN_RELATIONSHIPS',
    'CMAKE_PATTERN_METRICS',
    'create_pattern_context',
    'get_cmake_pattern_relationships',
    'update_cmake_pattern_metrics',
    'get_cmake_pattern_match_result'
]

class CMakePatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced CMake pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with CMake-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await get_feature_extractor("cmake")
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register CMake patterns
        from parsers.pattern_processor import pattern_processor
        self._pattern_processor = pattern_processor
        await self._pattern_processor.register_language_patterns(
            "cmake", 
            CMAKE_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "cmake_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(CMAKE_PATTERNS),
                "capabilities": list(CMAKE_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="cmake",
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
            
            # Finally add CMake-specific patterns
            async with AsyncErrorBoundary("cmake_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "cmake",
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
                cmake_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(cmake_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "cmake_pattern_learner",
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
                "cmake_pattern_learner",
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
                "cmake_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "cmake_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_cmake_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a CMake pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to CMake-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await get_feature_extractor("cmake")
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "cmake", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_cmake_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"cmake_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "cmake",
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
        await update_cmake_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "cmake_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_cmake_pattern_context(
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
            language_id="cmake",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "cmake", "version": "3.0+"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CMAKE_PATTERNS.keys())
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
cmake_pattern_learner = CMakePatternLearner()

async def initialize_cmake_patterns():
    """Initialize CMake patterns during app startup."""
    global cmake_pattern_learner
    from parsers.pattern_processor import pattern_processor
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register CMake patterns
    await pattern_processor.register_language_patterns(
        "cmake",
        CMAKE_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": CMAKE_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    cmake_pattern_learner = await CMakePatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "cmake",
        cmake_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "cmake_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(CMAKE_PATTERNS),
            "capabilities": list(CMAKE_CAPABILITIES)
        }
    ) 