"""Query patterns for YAML files.

This module provides YAML-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "yaml"

# YAML capabilities (extends common capabilities)
YAML_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.CONFIGURATION,
    AICapability.DATA_SERIALIZATION,
    AICapability.STRUCTURED_DATA
}

@dataclass
class YAMLPatternContext(PatternContext):
    """YAML-specific pattern context."""
    key_names: Set[str] = field(default_factory=set)
    anchor_names: Set[str] = field(default_factory=set)
    tag_names: Set[str] = field(default_factory=set)
    has_anchors: bool = False
    has_aliases: bool = False
    has_tags: bool = False
    has_sequences: bool = False
    has_mappings: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.key_names)}:{self.has_anchors}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "mapping": PatternPerformanceMetrics(),
    "sequence": PatternPerformanceMetrics(),
    "anchor": PatternPerformanceMetrics(),
    "tag": PatternPerformanceMetrics(),
    "scalar": PatternPerformanceMetrics()
}

YAML_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "mapping": ResilientPattern(
                pattern="""
                [
                    (block_mapping_pair
                        key: (_) @syntax.map.key
                        value: (_) @syntax.map.value) @syntax.map.pair,
                    (flow_mapping
                        (flow_pair
                            key: (_) @syntax.flow.map.key
                            value: (_) @syntax.flow.map.value) @syntax.flow.map.pair) @syntax.flow.map
                ]
                """,
                extract=lambda node: {
                    "type": "mapping",
                    "line_number": (
                        node["captures"].get("syntax.map.pair", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.flow.map", {}).get("start_point", [0])[0]
                    ),
                    "key": (
                        node["captures"].get("syntax.map.key", {}).get("text", "") or
                        node["captures"].get("syntax.flow.map.key", {}).get("text", "")
                    ),
                    "is_flow": "syntax.flow.map" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["scalar", "sequence", "mapping"],
                        PatternRelationType.DEPENDS_ON: ["anchor", "tag"]
                    }
                },
                name="mapping",
                description="Matches YAML mapping patterns",
                examples=["key: value", "{ key: value }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["mapping"],
                    "validation": {
                        "required_fields": ["key"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
                    }
                }
            ),
            "sequence": ResilientPattern(
                pattern="""
                [
                    (block_sequence
                        (block_sequence_item
                            (_) @syntax.seq.item) @syntax.seq.entry) @syntax.seq,
                    (flow_sequence
                        (_)* @syntax.flow.seq.item) @syntax.flow.seq
                ]
                """,
                extract=lambda node: {
                    "type": "sequence",
                    "line_number": (
                        node["captures"].get("syntax.seq", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.flow.seq", {}).get("start_point", [0])[0]
                    ),
                    "is_flow": "syntax.flow.seq" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["scalar", "sequence", "mapping"],
                        PatternRelationType.DEPENDS_ON: ["anchor", "tag"]
                    }
                },
                name="sequence",
                description="Matches YAML sequence patterns",
                examples=["- item1\n- item2", "[item1, item2]"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["sequence"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.ANCHORS: {
            "anchor": AdaptivePattern(
                pattern="""
                [
                    (anchor
                        name: (_) @anchor.name) @anchor.def,
                    (alias
                        name: (_) @alias.name) @alias.def
                ]
                """,
                extract=lambda node: {
                    "type": "anchor",
                    "name": (
                        node["captures"].get("anchor.name", {}).get("text", "") or
                        node["captures"].get("alias.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("anchor.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("alias.def", {}).get("start_point", [0])[0]
                    ),
                    "is_alias": "alias.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["mapping", "sequence", "scalar"],
                        PatternRelationType.DEPENDS_ON: ["anchor"]
                    }
                },
                name="anchor",
                description="Matches YAML anchor and alias patterns",
                examples=["&anchor value", "*alias"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.ANCHORS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["anchor"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
                    }
                }
            )
        },
        PatternPurpose.TAGS: {
            "tag": AdaptivePattern(
                pattern="""
                [
                    (tag
                        name: (_) @tag.name) @tag.def,
                    (verbatim_tag
                        name: (_) @tag.verbatim.name) @tag.verbatim.def
                ]
                """,
                extract=lambda node: {
                    "type": "tag",
                    "name": (
                        node["captures"].get("tag.name", {}).get("text", "") or
                        node["captures"].get("tag.verbatim.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("tag.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("tag.verbatim.def", {}).get("start_point", [0])[0]
                    ),
                    "is_verbatim": "tag.verbatim.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.APPLIES_TO: ["mapping", "sequence", "scalar"],
                        PatternRelationType.DEPENDS_ON: ["tag"]
                    }
                },
                name="tag",
                description="Matches YAML tag patterns",
                examples=["!!str value", "!<tag> value"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.TAGS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["tag"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[!][a-zA-Z0-9_-]*$'
                    }
                }
            )
        }
    },

    PatternCategory.BEST_PRACTICES: {
        // ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "indentation_error": QueryPattern(
            name="indentation_error",
            pattern=r'^( +)[^-\s].*\n\1[^ ]',
            extract=lambda m: {
                "type": "indentation_error",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects indentation errors", "examples": ["  key: value\n wrong_indent"]}
        ),
        "invalid_anchor": QueryPattern(
            name="invalid_anchor",
            pattern=r'&([^a-zA-Z0-9_-]|\s)',
            extract=lambda m: {
                "type": "invalid_anchor",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects invalid anchor names", "examples": ["&*invalid", "&space name"]}
        ),
        "duplicate_key": QueryPattern(
            name="duplicate_key",
            pattern=r'^([^:#\n]+):\s*[^\n]+\n(?:[^\n]+\n)*\1:',
            extract=lambda m: {
                "type": "duplicate_key",
                "key": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects duplicate keys", "examples": ["key: value1\nkey: value2"]}
        ),
        "invalid_mapping": QueryPattern(
            name="invalid_mapping",
            pattern=r'^[^:#\n]+:[^\s\n]',
            extract=lambda m: {
                "type": "invalid_mapping",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects invalid mapping syntax", "examples": ["key:value"]}
        ),
        "unresolved_alias": QueryPattern(
            name="unresolved_alias",
            pattern=r'\*([a-zA-Z_][a-zA-Z0-9_]*)',
            extract=lambda m: {
                "type": "unresolved_alias",
                "alias": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potentially unresolved aliases", "examples": ["*undefined_anchor"]}
        )
    }
}

class YAMLPatternLearner(CrossProjectPatternLearner):
    """Enhanced YAML pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with YAML-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("yaml", FileType.CONFIG)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register YAML patterns
        await self._pattern_processor.register_language_patterns(
            "yaml", 
            YAML_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "yaml_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(YAML_PATTERNS),
                "capabilities": list(YAML_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="yaml",
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
            
            # Finally add YAML-specific patterns
            async with AsyncErrorBoundary("yaml_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "yaml",
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
                yaml_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(yaml_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "yaml_pattern_learner",
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
                "yaml_pattern_learner",
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
                "yaml_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "yaml_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_yaml_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a YAML pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to YAML-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("yaml", FileType.CONFIG)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "yaml", FileType.CONFIG)
            if parse_result and parse_result.ast:
                context = await create_yaml_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"yaml_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "yaml",
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
        await update_yaml_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "yaml_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_yaml_pattern_context(
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
            language_id="yaml",
            file_type=FileType.CONFIG
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "yaml"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(YAML_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_yaml_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_yaml_pattern_match_result(
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
        metadata={"language": "yaml"}
    )

# Initialize pattern learner
pattern_learner = YAMLPatternLearner()

async def initialize_yaml_patterns():
    """Initialize YAML patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register YAML patterns
    await pattern_processor.register_language_patterns(
        "yaml",
        YAML_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": YAML_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await YAMLPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "yaml",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "yaml_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(YAML_PATTERNS),
            "capabilities": list(YAML_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "mapping": {
        PatternRelationType.CONTAINS: ["scalar", "sequence", "mapping"],
        PatternRelationType.DEPENDS_ON: ["anchor", "tag"]
    },
    "sequence": {
        PatternRelationType.CONTAINS: ["scalar", "sequence", "mapping"],
        PatternRelationType.DEPENDS_ON: ["anchor", "tag"]
    },
    "anchor": {
        PatternRelationType.REFERENCED_BY: ["mapping", "sequence", "scalar"],
        PatternRelationType.DEPENDS_ON: ["anchor"]
    },
    "tag": {
        PatternRelationType.APPLIES_TO: ["mapping", "sequence", "scalar"],
        PatternRelationType.DEPENDS_ON: ["tag"]
    }
}

# Export public interfaces
__all__ = [
    'YAML_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_yaml_pattern_match_result',
    'update_yaml_pattern_metrics',
    'YAMLPatternContext',
    'pattern_learner'
] 