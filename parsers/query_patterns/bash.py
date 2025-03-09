"""Bash-specific patterns with enhanced type system and relationships.

This module provides Bash-specific patterns that integrate with the enhanced
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
from .common import (
    COMMON_PATTERNS, COMMON_CAPABILITIES,
    process_common_pattern, validate_common_pattern
)
from .enhanced_patterns import AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request
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

# Bash capabilities (extends common capabilities)
BASH_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.SHELL_SCRIPTING,
    AICapability.PROCESS_MANAGEMENT
}

# Pattern relationships for Bash
BASH_PATTERN_RELATIONSHIPS = {
    "function_definition": [
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "variable_assignment": [
        PatternRelationship(
            source_pattern="variable_assignment",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "control_flow": [
        PatternRelationship(
            source_pattern="control_flow",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ]
}

# Performance metrics tracking for Bash patterns
BASH_PATTERN_METRICS = {
    "function_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "variable_assignment": PatternPerformanceMetrics(
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
    )
}

# Enhanced Bash patterns with proper typing and relationships
BASH_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            **COMMON_PATTERNS[PatternCategory.SYNTAX][PatternPurpose.UNDERSTANDING],  # Inherit common syntax patterns
            "function_definition": ResilientPattern(
                name="function_definition",
                pattern="""
                [
                    (function_definition
                        name: (word) @syntax.function.name
                        body: (compound_statement) @syntax.function.body) @syntax.function.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="bash",
                confidence=0.95,
                metadata={
                    "relationships": BASH_PATTERN_RELATIONSHIPS["function_definition"],
                    "metrics": BASH_PATTERN_METRICS["function_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "control_flow": ResilientPattern(
                name="control_flow",
                pattern="""
                [
                    (if_statement
                        condition: (_) @syntax.if.condition
                        consequence: (_) @syntax.if.then
                        alternative: (_)? @syntax.if.else) @syntax.if.statement,
                    
                    (for_statement
                        variable: (_) @syntax.for.variable
                        value: (_) @syntax.for.value
                        body: (_) @syntax.for.body) @syntax.for.statement,
                    
                    (while_statement
                        condition: (_) @syntax.while.condition
                        body: (_) @syntax.while.body) @syntax.while.statement,
                    
                    (case_statement
                        value: (_) @syntax.case.value
                        body: (_) @syntax.case.body) @syntax.case.statement
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="bash",
                confidence=0.95,
                metadata={
                    "relationships": BASH_PATTERN_RELATIONSHIPS["control_flow"],
                    "metrics": BASH_PATTERN_METRICS["control_flow"],
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
            "variable_assignment": AdaptivePattern(
                name="variable_assignment",
                pattern="""
                [
                    (variable_assignment
                        name: (_) @semantics.var.name
                        value: (_) @semantics.var.value) @semantics.var.assignment,
                    
                    (command_substitution
                        command: (_) @semantics.var.command) @semantics.var.substitution
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="bash",
                confidence=0.9,
                metadata={
                    "relationships": BASH_PATTERN_RELATIONSHIPS["variable_assignment"],
                    "metrics": BASH_PATTERN_METRICS["variable_assignment"],
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
            "comments": AdaptivePattern(
                name="comments",
                pattern="""
                [
                    (comment) @documentation.comment
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="bash",
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

class BashPatternLearner(CrossProjectPatternLearner):
    """Enhanced Bash pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Bash-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("bash", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Bash patterns
        await self._pattern_processor.register_language_patterns(
            "bash", 
            BASH_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "bash_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(BASH_PATTERNS),
                "capabilities": list(BASH_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="bash",
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
            
            # Finally add Bash-specific patterns
            async with AsyncErrorBoundary("bash_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "bash",
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
                bash_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(bash_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "bash_pattern_learner",
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
                "bash_pattern_learner",
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
                "bash_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "bash_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_bash_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Bash pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Bash-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("bash", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "bash", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_bash_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"bash_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "bash",
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
        await update_bash_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "bash_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_bash_pattern_context(
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
            language_id="bash",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "bash"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(BASH_PATTERNS.keys())
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
bash_pattern_learner = BashPatternLearner()

async def initialize_bash_patterns():
    """Initialize Bash patterns during app startup."""
    global bash_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Bash patterns
    await pattern_processor.register_language_patterns(
        "bash",
        BASH_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": BASH_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    bash_pattern_learner = await BashPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "bash",
        bash_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "bash_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(BASH_PATTERNS),
            "capabilities": list(BASH_CAPABILITIES)
        }
    )

async def extract_bash_features(
    pattern: Union[AdaptivePattern, ResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from pattern matches."""
    feature_extractor = await BaseFeatureExtractor.create("bash", FileType.CODE)
    
    features = ExtractedFeatures()
    
    for match in matches:
        # Extract features based on pattern category
        if pattern.category == PatternCategory.SYNTAX:
            syntax_features = await feature_extractor._extract_syntax_features(
                match,
                context
            )
            features.update(syntax_features)
            
        elif pattern.category == PatternCategory.SEMANTICS:
            semantic_features = await feature_extractor._extract_semantic_features(
                match,
                context
            )
            features.update(semantic_features)
    
    return features

async def validate_bash_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a Bash pattern with system integration."""
    # First try common pattern validation
    common_result = await validate_common_pattern(pattern, context)
    if common_result.is_valid:
        return common_result
    
    # Fall back to Bash-specific validation
    async with AsyncErrorBoundary("bash_pattern_validation"):
        # Get pattern processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="bash",
            context=context
        )
        
        # Update pattern metrics
        if not validation_result.is_valid:
            pattern_metrics = BASH_PATTERN_METRICS.get(pattern.name)
            if pattern_metrics:
                pattern_metrics.error_count += 1
        
        return validation_result

# Export public interfaces
__all__ = [
    'BASH_PATTERNS',
    'BASH_PATTERN_RELATIONSHIPS',
    'BASH_PATTERN_METRICS',
    'BASH_CAPABILITIES',
    'BashPatternLearner',
    'bash_pattern_learner',
    'process_bash_pattern',
    'initialize_bash_patterns',
    'extract_bash_features',
    'validate_bash_pattern'
]

# Module identification
LANGUAGE = "bash" 