"""Query patterns for Objective-C files.

This module provides Objective-C-specific patterns with enhanced type system and relationships.
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
from parsers.feature_extractor import get_feature_extractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# Language identifier
LANGUAGE = "objc"

# Objective-C capabilities (extends common capabilities)
OBJC_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.OBJECT_ORIENTED,
    AICapability.MEMORY_MANAGEMENT,
    AICapability.CATEGORIES
}

@dataclass
class ObjCPatternContext(PatternContext):
    """Objective-C-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    method_names: Set[str] = field(default_factory=set)
    property_names: Set[str] = field(default_factory=set)
    protocol_names: Set[str] = field(default_factory=set)
    has_arc: bool = False
    has_categories: bool = False
    has_blocks: bool = False
    has_extensions: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_arc}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "method": PatternPerformanceMetrics(),
    "property": PatternPerformanceMetrics(),
    "protocol": PatternPerformanceMetrics(),
    "category": PatternPerformanceMetrics()
}

OBJC_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_interface
                        name: (identifier) @syntax.class.name
                        superclass: (superclass_reference)? @syntax.class.super
                        protocols: (protocol_reference_list)? @syntax.class.protocols
                        properties: (property_declaration)* @syntax.class.properties
                        methods: (method_declaration)* @syntax.class.methods) @syntax.class.interface,
                    (class_implementation
                        name: (identifier) @syntax.class.impl.name
                        superclass: (superclass_reference)? @syntax.class.impl.super
                        ivars: (instance_variables)? @syntax.class.impl.ivars) @syntax.class.implementation
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.class.impl.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.class.interface", {}).get("start_point", [0])[0],
                    "is_implementation": "syntax.class.implementation" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["property", "method", "ivar"],
                        PatternRelationType.DEPENDS_ON: ["protocol", "class"]
                    }
                },
                name="class",
                description="Matches Objective-C class declarations",
                examples=["@interface MyClass : NSObject", "@implementation MyClass"],
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
            "method": ResilientPattern(
                pattern="""
                [
                    (method_declaration
                        type: (method_type) @syntax.method.type
                        selector: (selector) @syntax.method.selector
                        parameters: (parameter_list)? @syntax.method.params
                        body: (compound_statement)? @syntax.method.body) @syntax.method.def
                ]
                """,
                extract=lambda node: {
                    "type": "method",
                    "selector": node["captures"].get("syntax.method.selector", {}).get("text", ""),
                    "method_type": node["captures"].get("syntax.method.type", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.method.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["class", "protocol"]
                    }
                },
                name="method",
                description="Matches Objective-C method declarations",
                examples=["- (void)viewDidLoad", "+ (instancetype)sharedInstance"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["method"],
                    "validation": {
                        "required_fields": ["selector"],
                        "method_type_format": r'^[-+]$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.MEMORY_MANAGEMENT: {
            "memory_management": AdaptivePattern(
                pattern="""
                [
                    (message_expression
                        receiver: (_) @mem.msg.receiver
                        selector: (selector) @mem.msg.selector
                        (#match? @mem.msg.selector "alloc|retain|release|autorelease|dealloc")) @mem.msg,
                        
                    (property_declaration
                        attributes: (property_attributes) @mem.prop.attrs) @mem.prop
                ]
                """,
                extract=lambda node: {
                    "type": "memory_management",
                    "line_number": node["captures"].get("mem.msg", {}).get("start_point", [0])[0],
                    "is_memory_message": "mem.msg" in node["captures"],
                    "uses_arc_attributes": "mem.prop" in node["captures"] and "strong" in (node["captures"].get("mem.prop.attrs", {}).get("text", "") or ""),
                    "memory_selector": node["captures"].get("mem.msg.selector", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["class"],
                        PatternRelationType.REFERENCES: ["property"]
                    }
                },
                name="memory_management",
                description="Matches memory management patterns",
                examples=["[object retain]", "@property (nonatomic, strong) NSString *name"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.MEMORY_MANAGEMENT,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["memory"],
                    "validation": {
                        "required_fields": []
                    }
                }
            )
        },
        PatternPurpose.CATEGORIES: {
            "category": AdaptivePattern(
                pattern="""
                [
                    (category_interface
                        name: (identifier) @cat.class
                        category: (identifier) @cat.name) @cat.interface,
                        
                    (category_implementation
                        name: (identifier) @cat.impl.class
                        category: (identifier) @cat.impl.name) @cat.implementation
                ]
                """,
                extract=lambda node: {
                    "type": "category",
                    "class_name": (
                        node["captures"].get("cat.class", {}).get("text", "") or
                        node["captures"].get("cat.impl.class", {}).get("text", "")
                    ),
                    "category_name": (
                        node["captures"].get("cat.name", {}).get("text", "") or
                        node["captures"].get("cat.impl.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("cat.interface", {}).get("start_point", [0])[0],
                    "is_implementation": "cat.implementation" in node["captures"],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["class"],
                        PatternRelationType.CONTAINS: ["method", "property"]
                    }
                },
                name="category",
                description="Matches Objective-C categories",
                examples=["@interface NSString (MyAdditions)", "@implementation UIView (Animations)"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.CATEGORIES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["category"],
                    "validation": {
                        "required_fields": ["class_name", "category_name"],
                        "class_name_format": r'^[A-Z][a-zA-Z0-9_]*$',
                        "category_name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

class ObjCPatternLearner(CrossProjectPatternLearner):
    """Enhanced Objective-C pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Objective-C-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await get_feature_extractor("objc")
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Objective-C patterns
        await self._pattern_processor.register_language_patterns(
            "objc", 
            OBJC_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "objc_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(OBJC_PATTERNS),
                "capabilities": list(OBJC_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="objc",
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
            
            # Finally add Objective-C-specific patterns
            async with AsyncErrorBoundary("objc_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "objc",
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
                objc_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(objc_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "objc_pattern_learner",
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
                "objc_pattern_learner",
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
                "objc_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "objc_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_objc_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process an Objective-C pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Objective-C-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await get_feature_extractor("objc")
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "objc", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_objc_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"objc_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "objc",
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
        await update_objc_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "objc_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_objc_pattern_context(
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
            language_id="objc",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "objc"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(OBJC_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_objc_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_objc_pattern_match_result(
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
        metadata={"language": "objc"}
    )

# Initialize pattern learner
pattern_learner = ObjCPatternLearner()

async def initialize_objc_patterns():
    """Initialize Objective-C patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Objective-C patterns
    await pattern_processor.register_language_patterns(
        "objc",
        OBJC_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": OBJC_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await ObjCPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "objc",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "objc_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(OBJC_PATTERNS),
            "capabilities": list(OBJC_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["property", "method", "ivar"],
        PatternRelationType.DEPENDS_ON: ["protocol", "class"]
    },
    "method": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["class", "protocol"]
    },
    "property": {
        PatternRelationType.DEPENDS_ON: ["class"],
        PatternRelationType.REFERENCES: ["class"]
    },
    "category": {
        PatternRelationType.DEPENDS_ON: ["class"],
        PatternRelationType.CONTAINS: ["method", "property"]
    }
}

# Export public interfaces
__all__ = [
    'OBJC_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_objc_pattern_match_result',
    'update_objc_pattern_metrics',
    'ObjCPatternContext',
    'pattern_learner'
] 