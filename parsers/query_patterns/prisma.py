"""
Query patterns for Prisma schema files.

This module provides Prisma-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "prisma"

@dataclass
class PrismaPatternContext(PatternContext):
    """Prisma-specific pattern context."""
    model_names: Set[str] = field(default_factory=set)
    enum_names: Set[str] = field(default_factory=set)
    field_names: Set[str] = field(default_factory=set)
    has_relations: bool = False
    has_indexes: bool = False
    has_enums: bool = False
    has_types: bool = False
    has_datasources: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.model_names)}:{self.has_relations}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "model": PatternPerformanceMetrics(),
    "field": PatternPerformanceMetrics(),
    "relation": PatternPerformanceMetrics(),
    "index": PatternPerformanceMetrics()
}

# Initialize caches
_pattern_cache = UnifiedCache("prisma_patterns")
_context_cache = UnifiedCache("prisma_contexts")

async def initialize_caches():
    """Initialize pattern caches."""
    await cache_coordinator.register_cache("prisma_patterns", _pattern_cache)
    await cache_coordinator.register_cache("prisma_contexts", _context_cache)
    
    # Register warmup functions
    analytics = await get_cache_analytics()
    analytics.register_warmup_function(
        "prisma_patterns",
        _warmup_pattern_cache
    )
    analytics.register_warmup_function(
        "prisma_contexts",
        _warmup_context_cache
    )

async def _warmup_pattern_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for pattern cache."""
    results = {}
    for key in keys:
        try:
            # Get common patterns for warmup
            patterns = PRISMA_PATTERNS.get(PatternCategory.SYNTAX, {})
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
            context = PrismaPatternContext()
            results[key] = context.__dict__
        except Exception as e:
            await log(f"Error warming up context cache for {key}: {e}", level="warning")
    return results

PRISMA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "model": ResilientPattern(
                pattern="""
                [
                    (model_declaration
                        name: (identifier) @syntax.model.name
                        properties: (model_block) @syntax.model.props) @syntax.model,
                    (enum_declaration
                        name: (identifier) @syntax.enum.name
                        values: (enum_block) @syntax.enum.values) @syntax.enum,
                    (type_declaration
                        name: (identifier) @syntax.type.name
                        type: (_) @syntax.type.def) @syntax.type
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.model.name", {}).get("text", "") or
                        node["captures"].get("syntax.enum.name", {}).get("text", "") or
                        node["captures"].get("syntax.type.name", {}).get("text", "")
                    ),
                    "type": (
                        "model" if "syntax.model" in node["captures"] else
                        "enum" if "syntax.enum" in node["captures"] else
                        "type" if "syntax.type" in node["captures"] else
                        "other"
                    ),
                    "line_number": node["captures"].get("syntax.model", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["field", "index"],
                        PatternRelationType.DEPENDS_ON: ["model"]
                    }
                },
                name="model",
                description="Matches Prisma model declarations",
                examples=["model User { id Int @id }", "enum Role { USER ADMIN }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["model"],
                    "validation": {
                        "required_fields": ["name", "type"],
                        "name_format": r'^[A-Z][a-zA-Z0-9]*$'
                    }
                }
            ),
            "field": QueryPattern(
                pattern="""
                [
                    (field_declaration
                        name: (identifier) @syntax.field.name
                        type: (field_type) @syntax.field.type) @syntax.field,
                    (enum_value_declaration
                        name: (identifier) @syntax.enum.value.name) @syntax.enum.value
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.field.name", {}).get("text", "") or
                        node["captures"].get("syntax.enum.value.name", {}).get("text", "")
                    ),
                    "type": node["captures"].get("syntax.field.type", {}).get("text", ""),
                    "is_enum_value": "syntax.enum.value" in node["captures"]
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                (comment) @documentation.comment
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "type": "comment"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "relation": QueryPattern(
                pattern="""
                [
                    (field_declaration
                        type: (field_type) @structure.relation.type
                        attributes: (attribute
                            name: (identifier) @structure.relation.attr.name
                            (#eq? @structure.relation.attr.name "relation")
                            arguments: (arguments)? @structure.relation.attr.args)) @structure.relation,
                    (field_declaration
                        type: (field_type) @structure.relation.list.type {
                            match: "\\[\\w+\\]"
                        }) @structure.relation.list
                ]
                """,
                extract=lambda node: {
                    "type": "relation",
                    "is_list": "structure.relation.list" in node["captures"],
                    "has_relation_attribute": "structure.relation.attr.name" in node["captures"],
                    "relation_type": node["captures"].get("structure.relation.type", {}).get("text", "")
                }
            ),
            "index": QueryPattern(
                pattern="""
                [
                    (block_attribute
                        name: (identifier) @structure.index.name
                        (#match? @structure.index.name "^index$|^unique$|^fulltext$")
                        arguments: (arguments)? @structure.index.args) @structure.index
                ]
                """,
                extract=lambda node: {
                    "type": "index",
                    "name": node["captures"].get("structure.index.name", {}).get("text", ""),
                    "has_arguments": "structure.index.args" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.DATA_MODELING: {
            "data_modeling": QueryPattern(
                pattern="""
                [
                    (model_declaration
                        name: (identifier) @learning.model.name
                        properties: (model_block
                            (field_declaration
                                name: (identifier) @learning.model.field.name
                                type: (field_type) @learning.model.field.type
                                attributes: (attribute)* @learning.model.field.attrs))) @learning.model.decl,
                    (enum_declaration
                        name: (identifier) @learning.enum.name
                        values: (enum_block
                            (enum_value_declaration)* @learning.enum.values)) @learning.enum.decl,
                    (type_declaration
                        name: (identifier) @learning.type.name
                        type: (_) @learning.type.value) @learning.type.decl,
                    (datasource_declaration
                        provider: (source_block
                            (key_value
                                key: (identifier) @learning.ds.provider.key
                                value: (_) @learning.ds.provider.value) @learning.ds.provider) @learning.ds.block) @learning.ds.decl
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "data_modeling",
                    "is_model": "learning.model.decl" in node["captures"],
                    "is_enum": "learning.enum.decl" in node["captures"],
                    "is_type": "learning.type.decl" in node["captures"],
                    "is_datasource": "learning.ds.decl" in node["captures"],
                    "model_name": node["captures"].get("learning.model.name", {}).get("text", ""),
                    "enum_name": node["captures"].get("learning.enum.name", {}).get("text", ""),
                    "type_name": node["captures"].get("learning.type.name", {}).get("text", ""),
                    "field_name": node["captures"].get("learning.model.field.name", {}).get("text", ""),
                    "field_type": node["captures"].get("learning.model.field.type", {}).get("text", ""),
                    "field_has_attributes": len(node["captures"].get("learning.model.field.attrs", {}).get("text", "")) > 0 if "learning.model.field.attrs" in node["captures"] else False,
                    "datasource_provider": (
                        node["captures"].get("learning.ds.provider.value", {}).get("text", "")
                        if "learning.ds.provider.key" in node["captures"] and node["captures"].get("learning.ds.provider.key", {}).get("text", "") == "provider"
                        else ""
                    )
                }
            )
        },
        PatternPurpose.RELATIONSHIPS: {
            "relations": QueryPattern(
                pattern="""
                [
                    (field_declaration
                        name: (identifier) @learning.rel.field.name
                        type: (field_type) @learning.rel.field.type
                        attributes: (attribute
                            name: (identifier) @learning.rel.attr.name
                            (#eq? @learning.rel.attr.name "relation")
                            arguments: (arguments
                                (argument
                                    value: (_) @learning.rel.attr.value)))) @learning.rel.field,
                    (field_declaration
                        type: (field_type) @learning.rel.list.type {
                            match: "\\[\\w+\\]"
                        }) @learning.rel.list,
                    (field_declaration
                        attributes: (attribute
                            name: (identifier) @learning.rel.refs.name
                            (#eq? @learning.rel.refs.name "references"))
                            arguments: (arguments
                                (argument
                                    value: (_) @learning.rel.refs.field))) @learning.rel.refs
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "relations",
                    "is_relation_field": "learning.rel.attr.name" in node["captures"] and node["captures"].get("learning.rel.attr.name", {}).get("text", "") == "relation",
                    "is_list_relation": "learning.rel.list.type" in node["captures"] and "[" in node["captures"].get("learning.rel.list.type", {}).get("text", ""),
                    "is_foreign_key": "learning.rel.refs.name" in node["captures"] and node["captures"].get("learning.rel.refs.name", {}).get("text", "") == "references",
                    "relation_field_name": node["captures"].get("learning.rel.field.name", {}).get("text", ""),
                    "relation_field_type": node["captures"].get("learning.rel.field.type", {}).get("text", ""),
                    "relation_name": node["captures"].get("learning.rel.attr.value", {}).get("text", "").strip('"') if "learning.rel.attr.value" in node["captures"] else "",
                    "referenced_field": node["captures"].get("learning.rel.refs.field", {}).get("text", "").strip('"') if "learning.rel.refs.field" in node["captures"] else "",
                    "relation_type": (
                        "one_to_many" if "learning.rel.list.type" in node["captures"] else
                        "many_to_one" if "learning.rel.refs.name" in node["captures"] else
                        "one_to_one" if "learning.rel.attr.name" in node["captures"] else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.QUERIES: {
            "query_capabilities": QueryPattern(
                pattern="""
                [
                    (block_attribute
                        name: (identifier) @learning.query.attr.name
                        (#match? @learning.query.attr.name "^index$|^unique$|^fulltext$")
                        arguments: (arguments) @learning.query.attr.args) @learning.query.attr,
                    (attribute
                        name: (identifier) @learning.query.field.name
                        (#match? @learning.query.field.name "^default$|^map$|^updatedAt$|^id$")
                        arguments: (arguments)? @learning.query.field.args) @learning.query.field,
                    (attribute
                        name: (identifier) @learning.query.search.name
                        (#eq? @learning.query.search.name "fulltext")
                        arguments: (arguments) @learning.query.search.args) @learning.query.search
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "query_capabilities",
                    "is_index": "learning.query.attr.name" in node["captures"] and node["captures"].get("learning.query.attr.name", {}).get("text", "") == "index",
                    "is_unique": "learning.query.attr.name" in node["captures"] and node["captures"].get("learning.query.attr.name", {}).get("text", "") == "unique",
                    "is_fulltext": "learning.query.search.name" in node["captures"] and node["captures"].get("learning.query.search.name", {}).get("text", "") == "fulltext",
                    "has_default_value": "learning.query.field.name" in node["captures"] and node["captures"].get("learning.query.field.name", {}).get("text", "") == "default",
                    "is_id_field": "learning.query.field.name" in node["captures"] and node["captures"].get("learning.query.field.name", {}).get("text", "") == "id",
                    "is_timestamp": "learning.query.field.name" in node["captures"] and node["captures"].get("learning.query.field.name", {}).get("text", "") == "updatedAt",
                    "attribute_args": node["captures"].get("learning.query.attr.args", {}).get("text", ""),
                    "field_args": node["captures"].get("learning.query.field.args", {}).get("text", ""),
                    "attribute_type": (
                        "index" if "learning.query.attr.name" in node["captures"] and node["captures"].get("learning.query.attr.name", {}).get("text", "") == "index" else
                        "unique" if "learning.query.attr.name" in node["captures"] and node["captures"].get("learning.query.attr.name", {}).get("text", "") == "unique" else
                        "fulltext" if "learning.query.search.name" in node["captures"] and node["captures"].get("learning.query.search.name", {}).get("text", "") == "fulltext" else
                        "field_attribute" if "learning.query.field.name" in node["captures"] else
                        "unknown"
                    )
                }
            )
        }
    }
}

PRISMA_PATTERNS_FOR_LEARNING = {
    "data_modeling": {
        "pattern": """
        [
            (model_declaration
                name: (identifier) @model.name
                properties: (model_block
                    (field_declaration
                        name: (identifier) @model.field.name
                        type: (field_type) @model.field.type
                        attributes: (attribute)* @model.field.attrs))) @model.decl,
                        
            (enum_declaration
                name: (identifier) @enum.name
                values: (enum_block
                    (enum_value_declaration)* @enum.values)) @enum.decl,
                    
            (type_declaration
                name: (identifier) @type.name
                type: (_) @type.value) @type.decl,
                
            (datasource_declaration
                provider: (source_block
                    (key_value
                        key: (identifier) @ds.provider.key
                        value: (_) @ds.provider.value) @ds.provider) @ds.block) @ds.decl
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "data_modeling",
            "is_model": "model.decl" in node["captures"],
            "is_enum": "enum.decl" in node["captures"],
            "is_type": "type.decl" in node["captures"],
            "is_datasource": "ds.decl" in node["captures"],
            "model_name": node["captures"].get("model.name", {}).get("text", ""),
            "enum_name": node["captures"].get("enum.name", {}).get("text", ""),
            "type_name": node["captures"].get("type.name", {}).get("text", ""),
            "field_name": node["captures"].get("model.field.name", {}).get("text", ""),
            "field_type": node["captures"].get("model.field.type", {}).get("text", ""),
            "field_has_attributes": len(node["captures"].get("model.field.attrs", {}).get("text", "")) > 0 if "model.field.attrs" in node["captures"] else False,
            "datasource_provider": (
                node["captures"].get("ds.provider.value", {}).get("text", "")
                if "ds.provider.key" in node["captures"] and node["captures"].get("ds.provider.key", {}).get("text", "") == "provider"
                else ""
            )
        }
    },
    
    "relations": {
        "pattern": """
        [
            (field_declaration
                name: (identifier) @rel.field.name
                type: (field_type) @rel.field.type
                attributes: (attribute
                    name: (identifier) @rel.attr.name
                    (#eq? @rel.attr.name "relation")
                    arguments: (arguments
                        (argument
                            value: (_) @rel.attr.value)))) @rel.field,
                            
            (field_declaration
                type: (field_type) @rel.list.type {
                    match: "\\[\\w+\\]"
                }) @rel.list,
                
            (field_declaration
                attributes: (attribute
                    name: (identifier) @rel.refs.name
                    (#eq? @rel.refs.name "references"))
                    arguments: (arguments
                        (argument
                            value: (_) @rel.refs.field))) @rel.refs
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "relations",
            "is_relation_field": "rel.attr.name" in node["captures"] and node["captures"].get("rel.attr.name", {}).get("text", "") == "relation",
            "is_list_relation": "rel.list.type" in node["captures"] and "[" in node["captures"].get("rel.list.type", {}).get("text", ""),
            "is_foreign_key": "rel.refs.name" in node["captures"] and node["captures"].get("rel.refs.name", {}).get("text", "") == "references",
            "relation_field_name": node["captures"].get("rel.field.name", {}).get("text", ""),
            "relation_field_type": node["captures"].get("rel.field.type", {}).get("text", ""),
            "relation_name": node["captures"].get("rel.attr.value", {}).get("text", "").strip('"') if "rel.attr.value" in node["captures"] else "",
            "referenced_field": node["captures"].get("rel.refs.field", {}).get("text", "").strip('"') if "rel.refs.field" in node["captures"] else "",
            "relation_type": (
                "one_to_many" if "rel.list.type" in node["captures"] else
                "many_to_one" if "rel.refs.name" in node["captures"] else
                "one_to_one" if "rel.attr.name" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "query_capabilities": {
        "pattern": """
        [
            (block_attribute
                name: (identifier) @query.attr.name
                (#match? @query.attr.name "^index$|^unique$|^fulltext$")
                arguments: (arguments) @query.attr.args) @query.attr,
                
            (attribute
                name: (identifier) @query.field.name
                (#match? @query.field.name "^default$|^map$|^updatedAt$|^id$")
                arguments: (arguments)? @query.field.args) @query.field,
                
            (attribute
                name: (identifier) @query.search.name
                (#eq? @query.search.name "fulltext")
                arguments: (arguments) @query.search.args) @query.search
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "query_capabilities",
            "is_index": "query.attr.name" in node["captures"] and node["captures"].get("query.attr.name", {}).get("text", "") == "index",
            "is_unique": "query.attr.name" in node["captures"] and node["captures"].get("query.attr.name", {}).get("text", "") == "unique",
            "is_fulltext": "query.search.name" in node["captures"] and node["captures"].get("query.search.name", {}).get("text", "") == "fulltext",
            "has_default_value": "query.field.name" in node["captures"] and node["captures"].get("query.field.name", {}).get("text", "") == "default",
            "is_id_field": "query.field.name" in node["captures"] and node["captures"].get("query.field.name", {}).get("text", "") == "id",
            "is_timestamp": "query.field.name" in node["captures"] and node["captures"].get("query.field.name", {}).get("text", "") == "updatedAt",
            "attribute_args": node["captures"].get("query.attr.args", {}).get("text", ""),
            "field_args": node["captures"].get("query.field.args", {}).get("text", ""),
            "attribute_type": (
                "index" if "query.attr.name" in node["captures"] and node["captures"].get("query.attr.name", {}).get("text", "") == "index" else
                "unique" if "query.attr.name" in node["captures"] and node["captures"].get("query.attr.name", {}).get("text", "") == "unique" else
                "fulltext" if "query.search.name" in node["captures"] and node["captures"].get("query.search.name", {}).get("text", "") == "fulltext" else
                "field_attribute" if "query.field.name" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "schema_organization": {
        "pattern": """
        [
            (generator_declaration
                properties: (source_block
                    (key_value
                        key: (identifier) @gen.prop.key
                        value: (_) @gen.prop.value) @gen.prop)) @gen.decl,
                        
            (comment) @schema.comment,
            
            (datasource_declaration
                properties: (source_block) @ds.block) @ds.decl,
                
            (model_declaration
                (comment) @model.comment) @model.with.comment
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "schema_organization",
            "is_generator": "gen.decl" in node["captures"],
            "is_datasource": "ds.decl" in node["captures"],
            "has_schema_comment": "schema.comment" in node["captures"],
            "has_model_comment": "model.comment" in node["captures"],
            "generator_provider": (
                node["captures"].get("gen.prop.value", {}).get("text", "")
                if "gen.prop.key" in node["captures"] and node["captures"].get("gen.prop.key", {}).get("text", "") == "provider"
                else ""
            ),
            "comment_text": (
                node["captures"].get("schema.comment", {}).get("text", "") or 
                node["captures"].get("model.comment", {}).get("text", "")
            ),
            "has_documentation": (
                "@" in (node["captures"].get("schema.comment", {}).get("text", "") or 
                         node["captures"].get("model.comment", {}).get("text", "") or "")
            ),
            "organization_element": (
                "generator" if "gen.decl" in node["captures"] else
                "datasource" if "ds.decl" in node["captures"] else
                "model_documentation" if "model.comment" in node["captures"] else
                "schema_comment" if "schema.comment" in node["captures"] else
                "unknown"
            )
        }
    }
}

PRISMA_PATTERNS = {
    **COMMON_PATTERNS,

    "syntax": {
        "model": {
            "pattern": """
            [
                (model_declaration
                    name: (identifier) @syntax.model.name
                    properties: (model_block) @syntax.model.props) @syntax.model,
                (enum_declaration
                    name: (identifier) @syntax.enum.name
                    values: (enum_block) @syntax.enum.values) @syntax.enum,
                (type_declaration
                    name: (identifier) @syntax.type.name
                    type: (_) @syntax.type.def) @syntax.type
            ]
            """
        },
        "field": {
            "pattern": """
            [
                (field_declaration
                    name: (identifier) @syntax.field.name
                    type: (field_type) @syntax.field.type) @syntax.field,
                (enum_value_declaration
                    name: (identifier) @syntax.enum.value.name) @syntax.enum.value
            ]
            """
        },
        "attribute": {
            "pattern": """
            [
                (attribute
                    name: (identifier) @syntax.attr.name
                    arguments: (arguments)? @syntax.attr.args) @syntax.attr,
                (block_attribute
                    name: (identifier) @syntax.block.attr.name
                    arguments: (arguments)? @syntax.block.attr.args) @syntax.block.attr
            ]
            """
        },
        "directive": {
            "pattern": """
            [
                (datasource_declaration) @syntax.directive.datasource,
                (generator_declaration) @syntax.directive.generator
            ]
            """
        }
    },

    "structure": {
        "relation": {
            "pattern": """
            [
                (field_declaration
                    type: (field_type) @structure.relation.type
                    attributes: (attribute
                        name: (identifier) @structure.relation.attr.name
                        (#eq? @structure.relation.attr.name "relation")
                        arguments: (arguments)? @structure.relation.attr.args)) @structure.relation,
                (field_declaration
                    type: (field_type) @structure.relation.list.type {
                        match: "\\[\\w+\\]"
                    }) @structure.relation.list
            ]
            """
        },
        "index": {
            "pattern": """
            [
                (block_attribute
                    name: (identifier) @structure.index.name
                    (#match? @structure.index.name "^index$|^unique$|^fulltext$")
                    arguments: (arguments)? @structure.index.args) @structure.index
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment
            ]
            """
        }
    },
    
    "REPOSITORY_LEARNING": PRISMA_PATTERNS_FOR_LEARNING
}

# Initialize pattern learner with error handling
pattern_learner = CrossProjectPatternLearner()

@handle_async_errors(error_types=ProcessingError)
@cached_in_request
async def extract_prisma_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Prisma content for repository learning."""
    patterns = []
    context = PrismaPatternContext()
    
    try:
        async with AsyncErrorBoundary(
            "prisma_pattern_extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            # Update health status
            await global_health_monitor.update_component_status(
                "prisma_pattern_processor",
                ComponentStatus.PROCESSING,
                details={"operation": "pattern_extraction"}
            )
            
            # Process patterns with monitoring
            with monitor_operation("extract_patterns", "prisma_processor"):
                # Process each pattern category
                for category in PatternCategory:
                    if category in PRISMA_PATTERNS:
                        category_patterns = PRISMA_PATTERNS[category]
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
                                            if match["type"] == "model":
                                                context.model_names.add(match["name"])
                                            elif match["type"] == "enum":
                                                context.enum_names.add(match["name"])
                                                context.has_enums = True
                                            elif match["type"] == "field":
                                                context.field_names.add(match["name"])
                                            elif match["type"] == "relation":
                                                context.has_relations = True
                                            
                                    except Exception as e:
                                        await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                        continue
            
            # Update final status
            await global_health_monitor.update_component_status(
                "prisma_pattern_processor",
                ComponentStatus.HEALTHY,
                details={
                    "operation": "pattern_extraction_complete",
                    "patterns_found": len(patterns)
                }
            )
    
    except Exception as e:
        await log(f"Error extracting Prisma patterns: {e}", level="error")
        await global_health_monitor.update_component_status(
            "prisma_pattern_processor",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"error": str(e)}
        )
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "model": {
        PatternRelationType.CONTAINS: ["field", "index"],
        PatternRelationType.DEPENDS_ON: ["model"]
    },
    "field": {
        PatternRelationType.CONTAINED_BY: ["model"],
        PatternRelationType.DEPENDS_ON: ["type"]
    },
    "relation": {
        PatternRelationType.CONTAINED_BY: ["model"],
        PatternRelationType.DEPENDS_ON: ["model", "field"]
    },
    "index": {
        PatternRelationType.CONTAINED_BY: ["model"],
        PatternRelationType.DEPENDS_ON: ["field"]
    }
}

# Export public interfaces
__all__ = [
    'PRISMA_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_prisma_patterns_for_learning',
    'PrismaPatternContext',
    'pattern_learner',
    'initialize_caches'
] 