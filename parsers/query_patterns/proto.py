"""
Query patterns for Protocol Buffers files.

This module provides Protocol Buffer-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
from utils.error_handling import (
    handle_async_errors, AsyncErrorBoundary, ProcessingError, ErrorSeverity
)
from utils.logger import log
from utils.cache import UnifiedCache, cache_coordinator
from utils.cache_analytics import get_cache_analytics
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation
from utils.request_cache import cached_in_request, request_cache_context
from .common import COMMON_PATTERNS

# Language identifier
LANGUAGE = "proto"

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

# Initialize pattern learner with error handling
pattern_learner = CrossProjectPatternLearner()

@handle_async_errors(error_types=ProcessingError)
@cached_in_request
async def extract_proto_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Protocol Buffer content for repository learning."""
    patterns = []
    context = ProtoPatternContext()
    
    try:
        async with AsyncErrorBoundary(
            "proto_pattern_extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            # Update health status
            await global_health_monitor.update_component_status(
                "proto_pattern_processor",
                ComponentStatus.PROCESSING,
                details={"operation": "pattern_extraction"}
            )
            
            # Process patterns with monitoring
            with monitor_operation("extract_patterns", "proto_processor"):
                # Process each pattern category
                for category in PatternCategory:
                    if category in PROTO_PATTERNS:
                        category_patterns = PROTO_PATTERNS[category]
                        for purpose in category_patterns:
                            for pattern_name, pattern in category_patterns[purpose].items():
                                if isinstance(pattern, (ResilientPattern, AdaptivePattern)):
                                    try:
                                        matches = await pattern.matches(content, context)
                                        for match in matches:
                                            patterns.append({
                                                "name": pattern_name,
                                                "category": category.value,
                                                "purpose": purpose.value,
                                                "content": match.get("text", ""),
                                                "metadata": match,
                                                "confidence": pattern.confidence,
                                                "relationships": match.get("relationships", {})
                                            })
                                            
                                            # Update context
                                            if match["type"] == "message":
                                                context.message_names.add(match["name"])
                                            elif match["type"] == "service":
                                                context.service_names.add(match["name"])
                                                context.has_services = True
                                                if match.get("has_streaming"):
                                                    context.has_streams = True
                                            elif match["type"] == "option":
                                                context.has_options = True
                                            
                                    except Exception as e:
                                        await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                        continue
            
            # Update final status
            await global_health_monitor.update_component_status(
                "proto_pattern_processor",
                ComponentStatus.HEALTHY,
                details={
                    "operation": "pattern_extraction_complete",
                    "patterns_found": len(patterns)
                }
            )
    
    except Exception as e:
        await log(f"Error extracting Proto patterns: {e}", level="error")
        await global_health_monitor.update_component_status(
            "proto_pattern_processor",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"error": str(e)}
        )
    
    return patterns

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
    'extract_proto_patterns_for_learning',
    'ProtoPatternContext',
    'pattern_learner',
    'initialize_caches'
] 