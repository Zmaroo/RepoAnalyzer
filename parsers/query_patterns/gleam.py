"""Query patterns for Gleam files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

GLEAM_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                (function_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list)? @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function"
                }
            ),
            "class": QueryPattern(
                pattern="""
                (class_declaration
                    name: (identifier) @syntax.class.name
                    body: (class_body)? @syntax.class.body) @syntax.class.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                    "type": "class"
                }
            ),
            "interface": QueryPattern(
                pattern="""
                (interface_declaration
                    name: (identifier) @syntax.interface.name
                    body: (interface_body)? @syntax.interface.body) @syntax.interface.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.interface.name", {}).get("text", ""),
                    "type": "interface"
                }
            ),
            "typedef": QueryPattern(
                pattern="""
                (typedef_declaration
                    name: (identifier) @syntax.typedef.name
                    type: (type)? @syntax.typedef.type) @syntax.typedef.def
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
                (variable_declaration
                    name: (identifier) @semantics.variable.name
                    initializer: (expression)? @semantics.variable.value) @semantics.variable.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                    "type": "variable"
                }
            ),
            "type": QueryPattern(
                pattern="""
                (type
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
            "import": QueryPattern(
                pattern="""
                (import_statement
                    package: (package_name)? @structure.import.package
                    type: (type_name)? @structure.import.type) @structure.import.def
                """,
                extract=lambda node: {
                    "package": node["captures"].get("structure.import.package", {}).get("text", ""),
                    "type": node["captures"].get("structure.import.type", {}).get("text", "")
                }
            ),
            "package": QueryPattern(
                pattern="""
                (package_statement
                    name: (package_name) @structure.package.name) @structure.package.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.package.name", {}).get("text", ""),
                    "type": "package"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "functional_patterns": QueryPattern(
                pattern="""
                [
                    (fn_expr
                        arms: (_) @fp.fn.arms) @fp.fn,
                        
                    (case_expr
                        subjects: (_) @fp.case.subjects
                        arms: (_) @fp.case.arms) @fp.case,
                        
                    (pipe_expr
                        argument: (_) @fp.pipe.arg
                        target: (_) @fp.pipe.target) @fp.pipe,
                        
                    (application
                        fn: (_) @fp.app.fn
                        arguments: (_) @fp.app.args) @fp.app,
                        
                    (list_expr
                        elements: (_) @fp.list.elements) @fp.list,
                        
                    (record_expr
                        fields: (_) @fp.record.fields) @fp.record
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "lambda" if "fp.fn" in node["captures"] else
                        "case_expression" if "fp.case" in node["captures"] else
                        "pipe_operator" if "fp.pipe" in node["captures"] else
                        "function_application" if "fp.app" in node["captures"] else
                        "list_expression" if "fp.list" in node["captures"] else
                        "record_expression" if "fp.record" in node["captures"] else
                        "other"
                    ),
                    "uses_pattern_matching": "fp.case" in node["captures"],
                    "uses_pipe_operator": "fp.pipe" in node["captures"],
                    "uses_lambda": "fp.fn" in node["captures"],
                    "uses_higher_order_function": (
                        "fp.app" in node["captures"] and 
                        "fp.fn" in (node["captures"].get("fp.app.args", {}).get("text", "") or "")
                    ),
                    "is_pointfree_style": (
                        "fp.app" in node["captures"] and 
                        node["captures"].get("fp.app.args", {}).get("text", "").count(",") == 0
                    )
                }
            )
        },
        PatternPurpose.TYPE_SAFETY: {
            "type_safety": QueryPattern(
                pattern="""
                [
                    (type_alias
                        name: (_) @type.alias.name
                        parameters: (_)? @type.alias.params
                        value: (_) @type.alias.value) @type.alias,
                        
                    (type_definition
                        name: (_) @type.def.name
                        parameters: (_)? @type.def.params
                        constructors: (_) @type.def.constructors) @type.def,
                        
                    (opaque_type_declaration
                        name: (_) @type.opaque.name
                        parameters: (_)? @type.opaque.params
                        constructors: (_) @type.opaque.constructors) @type.opaque,
                        
                    (variant
                        name: (_) @type.variant.name
                        fields: (_)? @type.variant.fields) @type.variant,
                        
                    (bit_array_pattern
                        segments: (_) @type.bits.segments) @type.bits,
                        
                    (fn_signature
                        parameter_types: (_) @type.fn.params
                        return_type: (_) @type.fn.return) @type.fn
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "type_alias" if "type.alias" in node["captures"] else
                        "type_definition" if "type.def" in node["captures"] else
                        "opaque_type" if "type.opaque" in node["captures"] else
                        "variant_type" if "type.variant" in node["captures"] else
                        "bit_array" if "type.bits" in node["captures"] else
                        "function_signature" if "type.fn" in node["captures"] else
                        "other"
                    ),
                    "type_name": (
                        node["captures"].get("type.alias.name", {}).get("text", "") or
                        node["captures"].get("type.def.name", {}).get("text", "") or
                        node["captures"].get("type.opaque.name", {}).get("text", "") or
                        node["captures"].get("type.variant.name", {}).get("text", "")
                    ),
                    "uses_generics": any(
                        params and "<" in params
                        for params in [
                            node["captures"].get("type.alias.params", {}).get("text", ""),
                            node["captures"].get("type.def.params", {}).get("text", ""),
                            node["captures"].get("type.opaque.params", {}).get("text", "")
                        ]
                    ),
                    "uses_opaque_types": "type.opaque" in node["captures"],
                    "has_explicit_return_type": "type.fn.return" in node["captures"] and node["captures"].get("type.fn.return", {}).get("text", "")
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "module_organization": QueryPattern(
                pattern="""
                [
                    (module_definition
                        name: (_) @mod.name
                        body: (_) @mod.body) @mod,
                        
                    (import_expression
                        name: (_) @mod.import.name
                        alias: (_)? @mod.import.alias
                        unqualified_imports: (_)? @mod.import.unqualified) @mod.import,
                        
                    (public_function
                        name: (_) @mod.pub.name
                        body: (_) @mod.pub.body) @mod.pub.func,
                        
                    (function
                        name: (_) @mod.priv.name
                        body: (_) @mod.priv.body) @mod.priv.func,
                        
                    (public_constructor
                        name: (_) @mod.pub.type) @mod.pub.type,
                        
                    (constant
                        name: (_) @mod.const.name
                        value: (_) @mod.const.value) @mod.const
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "module_definition" if "mod" in node["captures"] and "mod.name" in node["captures"] else
                        "import_expression" if "mod.import" in node["captures"] else
                        "public_function" if "mod.pub.func" in node["captures"] else
                        "private_function" if "mod.priv.func" in node["captures"] else
                        "public_type" if "mod.pub.type" in node["captures"] else
                        "constant" if "mod.const" in node["captures"] else
                        "other"
                    ),
                    "module_name": node["captures"].get("mod.name", {}).get("text", ""),
                    "imported_module": node["captures"].get("mod.import.name", {}).get("text", ""),
                    "uses_unqualified_imports": "mod.import.unqualified" in node["captures"] and node["captures"].get("mod.import.unqualified", {}).get("text", ""),
                    "uses_aliased_imports": "mod.import.alias" in node["captures"] and node["captures"].get("mod.import.alias", {}).get("text", ""),
                    "has_public_interface": "mod.pub.func" in node["captures"] or "mod.pub.type" in node["captures"],
                    "is_api_function": "mod.pub.func" in node["captures"] and "pub" in (node["captures"].get("mod.pub.name", {}).get("text", "") or "")
                }
            )
        },
        PatternPurpose.ERROR_HANDLING: {
            "error_handling": QueryPattern(
                pattern="""
                [
                    (application
                        fn: (_) @error.result.fn
                        (#match? @error.result.fn "Result")
                        arguments: (_) @error.result.args) @error.result,
                        
                    (binary_expr
                        left: (_) @error.try.left
                        right: (_) @error.try.right
                        (#match? @error.try.right "try")) @error.try,
                        
                    (tuple_expr
                        elements: (_) @error.tuple.elements
                        (#match? @error.tuple.elements "Error,")) @error.tuple,
                        
                    (assert_expr
                        pattern: (_) @error.assert.pattern
                        value: (_) @error.assert.value) @error.assert
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "result_type" if "error.result" in node["captures"] else
                        "try_operator" if "error.try" in node["captures"] else
                        "error_tuple" if "error.tuple" in node["captures"] else
                        "assert_expression" if "error.assert" in node["captures"] else
                        "other"
                    ),
                    "uses_result_type": "error.result" in node["captures"],
                    "uses_try_operator": "error.try" in node["captures"],
                    "uses_error_tuple": "error.tuple" in node["captures"],
                    "uses_assert": "error.assert" in node["captures"],
                    "error_handling_approach": (
                        "result_monad" if "error.result" in node["captures"] else
                        "try_operator" if "error.try" in node["captures"] else
                        "tuple_pattern" if "error.tuple" in node["captures"] else
                        "assertion" if "error.assert" in node["captures"] else
                        "other"
                    )
                }
            )
        }
    }
} 