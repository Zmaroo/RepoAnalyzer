"""
Query patterns for Prisma schema files.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

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