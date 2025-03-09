"""Query patterns for reStructuredText files.

This module provides reStructuredText-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "rst"

# RST capabilities (extends common capabilities)
RST_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.DOCUMENTATION,
    AICapability.MARKUP,
    AICapability.CROSS_REFERENCES
}

@dataclass
class RSTPatternContext(PatternContext):
    """reStructuredText-specific pattern context."""
    section_names: Set[str] = field(default_factory=set)
    directive_names: Set[str] = field(default_factory=set)
    role_names: Set[str] = field(default_factory=set)
    reference_names: Set[str] = field(default_factory=set)
    has_sections: bool = False
    has_directives: bool = False
    has_roles: bool = False
    has_references: bool = False
    has_substitutions: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.section_names)}:{self.has_directives}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "section": PatternPerformanceMetrics(),
    "directive": PatternPerformanceMetrics(),
    "role": PatternPerformanceMetrics(),
    "reference": PatternPerformanceMetrics(),
    "list": PatternPerformanceMetrics()
}

RST_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "section": ResilientPattern(
                pattern="""
                [
                    (section
                        title: (_) @syntax.section.title
                        underline: (_) @syntax.section.underline
                        content: (_)* @syntax.section.content) @syntax.section.def,
                    (subsection
                        title: (_) @syntax.subsection.title
                        underline: (_) @syntax.subsection.underline
                        content: (_)* @syntax.subsection.content) @syntax.subsection.def
                ]
                """,
                extract=lambda node: {
                    "type": "section",
                    "title": (
                        node["captures"].get("syntax.section.title", {}).get("text", "") or
                        node["captures"].get("syntax.subsection.title", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.section.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.subsection.def", {}).get("start_point", [0])[0]
                    ),
                    "is_subsection": "syntax.subsection.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["section", "directive", "list"],
                        PatternRelationType.DEPENDS_ON: ["section"]
                    }
                },
                name="section",
                description="Matches reStructuredText section declarations",
                examples=["Title\n=====", "Section\n-------"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["section"],
                    "validation": {
                        "required_fields": ["title"],
                        "name_format": r'^[^\n]+$'
                    }
                }
            ),
            "directive": ResilientPattern(
                pattern="""
                [
                    (directive
                        name: (_) @syntax.directive.name
                        options: (directive_options)? @syntax.directive.options
                        content: (_)* @syntax.directive.content) @syntax.directive.def,
                    (role
                        name: (_) @syntax.role.name
                        content: (_) @syntax.role.content) @syntax.role.def
                ]
                """,
                extract=lambda node: {
                    "type": "directive",
                    "name": (
                        node["captures"].get("syntax.directive.name", {}).get("text", "") or
                        node["captures"].get("syntax.role.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.directive.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.role.def", {}).get("start_point", [0])[0]
                    ),
                    "is_role": "syntax.role.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["section"],
                        PatternRelationType.DEPENDS_ON: ["directive"]
                    }
                },
                name="directive",
                description="Matches reStructuredText directives and roles",
                examples=[".. note::", ":ref:`link`"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["directive"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-z0-9_-]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.REFERENCES: {
            "reference": AdaptivePattern(
                pattern="""
                [
                    (reference
                        name: (_) @ref.name
                        target: (_) @ref.target) @ref.def,
                    (substitution
                        name: (_) @ref.sub.name
                        value: (_) @ref.sub.value) @ref.sub.def,
                    (footnote
                        label: (_) @ref.footnote.label
                        content: (_) @ref.footnote.content) @ref.footnote.def
                ]
                """,
                extract=lambda node: {
                    "type": "reference",
                    "line_number": (
                        node["captures"].get("ref.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("ref.sub.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("ref.footnote.def", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("ref.name", {}).get("text", "") or
                        node["captures"].get("ref.sub.name", {}).get("text", "") or
                        node["captures"].get("ref.footnote.label", {}).get("text", "")
                    ),
                    "reference_type": (
                        "reference" if "ref.def" in node["captures"] else
                        "substitution" if "ref.sub.def" in node["captures"] else
                        "footnote" if "ref.footnote.def" in node["captures"] else
                        "unknown"
                    ),
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["section", "directive"],
                        PatternRelationType.DEPENDS_ON: ["reference"]
                    }
                },
                name="reference",
                description="Matches reStructuredText references",
                examples=["`link`_", "|substitution|", "[1]_"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REFERENCES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["reference"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_-]+$'
                    }
                }
            ),
            "list": AdaptivePattern(
                pattern="""
                [
                    (bullet_list
                        items: (list_item
                            content: (_) @list.bullet.content)* @list.bullet.items) @list.bullet.def,
                    (enumerated_list
                        items: (list_item
                            content: (_) @list.enum.content)* @list.enum.items) @list.enum.def,
                    (definition_list
                        items: (definition_item
                            term: (_) @list.def.term
                            definition: (_) @list.def.content)* @list.def.items) @list.def.def
                ]
                """,
                extract=lambda node: {
                    "type": "list",
                    "line_number": (
                        node["captures"].get("list.bullet.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("list.enum.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("list.def.def", {}).get("start_point", [0])[0]
                    ),
                    "list_type": (
                        "bullet" if "list.bullet.def" in node["captures"] else
                        "enumerated" if "list.enum.def" in node["captures"] else
                        "definition" if "list.def.def" in node["captures"] else
                        "unknown"
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["section", "directive"],
                        PatternRelationType.CONTAINS: ["list_item"]
                    }
                },
                name="list",
                description="Matches reStructuredText lists",
                examples=["* Item", "1. Item", "term\n  Definition"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REFERENCES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["list"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    }
}

class RSTPatternLearner(CrossProjectPatternLearner):
    """Enhanced reStructuredText pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with reStructuredText-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("rst", FileType.DOCUMENTATION)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register RST patterns
        await self._pattern_processor.register_language_patterns(
            "rst", 
            RST_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "rst_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(RST_PATTERNS),
                "capabilities": list(RST_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="rst",
                file_type=FileType.DOCUMENTATION,
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
            
            # Finally add RST-specific patterns
            async with AsyncErrorBoundary("rst_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "rst",
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
                rst_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(rst_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "rst_pattern_learner",
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
                "rst_pattern_learner",
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
                "rst_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "rst_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_rst_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a reStructuredText pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to RST-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("rst", FileType.DOCUMENTATION)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "rst", FileType.DOCUMENTATION)
            if parse_result and parse_result.ast:
                context = await create_rst_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"rst_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "rst",
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
        await update_rst_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "rst_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_rst_pattern_context(
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
            language_id="rst",
            file_type=FileType.DOCUMENTATION
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "rst"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(RST_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_rst_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_rst_pattern_match_result(
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
        metadata={"language": "rst"}
    )

# Initialize pattern learner
pattern_learner = RSTPatternLearner()

async def initialize_rst_patterns():
    """Initialize reStructuredText patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register RST patterns
    await pattern_processor.register_language_patterns(
        "rst",
        RST_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": RST_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await RSTPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "rst",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "rst_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(RST_PATTERNS),
            "capabilities": list(RST_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "section": {
        PatternRelationType.CONTAINS: ["section", "directive", "list"],
        PatternRelationType.DEPENDS_ON: ["section"]
    },
    "directive": {
        PatternRelationType.CONTAINED_BY: ["section"],
        PatternRelationType.DEPENDS_ON: ["directive"]
    },
    "reference": {
        PatternRelationType.REFERENCED_BY: ["section", "directive"],
        PatternRelationType.DEPENDS_ON: ["reference"]
    },
    "list": {
        PatternRelationType.CONTAINED_BY: ["section", "directive"],
        PatternRelationType.CONTAINS: ["list_item"]
    }
}

# Export public interfaces
__all__ = [
    'RST_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_rst_pattern_match_result',
    'update_rst_pattern_metrics',
    'RSTPatternContext',
    'pattern_learner'
] 