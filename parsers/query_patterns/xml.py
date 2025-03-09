"""Query patterns for XML files.

This module provides XML-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "xml"

# XML capabilities (extends common capabilities)
XML_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.MARKUP,
    AICapability.DATA_SERIALIZATION,
    AICapability.SCHEMA_VALIDATION
}

@dataclass
class XMLPatternContext(PatternContext):
    """XML-specific pattern context."""
    tag_names: Set[str] = field(default_factory=set)
    attribute_names: Set[str] = field(default_factory=set)
    namespace_names: Set[str] = field(default_factory=set)
    script_types: Set[str] = field(default_factory=set)
    style_types: Set[str] = field(default_factory=set)
    has_namespaces: bool = False
    has_dtd: bool = False
    has_cdata: bool = False
    has_processing_instructions: bool = False
    has_comments: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.tag_names)}:{self.has_namespaces}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "element": PatternPerformanceMetrics(),
    "attribute": PatternPerformanceMetrics(),
    "namespace": PatternPerformanceMetrics(),
    "script": PatternPerformanceMetrics(),
    "doctype": PatternPerformanceMetrics()
}

XML_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "element": ResilientPattern(
                pattern="""
                [
                    (element
                        start_tag: (start_tag
                            name: (_) @syntax.element.name
                            attributes: (attribute)* @syntax.element.attrs) @syntax.element.start
                        content: (_)* @syntax.element.content
                        end_tag: (end_tag) @syntax.element.end) @syntax.element.def,
                    (empty_element
                        name: (_) @syntax.empty.name
                        attributes: (attribute)* @syntax.empty.attrs) @syntax.empty.def
                ]
                """,
                extract=lambda node: {
                    "type": "element",
                    "name": (
                        node["captures"].get("syntax.element.name", {}).get("text", "") or
                        node["captures"].get("syntax.empty.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.element.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.empty.def", {}).get("start_point", [0])[0]
                    ),
                    "is_empty": "syntax.empty.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["element", "attribute", "text"],
                        PatternRelationType.DEPENDS_ON: ["namespace"]
                    }
                },
                name="element",
                description="Matches XML element declarations",
                examples=["<tag>content</tag>", "<empty-tag/>"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["element"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:-]*$'
                    }
                }
            ),
            "attribute": ResilientPattern(
                pattern="""
                [
                    (attribute
                        name: (_) @syntax.attr.name
                        value: (_) @syntax.attr.value) @syntax.attr.def,
                    (namespace_attribute
                        name: (_) @syntax.ns.attr.name
                        value: (_) @syntax.ns.attr.value) @syntax.ns.attr.def
                ]
                """,
                extract=lambda node: {
                    "type": "attribute",
                    "name": (
                        node["captures"].get("syntax.attr.name", {}).get("text", "") or
                        node["captures"].get("syntax.ns.attr.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.attr.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.ns.attr.def", {}).get("start_point", [0])[0]
                    ),
                    "is_namespace": "syntax.ns.attr.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["element"],
                        PatternRelationType.DEPENDS_ON: ["namespace"]
                    }
                },
                name="attribute",
                description="Matches XML attribute declarations",
                examples=['id="123"', 'xmlns:prefix="uri"'],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["attribute"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:-]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.STRUCTURE: {
            "doctype": AdaptivePattern(
                pattern="""
                [
                    (doctype
                        name: (_) @struct.doctype.name
                        external_id: (_)? @struct.doctype.external
                        dtd: (_)? @struct.doctype.dtd) @struct.doctype.def,
                    (processing_instruction
                        name: (_) @struct.pi.name
                        content: (_)? @struct.pi.content) @struct.pi.def
                ]
                """,
                extract=lambda node: {
                    "type": "doctype",
                    "name": (
                        node["captures"].get("struct.doctype.name", {}).get("text", "") or
                        node["captures"].get("struct.pi.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("struct.doctype.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("struct.pi.def", {}).get("start_point", [0])[0]
                    ),
                    "is_processing_instruction": "struct.pi.def" in node["captures"],
                    "has_dtd": "struct.doctype.dtd" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["entity", "notation"],
                        PatternRelationType.DEPENDS_ON: ["doctype"]
                    }
                },
                name="doctype",
                description="Matches XML DOCTYPE and processing instruction declarations",
                examples=["<!DOCTYPE html>", "<?xml version='1.0'?>"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.STRUCTURE,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["doctype"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:-]*$'
                    }
                }
            )
        },
        PatternPurpose.NAMESPACES: {
            "namespace": AdaptivePattern(
                pattern="""
                [
                    (namespace_declaration
                        prefix: (_)? @ns.prefix
                        uri: (_) @ns.uri) @ns.def,
                    (namespace_reference
                        prefix: (_) @ns.ref.prefix
                        local: (_) @ns.ref.local) @ns.ref.def
                ]
                """,
                extract=lambda node: {
                    "type": "namespace",
                    "line_number": (
                        node["captures"].get("ns.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("ns.ref.def", {}).get("start_point", [0])[0]
                    ),
                    "prefix": (
                        node["captures"].get("ns.prefix", {}).get("text", "") or
                        node["captures"].get("ns.ref.prefix", {}).get("text", "")
                    ),
                    "is_reference": "ns.ref.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.APPLIES_TO: ["element", "attribute"],
                        PatternRelationType.DEPENDS_ON: ["namespace"]
                    }
                },
                name="namespace",
                description="Matches XML namespace declarations and references",
                examples=['xmlns="uri"', 'xmlns:prefix="uri"'],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.NAMESPACES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["namespace"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:-]*$'
                    }
                }
            )
        }
    }
}

class XMLPatternLearner(CrossProjectPatternLearner):
    """Enhanced XML pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with XML-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("xml", FileType.MARKUP)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register XML patterns
        await self._pattern_processor.register_language_patterns(
            "xml", 
            XML_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "xml_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(XML_PATTERNS),
                "capabilities": list(XML_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="xml",
                file_type=FileType.MARKUP,
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
            
            # Finally add XML-specific patterns
            async with AsyncErrorBoundary("xml_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "xml",
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
                xml_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(xml_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "xml_pattern_learner",
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
                "xml_pattern_learner",
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
                "xml_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "xml_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_xml_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process an XML pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to XML-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("xml", FileType.MARKUP)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "xml", FileType.MARKUP)
            if parse_result and parse_result.ast:
                context = await create_xml_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"xml_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "xml",
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
        await update_xml_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "xml_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_xml_pattern_context(
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
            language_id="xml",
            file_type=FileType.MARKUP
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "xml"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(XML_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_xml_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_xml_pattern_match_result(
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
        metadata={"language": "xml"}
    )

# Initialize pattern learner
pattern_learner = XMLPatternLearner()

async def initialize_xml_patterns():
    """Initialize XML patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register XML patterns
    await pattern_processor.register_language_patterns(
        "xml",
        XML_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": XML_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await XMLPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "xml",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "xml_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(XML_PATTERNS),
            "capabilities": list(XML_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "element": {
        PatternRelationType.CONTAINS: ["element", "attribute", "text"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    },
    "attribute": {
        PatternRelationType.CONTAINED_BY: ["element"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    },
    "doctype": {
        PatternRelationType.CONTAINS: ["entity", "notation"],
        PatternRelationType.DEPENDS_ON: ["doctype"]
    },
    "namespace": {
        PatternRelationType.APPLIES_TO: ["element", "attribute"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    }
}

# Export public interfaces
__all__ = [
    'XML_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_xml_pattern_match_result',
    'update_xml_pattern_metrics',
    'XMLPatternContext',
    'pattern_learner'
] 