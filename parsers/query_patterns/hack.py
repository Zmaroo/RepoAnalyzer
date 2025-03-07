"""Query patterns for Hack files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

HACK_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_declaration
                        name: (identifier) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params
                        body: (compound_statement) @syntax.function.body) @syntax.function.def,
                    (method_declaration
                        name: (identifier) @syntax.function.method.name
                        parameters: (parameter_list) @syntax.function.method.params
                        body: (compound_statement) @syntax.function.method.body) @syntax.function.method
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.function.name", {}).get("text", "") or
                        node["captures"].get("syntax.function.method.name", {}).get("text", "")
                    ),
                    "type": "function",
                    "is_method": "syntax.function.method" in node["captures"]
                }
            ),
            "class": QueryPattern(
                pattern="""
                [
                    (class_declaration
                        name: (identifier) @syntax.class.name
                        body: (member_declarations) @syntax.class.body) @syntax.class.def,
                    (trait_declaration
                        name: (identifier) @syntax.trait.name
                        body: (member_declarations) @syntax.trait.body) @syntax.trait.def
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.trait.name", {}).get("text", "")
                    ),
                    "type": "class" if "syntax.class.def" in node["captures"] else "trait"
                }
            ),
            "interface": QueryPattern(
                pattern="""
                (interface_declaration
                    name: (identifier) @syntax.interface.name
                    body: (member_declarations) @syntax.interface.body) @syntax.interface.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.interface.name", {}).get("text", ""),
                    "type": "interface"
                }
            ),
            "enum": QueryPattern(
                pattern="""
                [
                    (enum_declaration
                        name: (identifier) @syntax.enum.name
                        body: (enum_members) @syntax.enum.body) @syntax.enum.def,
                    (enum_class_declaration
                        name: (identifier) @syntax.enum.class.name
                        body: (member_declarations) @syntax.enum.class.body) @syntax.enum.class.def
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.enum.name", {}).get("text", "") or
                        node["captures"].get("syntax.enum.class.name", {}).get("text", "")
                    ),
                    "type": "enum",
                    "is_enum_class": "syntax.enum.class.def" in node["captures"]
                }
            ),
            "typedef": QueryPattern(
                pattern="""
                (alias_declaration
                    name: (identifier) @syntax.typedef.name
                    type: (_) @syntax.typedef.type) @syntax.typedef.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.typedef.name", {}).get("text", ""),
                    "type": "typedef"
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (property_declaration
                        type: (_)? @semantics.variable.type
                        value: (_)? @semantics.variable.value) @semantics.variable.property,
                    (variable_declaration
                        name: (_) @semantics.variable.name
                        value: (_)? @semantics.variable.value) @semantics.variable.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                    "type": "variable",
                    "is_property": "semantics.variable.property" in node["captures"]
                }
            ),
            "expression": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (_) @semantics.expression.name
                        arguments: (_)? @semantics.expression.args) @semantics.expression.call,
                    (binary_expression
                        left: (_) @semantics.expression.binary.left
                        right: (_) @semantics.expression.binary.right) @semantics.expression.binary
                ]
                """,
                extract=lambda node: {
                    "type": "expression",
                    "expression_type": (
                        "call" if "semantics.expression.call" in node["captures"] else
                        "binary" if "semantics.expression.binary" in node["captures"] else
                        "other"
                    )
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment,
                    (doc_comment) @documentation.comment.doc
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment", {}).get("text", "") or
                        node["captures"].get("documentation.comment.doc", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_doc": "documentation.comment.doc" in node["captures"]
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "namespace": QueryPattern(
                pattern="""
                (namespace_declaration
                    name: (_) @structure.namespace.name) @structure.namespace.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.namespace.name", {}).get("text", ""),
                    "type": "namespace"
                }
            ),
            "import": QueryPattern(
                pattern="""
                [
                    (use_declaration
                        clauses: (_) @structure.import.clauses) @structure.import.use,
                    (require_clause
                        path: (_) @structure.import.path) @structure.import.require
                ]
                """,
                extract=lambda node: {
                    "type": "import",
                    "is_use": "structure.import.use" in node["captures"],
                    "is_require": "structure.import.require" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.TYPE_SAFETY: {
            "type_system_patterns": QueryPattern(
                pattern="""
                [
                    (alias_declaration
                        name: (identifier) @type.alias.name
                        type: (_) @type.alias.type) @type.alias,
                        
                    (function_declaration
                        return_type: (_) @type.func.return
                        parameters: (parameter_list
                            (parameter
                                type: (_) @type.param.type)*)) @type.func,
                                
                    (property_declaration
                        type: (_) @type.prop.type) @type.prop
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "type_system",
                    "uses_type_alias": "type.alias" in node["captures"],
                    "uses_return_type": "type.func.return" in node["captures"],
                    "uses_parameter_types": "type.param.type" in node["captures"],
                    "uses_property_types": "type.prop.type" in node["captures"],
                    "type_name": node["captures"].get("type.alias.name", {}).get("text", ""),
                    "return_type": node["captures"].get("type.func.return", {}).get("text", ""),
                    "property_type": node["captures"].get("type.prop.type", {}).get("text", ""),
                    "uses_generics": "<" in (
                        node["captures"].get("type.alias.type", {}).get("text", "") or
                        node["captures"].get("type.func.return", {}).get("text", "") or
                        node["captures"].get("type.param.type", {}).get("text", "") or
                        node["captures"].get("type.prop.type", {}).get("text", "")
                    )
                }
            )
        },
        PatternPurpose.ASYNC: {
            "async_patterns": QueryPattern(
                pattern="""
                [
                    (function_declaration
                        modifiers: (_) @async.func.modifiers
                        (#match? @async.func.modifiers "async")
                        name: (identifier) @async.func.name) @async.func,
                        
                    (call_expression
                        function: (qualified_identifier
                            name: (identifier) @async.call.name
                            (#match? @async.call.name "await"))) @async.await,
                            
                    (call_expression
                        function: (qualified_identifier
                            name: (identifier) @async.api.name
                            (#match? @async.api.name "genFromAwait|join|gen|gen_map|gen_filter"))) @async.api
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "async_programming",
                    "uses_async_function": "async.func" in node["captures"],
                    "uses_await": "async.await" in node["captures"],
                    "uses_async_apis": "async.api" in node["captures"],
                    "async_function_name": node["captures"].get("async.func.name", {}).get("text", ""),
                    "async_api_name": node["captures"].get("async.api.name", {}).get("text", ""),
                    "is_concurrent": "join" in (node["captures"].get("async.api.name", {}).get("text", "") or "")
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "shape_expressions": QueryPattern(
                pattern="""
                [
                    (shape_type_specifier
                        fields: (shape_field_specifier)+ @shape.fields) @shape.type,
                        
                    (function_parameter_declaration
                        type: (shape_type_specifier) @shape.param.type
                        name: (variable) @shape.param.name) @shape.param
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "shape_expressions",
                    "uses_shape_type": "shape.type" in node["captures"],
                    "uses_shape_parameter": "shape.param" in node["captures"],
                    "field_count": len((node["captures"].get("shape.fields", {}).get("text", "") or "").split(",")),
                    "parameter_name": node["captures"].get("shape.param.name", {}).get("text", ""),
                    "is_complex_shape": len((node["captures"].get("shape.fields", {}).get("text", "") or "").split(",")) > 3
                }
            )
        },
        PatternPurpose.UI: {
            "xhp_patterns": QueryPattern(
                pattern="""
                [
                    (xhp_class_declaration
                        name: (identifier) @xhp.class.name
                        attributes: (xhp_attribute_declaration)* @xhp.class.attrs
                        categories: (xhp_category_declaration)* @xhp.class.categories) @xhp.class,
                        
                    (xhp_expression
                        name: (identifier) @xhp.expr.name
                        attributes: (xhp_attribute)* @xhp.expr.attrs
                        body: (_)? @xhp.expr.body) @xhp.expr
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "xhp_patterns",
                    "uses_xhp_class": "xhp.class" in node["captures"],
                    "uses_xhp_expression": "xhp.expr" in node["captures"],
                    "class_name": node["captures"].get("xhp.class.name", {}).get("text", ""),
                    "component_name": node["captures"].get("xhp.expr.name", {}).get("text", ""),
                    "has_attributes": "xhp.class.attrs" in node["captures"] and node["captures"].get("xhp.class.attrs", {}).get("text", ""),
                    "has_categories": "xhp.class.categories" in node["captures"] and node["captures"].get("xhp.class.categories", {}).get("text", ""),
                    "is_ui_component": (
                        "xhp.class" in node["captures"] or 
                        "xhp.expr" in node["captures"]
                    )
                }
            )
        }
    }
} 