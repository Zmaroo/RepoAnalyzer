"""Query patterns for PureScript files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)

PURESCRIPT_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_declaration
                        name: (identifier) @syntax.function.name
                        parameters: (parameter)* @syntax.function.params
                        expression: (expression) @syntax.function.body) @syntax.function.def,
                    (type_signature
                        name: (identifier) @syntax.function.sig.name
                        type: (type_expression) @syntax.function.sig.type) @syntax.function.sig
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.function.name", {}).get("text", "") or
                        node["captures"].get("syntax.function.sig.name", {}).get("text", "")
                    ),
                    "type": "function",
                    "has_signature": "syntax.function.sig" in node["captures"],
                    "has_params": "syntax.function.params" in node["captures"]
                }
            ),
            "class": QueryPattern(
                pattern="""
                [
                    (data_declaration
                        name: (identifier) @syntax.class.data.name
                        constructors: (data_constructors) @syntax.class.data.constructors) @syntax.class.data,
                    (newtype_declaration
                        name: (identifier) @syntax.class.newtype.name
                        constructor: (newtype_constructor) @syntax.class.newtype.constructor) @syntax.class.newtype,
                    (class_declaration
                        name: (identifier) @syntax.class.typeclass.name
                        methods: (class_methods) @syntax.class.typeclass.methods) @syntax.class.typeclass,
                    (instance_declaration
                        class_name: (qualified_identifier) @syntax.class.instance.class
                        type_name: (type_expression) @syntax.class.instance.type) @syntax.class.instance
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.class.data.name", {}).get("text", "") or
                        node["captures"].get("syntax.class.newtype.name", {}).get("text", "") or
                        node["captures"].get("syntax.class.typeclass.name", {}).get("text", "")
                    ),
                    "type": (
                        "data" if "syntax.class.data" in node["captures"] else
                        "newtype" if "syntax.class.newtype" in node["captures"] else
                        "typeclass" if "syntax.class.typeclass" in node["captures"] else
                        "instance" if "syntax.class.instance" in node["captures"] else
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
                    (line_comment) @documentation.line_comment
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment", {}).get("text", "") or
                        node["captures"].get("documentation.line_comment", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_line_comment": "documentation.line_comment" in node["captures"]
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "module": QueryPattern(
                pattern="""
                [
                    (module_declaration
                        name: (module_name) @structure.module.name) @structure.module.def,
                    (import_declaration
                        module: (module_name) @structure.import.name
                        qualified: (qualified)? @structure.import.qualified
                        hiding: (hiding)? @structure.import.hiding
                        imports: (import_list)? @structure.import.list) @structure.import,
                    (export_list
                        (export) @structure.export) @structure.exports,
                    (where) @structure.where
                ]
                """,
                extract=lambda node: {
                    "type": (
                        "module" if "structure.module.def" in node["captures"] else
                        "import" if "structure.import" in node["captures"] else
                        "export" if "structure.exports" in node["captures"] else
                        "where" if "structure.where" in node["captures"] else
                        "other"
                    ),
                    "name": (
                        node["captures"].get("structure.module.name", {}).get("text", "") or
                        node["captures"].get("structure.import.name", {}).get("text", "")
                    ),
                    "is_qualified": "structure.import.qualified" in node["captures"],
                    "has_hiding": "structure.import.hiding" in node["captures"],
                    "has_imports": "structure.import.list" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.FUNCTIONAL: {
            "functional_patterns": QueryPattern(
                pattern="""
                [
                    (expression
                        (call_expression
                            expression: (identifier) @learning.func.call.name {
                                match: "^map$|^filter$|^fold$|^reduce$|^compose$|^pipe$|^flow$|^curry"
                            }
                            arguments: (arguments) @learning.func.call.args)) @learning.func.call,
                    (expression
                        (infix_expression
                            operator: (operator) @learning.func.infix.op {
                                match: "^\\$|^<\\$>|^<\\*>|^>>=$|^>>>$|^<<<$|^\\|>$|^<\\|$"
                            })) @learning.func.infix,
                    (case_expression
                        head: (_) @learning.func.case.head
                        branches: (case_branches
                            (case_branch
                                pattern: (pattern) @learning.func.case.pattern
                                expression: (expression) @learning.func.case.expr))) @learning.func.case,
                    (expression
                        (lambda_expression
                            parameters: (parameter)* @learning.func.lambda.params
                            expression: (expression) @learning.func.lambda.body)) @learning.func.lambda
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "functional_patterns",
                    "is_higher_order_call": "learning.func.call" in node["captures"],
                    "uses_function_composition": "learning.func.infix" in node["captures"] and any(
                        op in (node["captures"].get("learning.func.infix.op", {}).get("text", "") or "")
                        for op in [">>>", "<<<", "|>", "<|"]
                    ),
                    "uses_functor_applicative": "learning.func.infix" in node["captures"] and any(
                        op in (node["captures"].get("learning.func.infix.op", {}).get("text", "") or "")
                        for op in ["<$>", "<*>"]
                    ),
                    "uses_monadic_binding": "learning.func.infix" in node["captures"] and ">>=" in (node["captures"].get("learning.func.infix.op", {}).get("text", "") or ""),
                    "uses_pattern_matching": "learning.func.case" in node["captures"],
                    "uses_lambda": "learning.func.lambda" in node["captures"],
                    "higher_order_function": node["captures"].get("learning.func.call.name", {}).get("text", ""),
                    "pattern_type": (
                        "higher_order_function" if "learning.func.call" in node["captures"] else
                        "function_composition" if "learning.func.infix" in node["captures"] and any(
                            op in (node["captures"].get("learning.func.infix.op", {}).get("text", "") or "")
                            for op in [">>>", "<<<", "|>", "<|"]
                        ) else
                        "functor_applicative" if "learning.func.infix" in node["captures"] and any(
                            op in (node["captures"].get("learning.func.infix.op", {}).get("text", "") or "")
                            for op in ["<$>", "<*>"]
                        ) else
                        "monadic_binding" if "learning.func.infix" in node["captures"] and ">>=" in (node["captures"].get("learning.func.infix.op", {}).get("text", "") or "") else
                        "pattern_matching" if "learning.func.case" in node["captures"] else
                        "lambda" if "learning.func.lambda" in node["captures"] else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.TYPE_SYSTEM: {
            "type_system": QueryPattern(
                pattern="""
                [
                    (type_declaration
                        name: (identifier) @learning.type.decl.name
                        type: (type_expression) @learning.type.decl.expr) @learning.type.decl,
                    (data_declaration
                        name: (identifier) @learning.type.data.name
                        constructors: (data_constructors) @learning.type.data.ctors) @learning.type.data,
                    (newtype_declaration
                        name: (identifier) @learning.type.newtype.name
                        constructor: (newtype_constructor) @learning.type.newtype.ctor) @learning.type.newtype,
                    (class_declaration
                        name: (identifier) @learning.type.class.name
                        methods: (class_methods) @learning.type.class.methods) @learning.type.class,
                    (instance_declaration
                        class_name: (qualified_identifier) @learning.type.instance.class
                        type_name: (type_expression) @learning.type.instance.type
                        methods: (instance_methods) @learning.type.instance.methods) @learning.type.instance,
                    (function_declaration
                        signature: (type_signature
                            name: (identifier) @learning.type.sig.name
                            type: (type_expression) @learning.type.sig.type)) @learning.type.sig.func
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "type_system",
                    "is_type_alias": "learning.type.decl" in node["captures"],
                    "is_data_type": "learning.type.data" in node["captures"],
                    "is_newtype": "learning.type.newtype" in node["captures"],
                    "is_typeclass": "learning.type.class" in node["captures"],
                    "is_instance": "learning.type.instance" in node["captures"],
                    "has_type_signature": "learning.type.sig.func" in node["captures"],
                    "type_name": (
                        node["captures"].get("learning.type.decl.name", {}).get("text", "") or
                        node["captures"].get("learning.type.data.name", {}).get("text", "") or
                        node["captures"].get("learning.type.newtype.name", {}).get("text", "") or
                        node["captures"].get("learning.type.class.name", {}).get("text", "")
                    ),
                    "type_expression": (
                        node["captures"].get("learning.type.decl.expr", {}).get("text", "") or
                        node["captures"].get("learning.type.sig.type", {}).get("text", "")
                    ),
                    "typeclass_name": node["captures"].get("learning.type.instance.class", {}).get("text", ""),
                    "instance_type": node["captures"].get("learning.type.instance.type", {}).get("text", ""),
                    "function_with_signature": node["captures"].get("learning.type.sig.name", {}).get("text", ""),
                    "type_system_element": (
                        "type_alias" if "learning.type.decl" in node["captures"] else
                        "data_type" if "learning.type.data" in node["captures"] else
                        "newtype" if "learning.type.newtype" in node["captures"] else
                        "typeclass" if "learning.type.class" in node["captures"] else
                        "instance" if "learning.type.instance" in node["captures"] else
                        "type_signature" if "learning.type.sig.func" in node["captures"] else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.EFFECT_HANDLING: {
            "effect_handling": QueryPattern(
                pattern="""
                [
                    (expression
                        (call_expression
                            expression: (identifier) @learning.effect.call.name {
                                match: "^pure$|^bind$|^discard$|^liftEffect$|^unsafePerformEffect$"
                            })) @learning.effect.call,
                    (do_block
                        (statement)* @learning.effect.do.stmts) @learning.effect.do,
                    (do_block
                        (statement
                            (bind
                                pattern: (pattern) @learning.effect.bind.pat
                                expression: (expression) @learning.effect.bind.expr))) @learning.effect.bind,
                    (type_expression
                        (type_constructor) @learning.effect.type.ctor {
                            match: "^Effect$|^Aff$|^MonadEffect$|^ExceptT$|^ReaderT$|^StateT$|^Either$|^Maybe$"
                        }) @learning.effect.type
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "effect_handling",
                    "uses_effect_functions": "learning.effect.call" in node["captures"],
                    "uses_do_notation": "learning.effect.do" in node["captures"],
                    "uses_bind_in_do": "learning.effect.bind" in node["captures"],
                    "uses_effect_types": "learning.effect.type" in node["captures"],
                    "effect_function": node["captures"].get("learning.effect.call.name", {}).get("text", ""),
                    "effect_type": node["captures"].get("learning.effect.type.ctor", {}).get("text", ""),
                    "bind_pattern": node["captures"].get("learning.effect.bind.pat", {}).get("text", ""),
                    "effect_style": (
                        "pure_function" if "learning.effect.call" in node["captures"] and node["captures"].get("learning.effect.call.name", {}).get("text", "") == "pure" else
                        "do_notation" if "learning.effect.do" in node["captures"] else
                        "effect_lifting" if "learning.effect.call" in node["captures"] and "liftEffect" in node["captures"].get("learning.effect.call.name", {}).get("text", "") else
                        "unsafe_effect" if "learning.effect.call" in node["captures"] and "unsafePerformEffect" in node["captures"].get("learning.effect.call.name", {}).get("text", "") else
                        "bind_operation" if "learning.effect.call" in node["captures"] and "bind" in node["captures"].get("learning.effect.call.name", {}).get("text", "") else
                        "monad_transformer" if "learning.effect.type" in node["captures"] and any(
                            t in node["captures"].get("learning.effect.type.ctor", {}).get("text", "")
                            for t in ["ExceptT", "ReaderT", "StateT"]
                        ) else
                        "unknown"
                    )
                }
            )
        }
    }
}