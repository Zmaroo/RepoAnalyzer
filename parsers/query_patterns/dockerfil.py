"""Dockerfile-specific patterns with enhanced type system and relationships.

This module provides Dockerfile-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
The module is named 'dockerfil' to avoid conflicts with 'dockerfile' while maintaining
alignment with tree-sitter-language-pack's 'dockerfile' grammar.
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
from parsers.query_patterns.enhanced_patterns import TreeSitterAdaptivePattern, TreeSitterResilientPattern, TreeSitterCrossProjectPatternLearner
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

# Dockerfile capabilities (extends common capabilities)
DOCKERFILE_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.CONTAINERIZATION,
    AICapability.CONFIGURATION,
    AICapability.DEPLOYMENT
}

# Pattern relationships for Dockerfile
DOCKERFILE_PATTERN_RELATIONSHIPS = {
    "instruction": [
        PatternRelationship(
            source_pattern="instruction",
            target_pattern="variable",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"variables": True}
        ),
        PatternRelationship(
            source_pattern="instruction",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "base_image": [
        PatternRelationship(
            source_pattern="base_image",
            target_pattern="instruction",
            relationship_type=PatternRelationType.DEPENDS_ON,
            confidence=0.95,
            metadata={"from": True}
        )
    ],
    "expose": [
        PatternRelationship(
            source_pattern="expose",
            target_pattern="variable",
            relationship_type=PatternRelationType.USES,
            confidence=0.85,
            metadata={"port_vars": True}
        )
    ]
}

# Performance metrics tracking for Dockerfile patterns
DOCKERFILE_PATTERN_METRICS = {
    "instruction": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "base_image": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "expose": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced Dockerfile patterns with proper typing and relationships
DOCKERFILE_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "instruction": TreeSitterResilientPattern(
                name="instruction",
                pattern="""
                [
                    (instruction
                        name: (identifier) @syntax.instruction.name
                        value: (_) @syntax.instruction.value) @syntax.instruction.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
                confidence=0.95,
                metadata={
                    "relationships": DOCKERFILE_PATTERN_RELATIONSHIPS["instruction"],
                    "metrics": DOCKERFILE_PATTERN_METRICS["instruction"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "base_image": TreeSitterResilientPattern(
                name="base_image",
                pattern="""
                [
                    (from_instruction
                        image: (image_spec
                            name: (image_name) @syntax.image.name
                            tag: (image_tag)? @syntax.image.tag
                            digest: (image_digest)? @syntax.image.digest)
                        platform: (platform)? @syntax.image.platform
                        as: (image_alias)? @syntax.image.alias) @syntax.image.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
                confidence=0.95,
                metadata={
                    "relationships": DOCKERFILE_PATTERN_RELATIONSHIPS["base_image"],
                    "metrics": DOCKERFILE_PATTERN_METRICS["base_image"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "expose": TreeSitterResilientPattern(
                name="expose",
                pattern="""
                [
                    (expose_instruction
                        ports: (port_list
                            (port) @syntax.port.value
                            (port_protocol)? @syntax.port.protocol)*) @syntax.expose.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
                confidence=0.95,
                metadata={
                    "relationships": DOCKERFILE_PATTERN_RELATIONSHIPS["expose"],
                    "metrics": DOCKERFILE_PATTERN_METRICS["expose"],
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
                    (comment_line) @documentation.comment.line
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="instruction",
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
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": TreeSitterAdaptivePattern(
                name="variable",
                pattern="""
                [
                    (expansion
                        name: (variable) @semantics.var.name
                        default: (default_value)? @semantics.var.default) @semantics.var.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="dockerfile",
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
    """Create pattern context for Dockerfile files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "dockerfile"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(DOCKERFILE_PATTERNS.keys())
    )

def get_dockerfile_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return DOCKERFILE_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_dockerfile_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in DOCKERFILE_PATTERN_METRICS:
        pattern_metrics = DOCKERFILE_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_dockerfile_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_dockerfile_pattern_relationships(pattern_name),
        performance=DOCKERFILE_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "dockerfile"}
    )

class DockerfilePatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced Dockerfile pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Dockerfile-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await get_feature_extractor("dockerfile")
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Dockerfile patterns
        from parsers.pattern_processor import pattern_processor
        await pattern_processor.register_language_patterns(
            "dockerfile", 
            DOCKERFILE_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "dockerfile_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(DOCKERFILE_PATTERNS),
                "capabilities": list(DOCKERFILE_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="dockerfile",
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
            
            # Finally add Dockerfile-specific patterns
            async with AsyncErrorBoundary("dockerfile_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "dockerfile",
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
                dockerfile_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(dockerfile_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "dockerfile_pattern_learner",
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
                "dockerfile_pattern_learner",
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
                "dockerfile_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "dockerfile_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_dockerfile_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Dockerfile pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Dockerfile-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await get_feature_extractor("dockerfile")
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "dockerfile", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_dockerfile_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"dockerfile_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "dockerfile",
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
        await update_dockerfile_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "dockerfile_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_dockerfile_pattern_context(
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
            language_id="dockerfile",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "dockerfile"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(DOCKERFILE_PATTERNS.keys())
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
dockerfile_pattern_learner = DockerfilePatternLearner()

async def initialize_dockerfile_patterns():
    """Initialize Dockerfile patterns during app startup."""
    global dockerfile_pattern_learner
    
    # Initialize pattern processor first
    from parsers.pattern_processor import pattern_processor
    await pattern_processor.initialize()
    
    # Register Dockerfile patterns
    await pattern_processor.register_language_patterns(
        "dockerfile",
        DOCKERFILE_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": DOCKERFILE_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    dockerfile_pattern_learner = await DockerfilePatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "dockerfile",
        dockerfile_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "dockerfile_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(DOCKERFILE_PATTERNS),
            "capabilities": list(DOCKERFILE_CAPABILITIES)
        }
    )

# Export public interfaces
__all__ = [
    'DOCKERFILE_PATTERNS',
    'DOCKERFILE_PATTERN_RELATIONSHIPS',
    'DOCKERFILE_PATTERN_METRICS',
    'create_pattern_context',
    'get_dockerfile_pattern_relationships',
    'update_dockerfile_pattern_metrics',
    'get_dockerfile_pattern_match_result'
]

# Module identification
LANGUAGE = "dockerfile" 