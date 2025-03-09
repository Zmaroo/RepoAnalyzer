"""Query patterns for Swift files.

This module provides Swift-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "swift"

# Swift capabilities (extends common capabilities)
SWIFT_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.OBJECT_ORIENTED,
    AICapability.PROTOCOL_ORIENTED,
    AICapability.TYPE_SAFETY
}

@dataclass
class SwiftPatternContext(PatternContext):
    """Swift-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    struct_names: Set[str] = field(default_factory=set)
    protocol_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    extension_names: Set[str] = field(default_factory=set)
    has_generics: bool = False
    has_protocols: bool = False
    has_extensions: bool = False
    has_async: bool = False
    has_throws: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_generics}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "struct": PatternPerformanceMetrics(),
    "protocol": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "extension": PatternPerformanceMetrics()
}

SWIFT_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_declaration
                        name: (type_identifier) @syntax.class.name
                        type_parameters: (generic_parameter_clause)? @syntax.class.generics
                        inheritance_clause: (type_inheritance_clause)? @syntax.class.inheritance
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                    (struct_declaration
                        name: (type_identifier) @syntax.struct.name
                        type_parameters: (generic_parameter_clause)? @syntax.struct.generics
                        inheritance_clause: (type_inheritance_clause)? @syntax.struct.inheritance
                        body: (struct_body) @syntax.struct.body) @syntax.struct.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.struct.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.struct.def", {}).get("start_point", [0])[0]
                    ),
                    "is_struct": "syntax.struct.def" in node["captures"],
                    "has_generics": (
                        "syntax.class.generics" in node["captures"] or
                        "syntax.struct.generics" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "property", "initializer"],
                        PatternRelationType.DEPENDS_ON: ["protocol", "class"]
                    }
                },
                name="class",
                description="Matches Swift class and struct declarations",
                examples=["class MyClass<T>: BaseClass", "struct Point: Codable"],
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
            "protocol": ResilientPattern(
                pattern="""
                [
                    (protocol_declaration
                        name: (type_identifier) @syntax.protocol.name
                        type_parameters: (generic_parameter_clause)? @syntax.protocol.generics
                        inheritance_clause: (type_inheritance_clause)? @syntax.protocol.inheritance
                        body: (protocol_body) @syntax.protocol.body) @syntax.protocol.def,
                    (extension_declaration
                        name: (type_identifier) @syntax.extension.name
                        type_parameters: (generic_parameter_clause)? @syntax.extension.generics
                        inheritance_clause: (type_inheritance_clause)? @syntax.extension.inheritance
                        body: (extension_body) @syntax.extension.body) @syntax.extension.def
                ]
                """,
                extract=lambda node: {
                    "type": "protocol",
                    "name": (
                        node["captures"].get("syntax.protocol.name", {}).get("text", "") or
                        node["captures"].get("syntax.extension.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.protocol.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.extension.def", {}).get("start_point", [0])[0]
                    ),
                    "is_extension": "syntax.extension.def" in node["captures"],
                    "has_generics": (
                        "syntax.protocol.generics" in node["captures"] or
                        "syntax.extension.generics" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "property", "associatedtype"],
                        PatternRelationType.DEPENDS_ON: ["protocol"]
                    }
                },
                name="protocol",
                description="Matches Swift protocol declarations and extensions",
                examples=["protocol Drawable", "extension Array: CustomStringConvertible"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["protocol"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": ResilientPattern(
                pattern="""
                [
                    (function_declaration
                        modifiers: [(async) (throws)]* @syntax.func.modifier
                        name: (identifier) @syntax.func.name
                        type_parameters: (generic_parameter_clause)? @syntax.func.generics
                        parameters: (parameter_clause) @syntax.func.params
                        return_type: (type_annotation)? @syntax.func.return
                        body: (code_block) @syntax.func.body) @syntax.func.def,
                    (initializer_declaration
                        modifiers: [(convenience) (required)]* @syntax.init.modifier
                        parameters: (parameter_clause) @syntax.init.params
                        body: (code_block) @syntax.init.body) @syntax.init.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": node["captures"].get("syntax.func.name", {}).get("text", ""),
                    "line_number": (
                        node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.init.def", {}).get("start_point", [0])[0]
                    ),
                    "is_init": "syntax.init.def" in node["captures"],
                    "is_async": "async" in (node["captures"].get("syntax.func.modifier", {}).get("text", "") or ""),
                    "is_throws": "throws" in (node["captures"].get("syntax.func.modifier", {}).get("text", "") or ""),
                    "has_generics": "syntax.func.generics" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["statement", "expression"],
                        PatternRelationType.DEPENDS_ON: ["type", "protocol"]
                    }
                },
                name="function",
                description="Matches Swift function declarations",
                examples=["func process<T>(_ data: T) async throws -> Result<T, Error>", "init(name: String)"],
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
        PatternPurpose.EXTENSIONS: {
            "extension": AdaptivePattern(
                pattern="""
                [
                    (extension_declaration
                        name: (type_identifier) @ext.name
                        type_parameters: (generic_parameter_clause)? @ext.generics
                        inheritance_clause: (type_inheritance_clause)? @ext.inheritance
                        body: (extension_body) @ext.body) @ext.def,
                    (protocol_extension_declaration
                        name: (type_identifier) @ext.protocol.name
                        type_parameters: (generic_parameter_clause)? @ext.protocol.generics
                        inheritance_clause: (type_inheritance_clause)? @ext.protocol.inheritance
                        body: (extension_body) @ext.protocol.body) @ext.protocol.def
                ]
                """,
                extract=lambda node: {
                    "type": "extension",
                    "name": (
                        node["captures"].get("ext.name", {}).get("text", "") or
                        node["captures"].get("ext.protocol.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("ext.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("ext.protocol.def", {}).get("start_point", [0])[0]
                    ),
                    "is_protocol": "ext.protocol.def" in node["captures"],
                    "has_generics": (
                        "ext.generics" in node["captures"] or
                        "ext.protocol.generics" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.EXTENDS: ["class", "struct", "protocol"],
                        PatternRelationType.CONTAINS: ["method", "property"]
                    }
                },
                name="extension",
                description="Matches Swift extension declarations",
                examples=["extension Array where Element: Equatable", "extension Collection"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.EXTENSIONS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["extension"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

class SwiftPatternLearner(CrossProjectPatternLearner):
    """Enhanced Swift pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Swift-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("swift", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Swift patterns
        await self._pattern_processor.register_language_patterns(
            "swift", 
            SWIFT_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "swift_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(SWIFT_PATTERNS),
                "capabilities": list(SWIFT_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="swift",
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
            
            # Finally add Swift-specific patterns
            async with AsyncErrorBoundary("swift_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "swift",
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
                swift_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(swift_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "swift_pattern_learner",
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
                "swift_pattern_learner",
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
                "swift_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "swift_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_swift_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Swift pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Swift-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("swift", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "swift", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_swift_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"swift_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "swift",
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
        await update_swift_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "swift_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_swift_pattern_context(
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
            language_id="swift",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "swift"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(SWIFT_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_swift_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_swift_pattern_match_result(
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
        metadata={"language": "swift"}
    )

# Initialize pattern learner
pattern_learner = SwiftPatternLearner()

async def initialize_swift_patterns():
    """Initialize Swift patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Swift patterns
    await pattern_processor.register_language_patterns(
        "swift",
        SWIFT_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": SWIFT_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await SwiftPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "swift",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "swift_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(SWIFT_PATTERNS),
            "capabilities": list(SWIFT_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "property", "initializer"],
        PatternRelationType.DEPENDS_ON: ["protocol", "class"]
    },
    "protocol": {
        PatternRelationType.CONTAINS: ["method", "property", "associatedtype"],
        PatternRelationType.DEPENDS_ON: ["protocol"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["statement", "expression"],
        PatternRelationType.DEPENDS_ON: ["type", "protocol"]
    },
    "extension": {
        PatternRelationType.EXTENDS: ["class", "struct", "protocol"],
        PatternRelationType.CONTAINS: ["method", "property"]
    }
}

# Export public interfaces
__all__ = [
    'SWIFT_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_swift_pattern_match_result',
    'update_swift_pattern_metrics',
    'SwiftPatternContext',
    'pattern_learner'
] 