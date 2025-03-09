"""Query patterns for HCL files.

This module provides HCL-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

from typing import Dict, Any, List, Optional, Union, Set
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

# HCL capabilities (extends common capabilities)
HCL_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.CONFIGURATION,
    AICapability.INFRASTRUCTURE_AS_CODE,
    AICapability.TEMPLATING
}

@dataclass
class HCLPatternContext(PatternContext):
    """HCL-specific pattern context."""
    block_types: Set[str] = field(default_factory=set)
    resource_types: Set[str] = field(default_factory=set)
    provider_names: Set[str] = field(default_factory=set)
    variable_names: Set[str] = field(default_factory=set)
    has_providers: bool = False
    has_variables: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.block_types)}:{len(self.resource_types)}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "block": PatternPerformanceMetrics(),
    "resource": PatternPerformanceMetrics(),
    "provider": PatternPerformanceMetrics(),
    "variable": PatternPerformanceMetrics(),
    "output": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics()
}

# Pattern relationships for HCL
HCL_PATTERN_RELATIONSHIPS = {
    "block": {
        PatternRelationType.CONTAINS: ["attribute", "block"],
        PatternRelationType.DEPENDS_ON: ["provider"]
    },
    "resource": {
        PatternRelationType.DEPENDS_ON: ["provider", "variable"],
        PatternRelationType.REFERENCED_BY: ["output"]
    },
    "provider": {
        PatternRelationType.REFERENCED_BY: ["resource", "module"],
        PatternRelationType.DEPENDS_ON: ["required_providers"]
    },
    "variable": {
        PatternRelationType.REFERENCED_BY: ["resource", "module", "output"],
        PatternRelationType.DEPENDS_ON: []
    },
    "module": {
        PatternRelationType.REFERENCES: ["variable"],
        PatternRelationType.DEPENDS_ON: ["provider"]
    }
}

# Enhanced HCL patterns with proper typing and relationships
HCL_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "block": ResilientPattern(
                name="block",
                pattern="""
                (block
                    type: (identifier) @syntax.block.type
                    labels: (string_lit)* @syntax.block.labels
                    body: (body) @syntax.block.body) @syntax.block.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="hcl",
                confidence=0.95,
                metadata={
                    "relationships": HCL_PATTERN_RELATIONSHIPS["block"],
                    "metrics": PATTERN_METRICS["block"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            "attribute": ResilientPattern(
                name="attribute",
                pattern="""
                (attribute
                    name: (identifier) @syntax.attr.name
                    value: (expression) @syntax.attr.value) @syntax.attr.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="hcl",
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
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.INFRASTRUCTURE: {
            "resource_patterns": AdaptivePattern(
                name="resource_patterns",
                pattern="""
                [
                    (block
                        type: (identifier) @res.block.type
                        (#match? @res.block.type "^resource$")
                        labels: [
                            (string_lit) @res.block.resource_type
                            (string_lit) @res.block.resource_name
                        ]
                        body: (body) @res.block.body) @res.block,
                        
                    (block
                        type: (identifier) @res.data.type
                        (#match? @res.data.type "^data$")
                        labels: [
                            (string_lit) @res.data.data_type
                            (string_lit) @res.data.data_name
                        ]
                        body: (body) @res.data.body) @res.data
                ]
                """,
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.INFRASTRUCTURE,
                language_id="hcl",
                confidence=0.9,
                metadata={
                    "relationships": HCL_PATTERN_RELATIONSHIPS["resource"],
                    "metrics": PATTERN_METRICS["resource"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        },
        PatternPurpose.PROVIDERS: {
            "provider_configuration": AdaptivePattern(
                name="provider_configuration",
                pattern="""
                [
                    (block
                        type: (identifier) @prov.block.type
                        (#match? @prov.block.type "^provider$")
                        labels: (string_lit) @prov.block.name
                        body: (body) @prov.block.body) @prov.block,
                        
                    (block
                        type: (identifier) @prov.required.type
                        (#match? @prov.required.type "^required_providers$")
                        body: (body) @prov.required.body) @prov.required
                ]
                """,
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PROVIDERS,
                language_id="hcl",
                confidence=0.9,
                metadata={
                    "relationships": HCL_PATTERN_RELATIONSHIPS["provider"],
                    "metrics": PATTERN_METRICS["provider"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    }
}

class HCLPatternLearner(CrossProjectPatternLearner):
    """Enhanced HCL pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with HCL-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("hcl", FileType.CONFIG)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register HCL patterns
        await self._pattern_processor.register_language_patterns(
            "hcl", 
            HCL_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "hcl_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(HCL_PATTERNS),
                "capabilities": list(HCL_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="hcl",
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
            
            # Finally add HCL-specific patterns
            async with AsyncErrorBoundary("hcl_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "hcl",
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
                hcl_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(hcl_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "hcl_pattern_learner",
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
                "hcl_pattern_learner",
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
                "hcl_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "hcl_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_hcl_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process an HCL pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to HCL-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("hcl", FileType.CONFIG)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "hcl", FileType.CONFIG)
            if parse_result and parse_result.ast:
                context = await create_hcl_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"hcl_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "hcl",
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
        await update_hcl_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "hcl_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_hcl_pattern_context(
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
            language_id="hcl",
            file_type=FileType.CONFIG
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "hcl"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(HCL_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_hcl_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_hcl_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=HCL_PATTERN_RELATIONSHIPS.get(pattern_name, []),
        performance=PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "hcl"}
    )

# Initialize pattern learner
hcl_pattern_learner = HCLPatternLearner()

async def initialize_hcl_patterns():
    """Initialize HCL patterns during app startup."""
    global hcl_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register HCL patterns
    await pattern_processor.register_language_patterns(
        "hcl",
        HCL_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": HCL_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    hcl_pattern_learner = await HCLPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "hcl",
        hcl_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "hcl_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(HCL_PATTERNS),
            "capabilities": list(HCL_CAPABILITIES)
        }
    )

# Export public interfaces
__all__ = [
    'HCL_PATTERNS',
    'HCL_PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_hcl_pattern_match_result',
    'update_hcl_pattern_metrics',
    'HCLPatternContext',
    'hcl_pattern_learner'
]

# Module identification
LANGUAGE = "hcl" 