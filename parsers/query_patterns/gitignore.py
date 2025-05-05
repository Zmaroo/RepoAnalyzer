"""Gitignore-specific patterns with enhanced type system and relationships.

This module provides gitignore-specific patterns that integrate with the enhanced
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
from parsers.feature_extractor import FeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# Gitignore capabilities (extends common capabilities)
GITIGNORE_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.VERSION_CONTROL,
    AICapability.FILE_PATTERNS,
    AICapability.CONFIGURATION
}

# Pattern relationships for gitignore
GITIGNORE_PATTERN_RELATIONSHIPS = {
    "pattern": [
        PatternRelationship(
            source_pattern="pattern",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        ),
        PatternRelationship(
            source_pattern="pattern",
            target_pattern="section",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"section_patterns": True}
        )
    ],
    "section": [
        PatternRelationship(
            source_pattern="section",
            target_pattern="pattern",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"section_patterns": True}
        ),
        PatternRelationship(
            source_pattern="section",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ]
}

# Performance metrics tracking for gitignore patterns
GITIGNORE_PATTERN_METRICS = {
    "pattern": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "section": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced gitignore patterns with proper typing and relationships
GITIGNORE_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "pattern": TreeSitterResilientPattern(
                name="pattern",
                pattern="""
                [
                    (pattern) @syntax.pattern.def,
                    (negated_pattern) @syntax.pattern.negated,
                    (directory_pattern) @syntax.pattern.directory
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.95,
                metadata={
                    "relationships": GITIGNORE_PATTERN_RELATIONSHIPS["pattern"],
                    "metrics": GITIGNORE_PATTERN_METRICS["pattern"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "comment": TreeSitterAdaptivePattern(
                name="comment",
                pattern="(comment) @syntax.comment",
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
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
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "section": TreeSitterResilientPattern(
                name="section",
                pattern="(section_header) @semantics.section.header",
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.95,
                metadata={
                    "relationships": GITIGNORE_PATTERN_RELATIONSHIPS["section"],
                    "metrics": GITIGNORE_PATTERN_METRICS["section"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "expression": TreeSitterAdaptivePattern(
                name="expression",
                pattern="""
                [
                    (blank_line) @semantics.expression.blank,
                    (pattern) @semantics.expression.pattern,
                    (negated_pattern) @semantics.expression.negated
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
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
                pattern="(comment) @documentation.comment",
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="pattern",
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
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "root": TreeSitterResilientPattern(
                name="root",
                pattern="(root_gitignore) @structure.root",
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.95,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "global": TreeSitterResilientPattern(
                name="global",
                pattern="(global_gitignore) @structure.global",
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="gitignore",
                confidence=0.95,
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
    """Create pattern context for gitignore files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "gitignore"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(GITIGNORE_PATTERNS.keys())
    )

def get_gitignore_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return GITIGNORE_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_gitignore_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in GITIGNORE_PATTERN_METRICS:
        pattern_metrics = GITIGNORE_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_gitignore_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_gitignore_pattern_relationships(pattern_name),
        performance=GITIGNORE_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "gitignore"}
    )

class GitignorePatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced gitignore pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with gitignore-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = FeatureExtractor("gitignore")
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register gitignore patterns
        self._pattern_processor = await pattern_processor()
        await self._pattern_processor.register_language_patterns(
            "gitignore", 
            GITIGNORE_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "gitignore_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(GITIGNORE_PATTERNS),
                "capabilities": list(GITIGNORE_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="gitignore",
                file_type=FileType.CONFIG,
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
            
            # Finally add gitignore-specific patterns
            async with AsyncErrorBoundary("gitignore_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "gitignore",
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
                gitignore_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(gitignore_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "gitignore_pattern_learner",
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
                "gitignore_pattern_learner",
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
                "gitignore_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "gitignore_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_gitignore_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a gitignore pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to gitignore-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = FeatureExtractor("gitignore")
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "gitignore", FileType.CONFIG)
            if parse_result and parse_result.ast:
                context = await create_gitignore_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"gitignore_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "gitignore",
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
        await update_gitignore_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "gitignore_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_gitignore_pattern_context(
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
            language_id="gitignore",
            file_type=FileType.CONFIG
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "gitignore"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(GITIGNORE_PATTERNS.keys())
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
gitignore_pattern_learner = GitignorePatternLearner()

async def initialize_gitignore_patterns():
    """Initialize gitignore patterns during app startup."""
    global gitignore_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register gitignore patterns
    await pattern_processor.register_language_patterns(
        "gitignore",
        GITIGNORE_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": GITIGNORE_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    gitignore_pattern_learner = await GitignorePatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "gitignore",
        gitignore_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "gitignore_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(GITIGNORE_PATTERNS),
            "capabilities": list(GITIGNORE_CAPABILITIES)
        }
    )

# Export public interfaces
__all__ = [
    'GITIGNORE_PATTERNS',
    'GITIGNORE_PATTERN_RELATIONSHIPS',
    'GITIGNORE_PATTERN_METRICS',
    'create_pattern_context',
    'get_gitignore_pattern_relationships',
    'update_gitignore_pattern_metrics',
    'get_gitignore_pattern_match_result'
]

# Module identification
LANGUAGE = "gitignore" 