"""Kotlin-specific Tree-sitter patterns."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

KOTLIN_PATTERNS_FOR_LEARNING = {
    "extension_functions": {
        "pattern": """
        [
            (function_declaration
                modifiers: (_)? @ext.func.modifiers
                receiver_type: (_) @ext.func.receiver 
                name: (simple_identifier) @ext.func.name) @ext.func,
                
            (call_expression
                expression: (navigation_expression
                    expression: (_) @ext.call.receiver
                    value: (simple_identifier) @ext.call.name)) @ext.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "extension_functions",
            "is_extension_definition": "ext.func.receiver" in node["captures"],
            "is_extension_call": "ext.call" in node["captures"],
            "extension_name": node["captures"].get("ext.func.name", {}).get("text", ""),
            "receiver_type": node["captures"].get("ext.func.receiver", {}).get("text", ""),
            "uses_this_keyword": "this" in (node["captures"].get("ext.func", {}).get("text", "") or ""),
            "extension_modifiers": node["captures"].get("ext.func.modifiers", {}).get("text", "")
        }
    },
    
    "coroutine_patterns": {
        "pattern": """
        [
            (function_declaration
                modifiers: (_) @coroutine.func.modifiers
                (#match? @coroutine.func.modifiers "suspend")
                name: (simple_identifier) @coroutine.func.name) @coroutine.func,
                
            (call_expression
                expression: (simple_identifier) @coroutine.call.name
                (#match? @coroutine.call.name "launch|async|withContext|flow|runBlocking|coroutineScope")) @coroutine.call,
                
            (call_expression
                expression: (simple_identifier) @coroutine.await.name
                (#match? @coroutine.await.name "await|yield|delay")) @coroutine.await
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "coroutines",
            "is_suspend_function": "coroutine.func" in node["captures"] and "suspend" in (node["captures"].get("coroutine.func.modifiers", {}).get("text", "") or ""),
            "uses_coroutine_builder": "coroutine.call" in node["captures"],
            "uses_suspension_point": "coroutine.await" in node["captures"],
            "coroutine_builder": node["captures"].get("coroutine.call.name", {}).get("text", ""),
            "suspension_function": node["captures"].get("coroutine.await.name", {}).get("text", ""),
            "suspend_function_name": node["captures"].get("coroutine.func.name", {}).get("text", "")
        }
    },
    
    "data_class_patterns": {
        "pattern": """
        [
            (class_declaration
                modifiers: (_) @data.class.modifiers
                (#match? @data.class.modifiers "data")
                name: (type_identifier) @data.class.name
                primary_constructor: (class_parameters) @data.class.params) @data.class,
                
            (call_expression
                expression: (navigation_expression
                    expression: (_) @data.copy.obj
                    value: (simple_identifier) @data.copy.method
                    (#eq? @data.copy.method "copy"))) @data.copy
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "data_class",
            "is_data_class": "data.class" in node["captures"] and "data" in (node["captures"].get("data.class.modifiers", {}).get("text", "") or ""),
            "uses_copy_method": "data.copy" in node["captures"] and node["captures"].get("data.copy.method", {}).get("text", "") == "copy",
            "class_name": node["captures"].get("data.class.name", {}).get("text", ""),
            "parameter_count": len((node["captures"].get("data.class.params", {}).get("text", "") or ",").split(",")),
            "has_destructuring": "component" in (node["captures"].get("data.class", {}).get("text", "") or "")
        }
    },
    
    "functional_patterns": {
        "pattern": """
        [
            (call_expression
                expression: (simple_identifier) @func.higher.name
                (#match? @func.higher.name "map|filter|flatMap|reduce|fold|forEach|any|all")
                value_arguments: (value_arguments
                    (lambda_literal) @func.higher.lambda)) @func.higher.call,
                    
            (call_expression
                expression: (simple_identifier) @func.scope.name
                (#match? @func.scope.name "let|run|with|apply|also")
                value_arguments: (value_arguments
                    (lambda_literal) @func.scope.lambda)) @func.scope.call,
                    
            (lambda_literal
                lambda_parameters: (_)? @func.lambda.params
                statements: (_) @func.lambda.body) @func.lambda
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional_programming",
            "uses_higher_order_function": "func.higher.call" in node["captures"],
            "uses_scope_function": "func.scope.call" in node["captures"],
            "uses_lambda": "func.lambda" in node["captures"],
            "higher_order_function": node["captures"].get("func.higher.name", {}).get("text", ""),
            "scope_function": node["captures"].get("func.scope.name", {}).get("text", ""),
            "lambda_has_parameters": "func.lambda.params" in node["captures"] and node["captures"].get("func.lambda.params", {}).get("text", ""),
            "functional_pattern_type": (
                "collection_operation" if "func.higher.call" in node["captures"] else
                "scope_function" if "func.scope.call" in node["captures"] else
                "lambda_expression" if "func.lambda" in node["captures"] else
                "other"
            )
        }
    }
}

KOTLIN_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    modifiers: [(public) (private) (protected) (internal) (override) (suspend) (inline) (tailrec)]* @syntax.function.modifier
                    name: (simple_identifier) @syntax.function.name
                    type_parameters: (type_parameters)? @syntax.function.type_params
                    value_parameters: (value_parameters)? @syntax.function.params
                    type: (type_reference)? @syntax.function.return_type
                    body: [(block) (expression)]? @syntax.function.body) @syntax.function.def,
                    
                (getter
                    modifiers: [(public) (private) (protected) (internal)]* @syntax.function.getter.modifier
                    body: [(block) (expression)]? @syntax.function.getter.body) @syntax.function.getter,
                    
                (setter
                    modifiers: [(public) (private) (protected) (internal)]* @syntax.function.setter.modifier
                    parameter: (parameter)? @syntax.function.setter.param
                    body: [(block) (expression)]? @syntax.function.setter.body) @syntax.function.setter
            ]
            """
        },
        "class": {
            "pattern": """
            (class_declaration
                modifiers: [(public) (private) (protected) (internal) (abstract) (final) (sealed) (inner) (data)]* @syntax.class.modifier
                name: (type_identifier) @syntax.class.name
                type_parameters: (type_parameters)? @syntax.class.type_params
                primary_constructor: (class_parameters)? @syntax.class.constructor
                delegation_specifiers: (delegation_specifiers)? @syntax.class.delegation
                body: (class_body)? @syntax.class.body) @syntax.class.def
            """
        },
        "interface": {
            "pattern": """
            (interface_declaration
                modifiers: [(public) (private) (protected) (internal)]* @syntax.interface.modifier
                name: (type_identifier) @syntax.interface.name
                type_parameters: (type_parameters)? @syntax.interface.type_params
                delegation_specifiers: (delegation_specifiers)? @syntax.interface.extends
                body: (class_body)? @syntax.interface.body) @syntax.interface.def
            """
        }
    },

    "semantics": {
        "type": {
            "pattern": """
            [
                (type_alias
                    modifiers: [(public) (private) (protected) (internal)]* @semantics.type.alias.modifier
                    name: (type_identifier) @semantics.type.alias.name
                    type_parameters: (type_parameters)? @semantics.type.alias.params
                    type: (type_reference) @semantics.type.alias.value) @semantics.type.alias,
                    
                (type_constraint
                    annotation: (annotation)* @semantics.type.constraint.annotation
                    type: (type_reference) @semantics.type.constraint.type) @semantics.type.constraint
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (kdoc
                    content: (_) @documentation.kdoc.content
                    tag: (kdoc_tag)* @documentation.kdoc.tag) @documentation.kdoc
            ]
            """
        }
    },

    "structure": {
        "package": {
            "pattern": """
            (package_header
                identifier: (identifier) @structure.package.name) @structure.package.def
            """
        },
        "import": {
            "pattern": """
            (import_header
                identifier: (identifier) @structure.import.path
                alias: (import_alias)? @structure.import.alias) @structure.import.def
            """
        }
    },
    
    "REPOSITORY_LEARNING": KOTLIN_PATTERNS_FOR_LEARNING
} 