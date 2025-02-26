"""Purescript-specific Tree-sitter patterns.

These queries capture key constructs in Purescript:
  - Module declarations.
  - Value declarations (used for functions).
  - Data declarations.
  - Class declarations.
  
Adjust node names as needed to match your Purescript grammar.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

PURESCRIPT_PATTERNS_FOR_LEARNING = {
    "functional_patterns": {
        "pattern": """
        [
            (function_declaration
                name: (identifier) @func.name
                parameters: (parameter)* @func.params
                expression: (expression) @func.body) @func.decl,
                
            (expression
                (call_expression
                    expression: (identifier) @func.call.name {
                        match: "^map$|^filter$|^fold$|^reduce$|^compose$|^pipe$|^flow$|^curry"
                    }
                    arguments: (arguments) @func.call.args)) @func.call,
                
            (expression
                (infix_expression
                    operator: (operator) @func.infix.op {
                        match: "^\\$|^<\\$>|^<\\*>|^>>=$|^>>>$|^<<<$|^\\|>$|^<\\|$"
                    })) @func.infix,
                    
            (case_expression
                head: (_) @func.case.head
                branches: (case_branches
                    (case_branch
                        pattern: (pattern) @func.case.pattern
                        expression: (expression) @func.case.expr))) @func.case,
                        
            (expression
                (lambda_expression
                    parameters: (parameter)* @func.lambda.params
                    expression: (expression) @func.lambda.body)) @func.lambda
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional_patterns",
            "is_function_declaration": "func.decl" in node["captures"],
            "is_higher_order_call": "func.call" in node["captures"],
            "uses_function_composition": "func.infix" in node["captures"] and any(
                op in (node["captures"].get("func.infix.op", {}).get("text", "") or "")
                for op in [">>>", "<<<", "|>", "<|"]
            ),
            "uses_functor_applicative": "func.infix" in node["captures"] and any(
                op in (node["captures"].get("func.infix.op", {}).get("text", "") or "")
                for op in ["<$>", "<*>"]
            ),
            "uses_monadic_binding": "func.infix" in node["captures"] and ">>=" in (node["captures"].get("func.infix.op", {}).get("text", "") or ""),
            "uses_pattern_matching": "func.case" in node["captures"],
            "uses_lambda": "func.lambda" in node["captures"],
            "function_name": node["captures"].get("func.name", {}).get("text", ""),
            "higher_order_function": node["captures"].get("func.call.name", {}).get("text", ""),
            "pattern_type": (
                "function_declaration" if "func.decl" in node["captures"] else
                "higher_order_function" if "func.call" in node["captures"] else
                "function_composition" if "func.infix" in node["captures"] and any(
                    op in (node["captures"].get("func.infix.op", {}).get("text", "") or "")
                    for op in [">>>", "<<<", "|>", "<|"]
                ) else
                "functor_applicative" if "func.infix" in node["captures"] and any(
                    op in (node["captures"].get("func.infix.op", {}).get("text", "") or "")
                    for op in ["<$>", "<*>"]
                ) else
                "monadic_binding" if "func.infix" in node["captures"] and ">>=" in (node["captures"].get("func.infix.op", {}).get("text", "") or "") else
                "pattern_matching" if "func.case" in node["captures"] else
                "lambda" if "func.lambda" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "type_system": {
        "pattern": """
        [
            (type_declaration
                name: (identifier) @type.decl.name
                type: (type_expression) @type.decl.expr) @type.decl,
                
            (data_declaration
                name: (identifier) @type.data.name
                constructors: (data_constructors) @type.data.ctors) @type.data,
                
            (newtype_declaration
                name: (identifier) @type.newtype.name
                constructor: (newtype_constructor) @type.newtype.ctor) @type.newtype,
                
            (class_declaration
                name: (identifier) @type.class.name
                methods: (class_methods) @type.class.methods) @type.class,
                
            (instance_declaration
                class_name: (qualified_identifier) @type.instance.class
                type_name: (type_expression) @type.instance.type
                methods: (instance_methods) @type.instance.methods) @type.instance,
                
            (function_declaration
                signature: (type_signature
                    name: (identifier) @type.sig.name
                    type: (type_expression) @type.sig.type)) @type.sig.func
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "type_system",
            "is_type_alias": "type.decl" in node["captures"],
            "is_data_type": "type.data" in node["captures"],
            "is_newtype": "type.newtype" in node["captures"],
            "is_typeclass": "type.class" in node["captures"],
            "is_instance": "type.instance" in node["captures"],
            "has_type_signature": "type.sig.func" in node["captures"],
            "type_name": (
                node["captures"].get("type.decl.name", {}).get("text", "") or
                node["captures"].get("type.data.name", {}).get("text", "") or
                node["captures"].get("type.newtype.name", {}).get("text", "") or
                node["captures"].get("type.class.name", {}).get("text", "")
            ),
            "type_expression": (
                node["captures"].get("type.decl.expr", {}).get("text", "") or
                node["captures"].get("type.sig.type", {}).get("text", "")
            ),
            "typeclass_name": node["captures"].get("type.instance.class", {}).get("text", ""),
            "instance_type": node["captures"].get("type.instance.type", {}).get("text", ""),
            "function_with_signature": node["captures"].get("type.sig.name", {}).get("text", ""),
            "type_system_element": (
                "type_alias" if "type.decl" in node["captures"] else
                "data_type" if "type.data" in node["captures"] else
                "newtype" if "type.newtype" in node["captures"] else
                "typeclass" if "type.class" in node["captures"] else
                "instance" if "type.instance" in node["captures"] else
                "type_signature" if "type.sig.func" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "module_organization": {
        "pattern": """
        [
            (module_declaration
                name: (module_name) @mod.name) @mod.decl,
                
            (import_declaration
                module: (module_name) @mod.import.name
                qualified: (qualified)? @mod.import.qualified
                hiding: (hiding)? @mod.import.hiding
                imports: (import_list)? @mod.import.list) @mod.import,
                
            (export_list
                (export) @mod.export) @mod.exports,
                
            (where) @mod.where
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "module_organization",
            "is_module_declaration": "mod.decl" in node["captures"],
            "is_import": "mod.import" in node["captures"],
            "has_explicit_exports": "mod.exports" in node["captures"],
            "module_name": node["captures"].get("mod.name", {}).get("text", ""),
            "imported_module": node["captures"].get("mod.import.name", {}).get("text", ""),
            "is_qualified_import": "mod.import.qualified" in node["captures"],
            "uses_hiding": "mod.import.hiding" in node["captures"],
            "has_selective_imports": len(node["captures"].get("mod.import.list", {}).get("text", "")) > 0 if "mod.import.list" in node["captures"] else False,
            "exported_items": node["captures"].get("mod.export", {}).get("text", ""),
            "module_element": (
                "declaration" if "mod.decl" in node["captures"] else
                "import" if "mod.import" in node["captures"] else
                "export" if "mod.exports" in node["captures"] else
                "where_block" if "mod.where" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "effect_handling": {
        "pattern": """
        [
            (expression
                (call_expression
                    expression: (identifier) @effect.call.name {
                        match: "^pure$|^bind$|^discard$|^liftEffect$|^unsafePerformEffect$"
                    })) @effect.call,
                    
            (do_block
                (statement)* @effect.do.stmts) @effect.do,
                
            (do_block
                (statement
                    (bind
                        pattern: (pattern) @effect.bind.pat
                        expression: (expression) @effect.bind.expr))) @effect.bind,
                        
            (type_expression
                (type_constructor) @effect.type.ctor {
                    match: "^Effect$|^Aff$|^MonadEffect$|^ExceptT$|^ReaderT$|^StateT$|^Either$|^Maybe$"
                }) @effect.type
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "effect_handling",
            "uses_effect_functions": "effect.call" in node["captures"],
            "uses_do_notation": "effect.do" in node["captures"],
            "uses_bind_in_do": "effect.bind" in node["captures"],
            "uses_effect_types": "effect.type" in node["captures"],
            "effect_function": node["captures"].get("effect.call.name", {}).get("text", ""),
            "effect_type": node["captures"].get("effect.type.ctor", {}).get("text", ""),
            "bind_pattern": node["captures"].get("effect.bind.pat", {}).get("text", ""),
            "effect_style": (
                "pure_function" if "effect.call" in node["captures"] and node["captures"].get("effect.call.name", {}).get("text", "") == "pure" else
                "do_notation" if "effect.do" in node["captures"] else
                "effect_lifting" if "effect.call" in node["captures"] and "liftEffect" in node["captures"].get("effect.call.name", {}).get("text", "") else
                "unsafe_effect" if "effect.call" in node["captures"] and "unsafePerformEffect" in node["captures"].get("effect.call.name", {}).get("text", "") else
                "bind_operation" if "effect.call" in node["captures"] and "bind" in node["captures"].get("effect.call.name", {}).get("text", "") else
                "monad_transformer" if "effect.type" in node["captures"] and any(
                    t in node["captures"].get("effect.type.ctor", {}).get("text", "")
                    for t in ["ExceptT", "ReaderT", "StateT"]
                ) else
                "unknown"
            )
        }
    }
}

PURESCRIPT_PATTERNS = {
    **COMMON_PATTERNS,

    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (parameter)* @syntax.function.params
                    expression: (expression) @syntax.function.body) @syntax.function.def,
                (type_signature
                    name: (identifier) @syntax.function.sig.name
                    type: (type_expression) @syntax.function.sig.type) @syntax.function.sig
            ]
            """
        },
        "class": {
            "pattern": """
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
            """
        },
        "expression": {
            "pattern": """
            [
                (do_block
                    (statement)* @syntax.expr.do.statements) @syntax.expr.do,
                (case_expression
                    head: (expression) @syntax.expr.case.head
                    branches: (case_branches) @syntax.expr.case.branches) @syntax.expr.case,
                (lambda_expression
                    parameters: (parameter)* @syntax.expr.lambda.params
                    expression: (expression) @syntax.expr.lambda.body) @syntax.expr.lambda,
                (infix_expression
                    left: (expression) @syntax.expr.infix.left
                    operator: (operator) @syntax.expr.infix.op
                    right: (expression) @syntax.expr.infix.right) @syntax.expr.infix
            ]
            """
        },
        "pattern": {
            "pattern": """
            [
                (pattern) @syntax.pattern
            ]
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            [
                (module_declaration
                    name: (module_name) @structure.module.name
                    exports: (export_list)? @structure.module.exports) @structure.module,
                (import_declaration
                    module: (module_name) @structure.import.module
                    imports: (import_list)? @structure.import.list) @structure.import,
                (export
                    name: (_) @structure.export.name) @structure.export
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_declaration
                    name: (identifier) @structure.type.alias.name
                    type: (type_expression) @structure.type.alias.type) @structure.type.alias,
                (type_expression
                    (forall
                        variables: (type_variable)* @structure.type.forall.vars
                        type: (type_expression) @structure.type.forall.type)) @structure.type.forall
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (line_comment) @documentation.line_comment
            ]
            """
        }
    },
    
    "REPOSITORY_LEARNING": PURESCRIPT_PATTERNS_FOR_LEARNING
}