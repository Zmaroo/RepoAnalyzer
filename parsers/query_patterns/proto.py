"""
Query patterns for Protocol Buffers files.

This module provides Protocol Buffer-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Set, Union
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
from utils.cache import cache_coordinator, UnifiedCache
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
LANGUAGE = "proto"

# Proto capabilities (extends common capabilities)
PROTO_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.RPC,
    AICapability.SERIALIZATION,
    AICapability.SCHEMA_DEFINITION
}

@dataclass
class ProtoPatternContext(PatternContext):
    """Protocol Buffer-specific pattern context."""
    message_names: Set[str] = field(default_factory=set)
    service_names: Set[str] = field(default_factory=set)
    enum_names: Set[str] = field(default_factory=set)
    has_services: bool = False
    has_streams: bool = False
    has_options: bool = False
    has_imports: bool = False
    has_packages: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.message_names)}:{self.has_services}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "message": PatternPerformanceMetrics(),
    "service": PatternPerformanceMetrics(),
    "field": PatternPerformanceMetrics(),
    "option": PatternPerformanceMetrics()
}

# Initialize caches - using the same cache coordinator as other modules
_pattern_cache = UnifiedCache("proto_patterns")
_context_cache = UnifiedCache("proto_contexts")

async def initialize_caches():
    """Initialize pattern caches."""
    await cache_coordinator.register_cache("proto_patterns", _pattern_cache)
    await cache_coordinator.register_cache("proto_contexts", _context_cache)
    
    # Register warmup functions
    analytics = await get_cache_analytics()
    analytics.register_warmup_function(
        "proto_patterns",
        _warmup_pattern_cache
    )
    analytics.register_warmup_function(
        "proto_contexts",
        _warmup_context_cache
    )

async def _warmup_pattern_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for pattern cache."""
    results = {}
    for key in keys:
        try:
            # Get common patterns for warmup
            patterns = PROTO_PATTERNS.get(PatternCategory.SYNTAX, {})
            if patterns:
                results[key] = patterns
        except Exception as e:
            await log(f"Error warming up pattern cache for {key}: {e}", level="warning")
    return results

async def _warmup_context_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for context cache."""
    results = {}
    for key in keys:
        try:
            # Create empty context for warmup
            context = ProtoPatternContext()
            results[key] = context.__dict__
        except Exception as e:
            await log(f"Error warming up context cache for {key}: {e}", level="warning")
    return results

# Convert existing patterns to enhanced patterns
PROTO_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "message": ResilientPattern(
                pattern="""
                [
                    (message
                        name: (message_name) @syntax.msg.name
                        body: (message_body
                            (field
                                type: (type) @syntax.msg.field.type
                                name: (identifier) @syntax.msg.field.name)*)) @syntax.msg.def,
                    (message
                        body: (message_body
                            (oneof
                                name: (identifier) @syntax.msg.oneof.name
                                fields: (oneof_field)* @syntax.msg.oneof.fields))) @syntax.msg.with.oneof,
                    (message
                        body: (message_body
                            (map_field
                                key_type: (key_type) @syntax.msg.map.key_type
                                type: (type) @syntax.msg.map.value_type
                                name: (identifier) @syntax.msg.map.name))) @syntax.msg.with.map,
                    (message
                        body: (message_body
                            (message
                                name: (message_name) @syntax.msg.nested.name))) @syntax.msg.with.nested
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.msg.name", {}).get("text", ""),
                    "type": "message",
                    "has_oneof": "syntax.msg.with.oneof" in node["captures"],
                    "has_map": "syntax.msg.with.map" in node["captures"],
                    "has_nested": "syntax.msg.with.nested" in node["captures"],
                    "line_number": node["captures"].get("syntax.msg.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["field", "oneof", "map", "message"],
                        PatternRelationType.DEPENDS_ON: ["message"]
                    }
                },
                name="message",
                description="Matches Protocol Buffer message declarations",
                examples=["message User { string name = 1; }", "message Status { enum Code { OK = 0; } }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["message"],
                    "validation": {
                        "required_fields": ["name", "type"],
                        "name_format": r'^[A-Z][a-zA-Z0-9]*$'
                    }
                }
            ),
            "service": ResilientPattern(
                pattern="""
                [
                    (service
                        name: (service_name) @syntax.svc.name
                        body: (service_body
                            (rpc
                                name: (rpc_name) @syntax.svc.rpc.name
                                input_type: (message_or_enum_type) @syntax.svc.rpc.req
                                output_type: (message_or_enum_type) @syntax.svc.rpc.resp))) @syntax.svc.def,
                    (rpc
                        name: (rpc_name) @syntax.rpc.name
                        input_type: (message_or_enum_type
                            stream: (stream)? @syntax.rpc.req.stream
                            message_name: (_) @syntax.rpc.req.type)
                        output_type: (message_or_enum_type
                            stream: (stream)? @syntax.rpc.resp.stream
                            message_name: (_) @syntax.rpc.resp.type)) @syntax.rpc.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.svc.name", {}).get("text", ""),
                    "type": "service",
                    "rpc_name": node["captures"].get("syntax.rpc.name", {}).get("text", ""),
                    "has_streaming": (
                        "syntax.rpc.req.stream" in node["captures"] or
                        "syntax.rpc.resp.stream" in node["captures"]
                    ),
                    "line_number": node["captures"].get("syntax.svc.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["rpc"],
                        PatternRelationType.DEPENDS_ON: ["message"]
                    }
                },
                name="service",
                description="Matches Protocol Buffer service declarations",
                examples=["service UserService { rpc GetUser (GetUserRequest) returns (User); }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["service"],
                    "validation": {
                        "required_fields": ["name", "type"],
                        "name_format": r'^[A-Z][a-zA-Z0-9]*Service$'
                    }
                }
            )
        }
    },
    
    "message_definitions": {
        "pattern": """
        [
            (message
                name: (message_name) @msg.name
                body: (message_body
                    (field
                        type: (type) @msg.field.type
                        name: (identifier) @msg.field.name)*)) @msg.def,
                        
            (message
                body: (message_body
                    (oneof
                        name: (identifier) @msg.oneof.name
                        fields: (oneof_field)* @msg.oneof.fields))) @msg.with.oneof,
                        
            (message
                body: (message_body
                    (map_field
                        key_type: (key_type) @msg.map.key_type
                        type: (type) @msg.map.value_type
                        name: (identifier) @msg.map.name))) @msg.with.map,
                        
            (message
                body: (message_body
                    (message
                        name: (message_name) @msg.nested.name))) @msg.with.nested
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "message_definitions",
            "is_message": "msg.def" in node["captures"],
            "has_oneof": "msg.with.oneof" in node["captures"],
            "has_map": "msg.with.map" in node["captures"],
            "has_nested_message": "msg.with.nested" in node["captures"],
            "message_name": node["captures"].get("msg.name", {}).get("text", ""),
            "field_type": node["captures"].get("msg.field.type", {}).get("text", ""),
            "field_name": node["captures"].get("msg.field.name", {}).get("text", ""),
            "oneof_name": node["captures"].get("msg.oneof.name", {}).get("text", ""),
            "map_name": node["captures"].get("msg.map.name", {}).get("text", ""),
            "nested_message_name": node["captures"].get("msg.nested.name", {}).get("text", ""),
            "message_complexity": (
                "complex" if any([
                    "msg.with.oneof" in node["captures"],
                    "msg.with.map" in node["captures"],
                    "msg.with.nested" in node["captures"]
                ]) else "simple"
            )
        }
    },
    
    "service_definitions": {
        "pattern": """
        [
            (service
                name: (service_name) @svc.name
                body: (service_body
                    (rpc
                        name: (rpc_name) @svc.rpc.name
                        input_type: (message_or_enum_type) @svc.rpc.req
                        output_type: (message_or_enum_type) @svc.rpc.resp))) @svc.def,
                        
            (rpc
                name: (rpc_name) @rpc.name
                input_type: (message_or_enum_type
                    stream: (stream)? @rpc.req.stream
                    message_name: (_) @rpc.req.type)
                output_type: (message_or_enum_type
                    stream: (stream)? @rpc.resp.stream
                    message_name: (_) @rpc.resp.type)) @rpc.def,
                    
            (rpc
                options: (option
                    name: [(full_ident) (identifier)] @rpc.option.name
                    value: (constant) @rpc.option.value)) @rpc.with.options
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "service_definitions",
            "is_service": "svc.def" in node["captures"],
            "is_rpc": "rpc.def" in node["captures"],
            "has_options": "rpc.with.options" in node["captures"],
            "service_name": node["captures"].get("svc.name", {}).get("text", ""),
            "rpc_name": node["captures"].get("svc.rpc.name", {}).get("text", "") or node["captures"].get("rpc.name", {}).get("text", ""),
            "request_type": node["captures"].get("svc.rpc.req", {}).get("text", "") or node["captures"].get("rpc.req.type", {}).get("text", ""),
            "response_type": node["captures"].get("svc.rpc.resp", {}).get("text", "") or node["captures"].get("rpc.resp.type", {}).get("text", ""),
            "request_is_stream": "rpc.req.stream" in node["captures"],
            "response_is_stream": "rpc.resp.stream" in node["captures"],
            "option_name": node["captures"].get("rpc.option.name", {}).get("text", ""),
            "option_value": node["captures"].get("rpc.option.value", {}).get("text", ""),
            "rpc_pattern": (
                "unary" if not ("rpc.req.stream" in node["captures"] or "rpc.resp.stream" in node["captures"]) else
                "client_streaming" if "rpc.req.stream" in node["captures"] and not "rpc.resp.stream" in node["captures"] else
                "server_streaming" if not "rpc.req.stream" in node["captures"] and "rpc.resp.stream" in node["captures"] else
                "bidirectional" if "rpc.req.stream" in node["captures"] and "rpc.resp.stream" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "field_options": {
        "pattern": """
        [
            (field
                options: (field_options) @field.options) @field.with.options,
                
            (field_options
                (option
                    name: [(full_ident) (identifier)] @field.option.name
                    value: (constant) @field.option.value)) @field.option,
                    
            (option
                name: [(full_ident) (identifier)] @option.name
                value: (constant) @option.value) @option.def,
                
            (extend
                name: (message_or_enum_type) @extend.name
                body: (extend_body
                    (field) @extend.field)) @extend.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "field_options",
            "has_field_options": "field.with.options" in node["captures"],
            "is_option_definition": "option.def" in node["captures"],
            "is_extend_definition": "extend.def" in node["captures"],
            "field_option_name": node["captures"].get("field.option.name", {}).get("text", ""),
            "field_option_value": node["captures"].get("field.option.value", {}).get("text", ""),
            "option_name": node["captures"].get("option.name", {}).get("text", ""),
            "option_value": node["captures"].get("option.value", {}).get("text", ""),
            "extend_name": node["captures"].get("extend.name", {}).get("text", ""),
            "option_type": (
                "field_option" if "field.option" in node["captures"] else
                "file_option" if "option.def" in node["captures"] else
                "extension" if "extend.def" in node["captures"] else
                "unknown"
            ),
            "uses_common_options": any([
                "deprecated" in (node["captures"].get("field.option.name", {}).get("text", "") or node["captures"].get("option.name", {}).get("text", "")),
                "packed" in (node["captures"].get("field.option.name", {}).get("text", "") or node["captures"].get("option.name", {}).get("text", "")),
                "json_name" in (node["captures"].get("field.option.name", {}).get("text", "") or node["captures"].get("option.name", {}).get("text", ""))
            ])
        }
    },
    
    "best_practices": {
        "pattern": """
        [
            (package
                name: (full_ident) @pkg.name) @pkg.def,
                
            (import
                path: (string) @import.path) @import.def,
                
            (syntax
                value: (string) @syntax.version) @syntax.def,
                
            (enum
                name: (enum_name) @enum.name
                body: (enum_body
                    (enum_value
                        name: (identifier) @enum.field.name
                        value: (integer) @enum.field.value))) @enum.def,
                        
            (map_field
                key_type: (key_type) @field.map.key_type
                type: (type) @field.map.value_type) @field.map
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "best_practices",
            "has_package": "pkg.def" in node["captures"],
            "has_import": "import.def" in node["captures"],
            "has_syntax": "syntax.def" in node["captures"],
            "is_enum": "enum.def" in node["captures"],
            "uses_map": "field.map" in node["captures"],
            "package_name": node["captures"].get("pkg.name", {}).get("text", ""),
            "import_path": node["captures"].get("import.path", {}).get("text", ""),
            "syntax_version": node["captures"].get("syntax.version", {}).get("text", ""),
            "enum_name": node["captures"].get("enum.name", {}).get("text", ""),
            "enum_field_name": node["captures"].get("enum.field.name", {}).get("text", ""),
            "enum_field_value": node["captures"].get("enum.field.value", {}).get("text", ""),
            "map_key_type": node["captures"].get("field.map.key_type", {}).get("text", ""),
            "map_value_type": node["captures"].get("field.map.value_type", {}).get("text", ""),
            "follows_convention": (
                node["captures"].get("pkg.name", {}).get("text", "").count(".") > 0 if "pkg.def" in node["captures"] else
                node["captures"].get("enum.field.name", {}).get("text", "").isupper() if "enum.def" in node["captures"] else
                "proto2" in node["captures"].get("syntax.version", {}).get("text", "") or "proto3" in node["captures"].get("syntax.version", {}).get("text", "") if "syntax.def" in node["captures"] else
                True
            )
        }
    }
}

class ProtoPatternLearner(CrossProjectPatternLearner):
    """Enhanced Protocol Buffers pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Protocol Buffers-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("proto", FileType.SCHEMA)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Proto patterns
        await self._pattern_processor.register_language_patterns(
            "proto", 
            PROTO_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "proto_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(PROTO_PATTERNS),
                "capabilities": list(PROTO_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="proto",
                file_type=FileType.SCHEMA,
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
            
            # Finally add Proto-specific patterns
            async with AsyncErrorBoundary("proto_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "proto",
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
                proto_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(proto_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "proto_pattern_learner",
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
                "proto_pattern_learner",
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
                "proto_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "proto_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_proto_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Protocol Buffers pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Proto-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("proto", FileType.SCHEMA)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "proto", FileType.SCHEMA)
            if parse_result and parse_result.ast:
                context = await create_proto_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"proto_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "proto",
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
        await update_proto_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "proto_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_proto_pattern_context(
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
            language_id="proto",
            file_type=FileType.SCHEMA
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "proto"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(PROTO_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_proto_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_proto_pattern_match_result(
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
        metadata={"language": "proto"}
    )

# Initialize pattern learner
pattern_learner = ProtoPatternLearner()

async def initialize_proto_patterns():
    """Initialize Protocol Buffers patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Proto patterns
    await pattern_processor.register_language_patterns(
        "proto",
        PROTO_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": PROTO_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await ProtoPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "proto",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "proto_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(PROTO_PATTERNS),
            "capabilities": list(PROTO_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "message": {
        PatternRelationType.CONTAINS: ["field", "oneof", "map", "message"],
        PatternRelationType.DEPENDS_ON: ["message"]
    },
    "service": {
        PatternRelationType.CONTAINS: ["rpc"],
        PatternRelationType.DEPENDS_ON: ["message"]
    },
    "rpc": {
        PatternRelationType.CONTAINED_BY: ["service"],
        PatternRelationType.DEPENDS_ON: ["message"]
    },
    "field": {
        PatternRelationType.CONTAINED_BY: ["message", "oneof"],
        PatternRelationType.DEPENDS_ON: ["type"]
    }
}

# Export public interfaces
__all__ = [
    'PROTO_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_proto_pattern_match_result',
    'update_proto_pattern_metrics',
    'ProtoPatternContext',
    'pattern_learner'
] 