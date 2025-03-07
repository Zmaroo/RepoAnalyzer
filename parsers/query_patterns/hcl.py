"""Query patterns for HCL files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

HCL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                (function_call
                    name: (identifier) @syntax.function.name
                    arguments: (function_arguments)? @syntax.function.args) @syntax.function.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function"
                }
            ),
            "block": QueryPattern(
                pattern="""
                (block
                    type: (identifier) @syntax.block.type
                    labels: (string_lit)* @syntax.block.labels
                    body: (body) @syntax.block.body) @syntax.block.def
                """,
                extract=lambda node: {
                    "type": "block",
                    "block_type": node["captures"].get("syntax.block.type", {}).get("text", ""),
                    "labels": node["captures"].get("syntax.block.labels", {}).get("text", "")
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                (attribute
                    name: (identifier) @semantics.variable.name
                    value: (expression) @semantics.variable.value) @semantics.variable.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                    "type": "variable"
                }
            ),
            "expression": QueryPattern(
                pattern="""
                [
                    (expression
                        content: (_) @semantics.expression.content) @semantics.expression.def,
                    (template_expr
                        content: (_) @semantics.expression.template.content) @semantics.expression.template
                ]
                """,
                extract=lambda node: {
                    "type": "expression",
                    "is_template": "semantics.expression.template" in node["captures"]
                }
            ),
            "type": QueryPattern(
                pattern="""
                (type_expr
                    name: (identifier) @semantics.type.name) @semantics.type.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                    "type": "type"
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="(comment) @documentation.comment",
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "type": "comment"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "block": QueryPattern(
                pattern="""
                (config_file
                    body: (body) @structure.block.body) @structure.block.def
                """,
                extract=lambda node: {
                    "type": "config_file"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.INFRASTRUCTURE: {
            "resource_patterns": QueryPattern(
                pattern="""
                [
                    (block
                        type: (identifier) @res.block.type
                        (#match? @res.block.type "^resource$")
                        labels: [
                            (string_lit) @res.block.resource_type
                            (string_lit) @res.block.resource_name
                        ]
                        body: (body) @res.block.body) @res.block,
                        
                    (block
                        type: (identifier) @res.data.type
                        (#match? @res.data.type "^data$")
                        labels: [
                            (string_lit) @res.data.data_type
                            (string_lit) @res.data.data_name
                        ]
                        body: (body) @res.data.body) @res.data
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "resource_definition" if "res.block" in node["captures"] else "data_source",
                    "resource_type": node["captures"].get("res.block.resource_type", {}).get("text", ""),
                    "resource_name": node["captures"].get("res.block.resource_name", {}).get("text", ""),
                    "data_type": node["captures"].get("res.data.data_type", {}).get("text", ""),
                    "data_name": node["captures"].get("res.data.data_name", {}).get("text", ""),
                    "is_resource": "res.block" in node["captures"],
                    "is_data_source": "res.data" in node["captures"],
                    "definition_body_size": len((node["captures"].get("res.block.body", {}).get("text", "") or 
                                            node["captures"].get("res.data.body", {}).get("text", "") or "").split("\n"))
                }
            )
        },
        PatternPurpose.VARIABLES: {
            "variable_usage": QueryPattern(
                pattern="""
                [
                    (block
                        type: (identifier) @var.block.type
                        (#match? @var.block.type "^variable$")
                        labels: (string_lit) @var.block.name
                        body: (body) @var.block.body) @var.block,
                        
                    (template_expr
                        content: (_) @var.expr.content) @var.expr,
                        
                    (attribute
                        name: (identifier) @var.attr.name
                        value: (expression 
                            (template_expr) @var.attr.template)) @var.attr
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "variable_definition" if "var.block" in node["captures"] else
                        "variable_reference" if "var.expr" in node["captures"] else
                        "attribute_with_variable" if "var.attr" in node["captures"] else
                        "other"
                    ),
                    "variable_name": node["captures"].get("var.block.name", {}).get("text", "").strip('"\''),
                    "uses_template_expression": "var.expr" in node["captures"],
                    "attribute_name": node["captures"].get("var.attr.name", {}).get("text", ""),
                    "template_content": (
                        node["captures"].get("var.expr.content", {}).get("text", "") or
                        node["captures"].get("var.attr.template", {}).get("text", "")
                    ),
                    "has_default_value": "default" in (node["captures"].get("var.block.body", {}).get("text", "") or "")
                }
            )
        },
        PatternPurpose.PROVIDERS: {
            "provider_configuration": QueryPattern(
                pattern="""
                [
                    (block
                        type: (identifier) @prov.block.type
                        (#match? @prov.block.type "^provider$")
                        labels: (string_lit) @prov.block.name
                        body: (body) @prov.block.body) @prov.block,
                        
                    (block
                        type: (identifier) @prov.required.type
                        (#match? @prov.required.type "^required_providers$")
                        body: (body) @prov.required.body) @prov.required
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "provider_block" if "prov.block" in node["captures"] else
                        "required_providers" if "prov.required" in node["captures"] else
                        "other"
                    ),
                    "provider_name": node["captures"].get("prov.block.name", {}).get("text", "").strip('"\''),
                    "provider_configuration": node["captures"].get("prov.block.body", {}).get("text", ""),
                    "requires_multiple_providers": "prov.required" in node["captures"],
                    "uses_version_constraints": "version" in (
                        node["captures"].get("prov.block.body", {}).get("text", "") or
                        node["captures"].get("prov.required.body", {}).get("text", "") or ""
                    )
                }
            )
        },
        PatternPurpose.MODULES: {
            "module_patterns": QueryPattern(
                pattern="""
                [
                    (block
                        type: (identifier) @mod.block.type
                        (#match? @mod.block.type "^module$")
                        labels: (string_lit) @mod.block.name
                        body: (body) @mod.block.body) @mod.block,
                        
                    (attribute
                        name: (identifier) @mod.output.name
                        (#match? @mod.output.name "^output$")
                        value: (expression) @mod.output.value) @mod.output
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "module_definition" if "mod.block" in node["captures"] else
                        "module_output" if "mod.output" in node["captures"] else
                        "other"
                    ),
                    "module_name": node["captures"].get("mod.block.name", {}).get("text", "").strip('"\''),
                    "uses_source_attribute": "source" in (node["captures"].get("mod.block.body", {}).get("text", "") or ""),
                    "passes_variables": "var." in (node["captures"].get("mod.block.body", {}).get("text", "") or ""),
                    "module_complexity": len((node["captures"].get("mod.block.body", {}).get("text", "") or "").split("\n"))
                }
            )
        }
    }
} 