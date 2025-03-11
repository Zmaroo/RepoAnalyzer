"""
Query patterns for Prisma schema files.

This module provides Prisma-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "prisma"

# Prisma capabilities (extends common capabilities)
PRISMA_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.DATA_MODELING,
    AICapability.DATABASE_SCHEMA,
    AICapability.RELATIONSHIPS
}

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
    },

    PatternCategory.BEST_PRACTICES: {
        // ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "invalid_model": QueryPattern(
            name="invalid_model",
            pattern=r'model\s+([A-Z][a-zA-Z0-9_]*)\s*{[^}]*}',
            extract=lambda m: {
                "type": "invalid_model",
                "model": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potentially invalid model definitions", "examples": ["model user {}"]}
        ),
        "relation_error": QueryPattern(
            name="relation_error",
            pattern=r'@relation\s*\(\s*fields:\s*\[([^\]]+)\]\s*,\s*references:\s*\[([^\]]+)\]\s*\)',
            extract=lambda m: {
                "type": "relation_error",
                "fields": m.group(1),
                "references": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potential relation errors", "examples": ["@relation(fields: [authorId], references: [id])"]}
        ),
        "type_mismatch": QueryPattern(
            name="type_mismatch",
            pattern=r'(\w+)\s+(\w+)\s+@(?:id|unique|default)\([^)]*\)',
            extract=lambda m: {
                "type": "type_mismatch",
                "field": m.group(2),
                "type": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potential type mismatches", "examples": ["String id @id @default(uuid())"]}
        ),
        "missing_relation": QueryPattern(
            name="missing_relation",
            pattern=r'(\w+)\s+(\w+)\s*(?!@relation)',
            extract=lambda m: {
                "type": "missing_relation",
                "field": m.group(2),
                "type": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.8
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potentially missing relations", "examples": ["User author"]}
        ),
        "invalid_enum": QueryPattern(
            name="invalid_enum",
            pattern=r'enum\s+([A-Z][a-zA-Z0-9_]*)\s*{[^}]*}',
            extract=lambda m: {
                "type": "invalid_enum",
                "enum": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potentially invalid enum definitions", "examples": ["enum status {}"]}
        )
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

class PrismaPatternLearner(CrossProjectPatternLearner):
    """Enhanced Prisma pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Prisma-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("prisma", FileType.SCHEMA)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Prisma patterns
        await self._pattern_processor.register_language_patterns(
            "prisma", 
            PRISMA_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "prisma_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(PRISMA_PATTERNS),
                "capabilities": list(PRISMA_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="prisma",
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
            
            # Finally add Prisma-specific patterns
            async with AsyncErrorBoundary("prisma_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "prisma",
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
                prisma_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(prisma_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "prisma_pattern_learner",
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
                "prisma_pattern_learner",
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
                "prisma_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "prisma_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_prisma_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Prisma pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Prisma-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("prisma", FileType.SCHEMA)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "prisma", FileType.SCHEMA)
            if parse_result and parse_result.ast:
                context = await create_prisma_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"prisma_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "prisma",
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
        await update_prisma_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "prisma_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_prisma_pattern_context(
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
            language_id="prisma",
            file_type=FileType.SCHEMA
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "prisma"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(PRISMA_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_prisma_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_prisma_pattern_match_result(
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
        metadata={"language": "prisma"}
    )

# Initialize pattern learner
pattern_learner = PrismaPatternLearner()

async def initialize_prisma_patterns():
    """Initialize Prisma patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Prisma patterns
    await pattern_processor.register_language_patterns(
        "prisma",
        PRISMA_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": PRISMA_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await PrismaPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "prisma",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "prisma_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(PRISMA_PATTERNS),
            "capabilities": list(PRISMA_CAPABILITIES)
        }
    )

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
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_prisma_pattern_match_result',
    'update_prisma_pattern_metrics',
    'PrismaPatternContext',
    'pattern_learner'
] 