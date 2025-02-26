"""Query patterns for Swift files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

SWIFT_PATTERNS_FOR_LEARNING = {
    "protocol_oriented": {
        "pattern": """
        [
            (protocol_declaration
                name: (type_identifier) @protocol.name
                inheritance_clause: (inheritance_clause
                    (type_identifier)+ @protocol.parent)? @protocol.inheritance
                body: (declaration_block
                    [(function_declaration) (variable_declaration) (property_declaration) (typealias_declaration)]+ @protocol.requirements) @protocol.body) @protocol.def,
                
            (extension_declaration
                name: (type_identifier) @extension.type
                inheritance_clause: (inheritance_clause
                    (type_identifier)+ @extension.protocols)? @extension.inheritance
                body: (declaration_block) @extension.body) @extension.def {
                filter: { @extension.protocols is not null }
            },
                
            (struct_declaration
                name: (type_identifier) @struct.name
                inheritance_clause: (inheritance_clause
                    (type_identifier)+ @struct.protocols)? @struct.inheritance
                body: (declaration_block)? @struct.body) @struct.def {
                filter: { @struct.protocols is not null }
            },
                
            (class_declaration
                name: (type_identifier) @class.name
                inheritance_clause: (inheritance_clause
                    (type_identifier)+ @class.protocols)? @class.inheritance
                body: (declaration_block)? @class.body) @class.def {
                filter: { @class.protocols is not null }
            }
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "protocol_oriented",
            "is_protocol": "protocol.def" in node["captures"],
            "is_extension": "extension.def" in node["captures"],
            "is_struct": "struct.def" in node["captures"],
            "is_class": "class.def" in node["captures"],
            "name": (
                node["captures"].get("protocol.name", {}).get("text", "") or
                node["captures"].get("extension.type", {}).get("text", "") or
                node["captures"].get("struct.name", {}).get("text", "") or
                node["captures"].get("class.name", {}).get("text", "")
            ),
            "conforms_to": [p.get("text", "") for p in (
                node["captures"].get("protocol.parent", []) or
                node["captures"].get("extension.protocols", []) or
                node["captures"].get("struct.protocols", []) or
                node["captures"].get("class.protocols", [])
            )],
            "pattern_kind": (
                "protocol_definition" if "protocol.def" in node["captures"] else
                "protocol_extension" if "extension.def" in node["captures"] else
                "protocol_conforming_struct" if "struct.def" in node["captures"] else
                "protocol_conforming_class" if "class.def" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "functional_patterns": {
        "pattern": """
        [
            (closure_expression
                parameters: (closure_parameter_clause
                    (closure_parameter
                        name: (identifier) @func.closure.param.name
                        type: (type_annotation)? @func.closure.param.type)* @func.closure.params)? @func.closure.param_clause
                throws: (_)? @func.closure.throws
                result: (return_type)? @func.closure.return
                body: (statement_block) @func.closure.body) @func.closure,
                
            (function_call
                function: [(identifier) @func.call.name (member_expression)]
                trailing_closure: (closure_expression)? @func.call.trailing
                arguments: (tuple_expression
                    (argument
                        label: (_)? @func.call.arg.label
                        value: (_) @func.call.arg.value)* @func.call.args)? @func.call.tuple) @func.call,
                
            (variable_declaration
                pattern: (identifier_pattern) @func.var.name
                type: (type_annotation)? @func.var.type
                value: (lambda_literal
                    body: (statement_block) @func.lambda.body)? @func.lambda
                ) @func.var.decl {
                filter: { @func.lambda is not null }
            },
                
            (for_in_statement
                pattern: (identifier_pattern) @func.iter.item
                expression: [(array_literal) (range_expression) (function_call) (member_expression)] @func.iter.collection
                body: (statement_block) @func.iter.body) @func.iter
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional_patterns",
            "is_closure": "func.closure" in node["captures"],
            "is_function_call": "func.call" in node["captures"],
            "is_lambda": "func.lambda" in node["captures"],
            "is_iteration": "func.iter" in node["captures"],
            "function_name": node["captures"].get("func.call.name", {}).get("text", ""),
            "has_trailing_closure": "func.call.trailing" in node["captures"] and node["captures"].get("func.call.trailing", {}).get("text", "") != "",
            "arg_count": len([arg for arg in node["captures"].get("func.call.args", [])]) if "func.call.args" in node["captures"] else 0,
            "iteration_item": node["captures"].get("func.iter.item", {}).get("text", ""),
            "pattern_kind": (
                "closure" if "func.closure" in node["captures"] else
                "function_call" if "func.call" in node["captures"] else
                "lambda" if "func.lambda" in node["captures"] else
                "iteration" if "func.iter" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "type_safety": {
        "pattern": """
        [
            (optional_type
                type: (_) @type.optional.inner) @type.optional,
                
            (if_statement
                condition: (optional_binding_condition
                    name: (identifier) @type.binding.name
                    value: (_) @type.binding.value) @type.binding
                body: (statement_block) @type.binding.body) @type.binding.if,
                
            (guard_statement
                condition: (optional_binding_condition
                    name: (identifier) @type.guard.name
                    value: (_) @type.guard.value) @type.guard
                body: (statement_block) @type.guard.body) @type.guard.stmt,
                
            (force_unwrap_expression
                expression: (_) @type.force.expr) @type.force,
                
            (optional_chaining_expression
                expression: (_) @type.chain.expr) @type.chain,
                
            (as_expression
                expression: (_) @type.cast.expr
                type: (_) @type.cast.type) @type.cast {
                filter: { @type.cast.text =~ "as\\?" }
            },
                
            (switch_statement
                expression: (_) @type.switch.expr
                body: (switch_body
                    (case) @type.switch.case+) @type.switch.cases) @type.switch
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "type_safety",
            "is_optional_type": "type.optional" in node["captures"],
            "is_optional_binding": "type.binding" in node["captures"],
            "is_guard": "type.guard" in node["captures"],
            "is_force_unwrap": "type.force" in node["captures"],
            "is_optional_chaining": "type.chain" in node["captures"],
            "is_type_cast": "type.cast" in node["captures"],
            "is_switch": "type.switch" in node["captures"],
            "bound_name": node["captures"].get("type.binding.name", {}).get("text", "") or node["captures"].get("type.guard.name", {}).get("text", ""),
            "inner_type": node["captures"].get("type.optional.inner", {}).get("text", ""),
            "cast_type": node["captures"].get("type.cast.type", {}).get("text", ""),
            "num_cases": len([case for case in node["captures"].get("type.switch.case", [])]) if "type.switch.cases" in node["captures"] else 0,
            "pattern_kind": (
                "optional_type" if "type.optional" in node["captures"] else
                "optional_binding" if "type.binding" in node["captures"] else
                "guard_let" if "type.guard" in node["captures"] else
                "force_unwrap" if "type.force" in node["captures"] else
                "optional_chaining" if "type.chain" in node["captures"] else
                "type_cast" if "type.cast" in node["captures"] else
                "switch_pattern" if "type.switch" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "concurrency": {
        "pattern": """
        [
            (function_declaration
                modifier: [(attribute) (simple_identifier)] @concurrency.func.modifier {
                    match: "^(async|@MainActor)$"
                }
                name: (simple_identifier) @concurrency.func.name
                parameters: (parameter_clause) @concurrency.func.params
                result: (return_type
                    type: (_) @concurrency.func.return)? @concurrency.func.result
                body: (statement_block) @concurrency.func.body) @concurrency.func,
                
            (await_expression
                expression: (_) @concurrency.await.expr) @concurrency.await,
                
            (function_call
                function: (simple_identifier) @concurrency.task.func {
                    match: "^(Task|detach)$"
                }
                trailing_closure: (closure_expression) @concurrency.task.closure) @concurrency.task,
                
            (actor_declaration
                name: (type_identifier) @concurrency.actor.name
                body: (declaration_block) @concurrency.actor.body) @concurrency.actor
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "concurrency",
            "is_async_function": "concurrency.func" in node["captures"] and "async" in node["captures"].get("concurrency.func.modifier", {}).get("text", ""),
            "is_main_actor": "concurrency.func" in node["captures"] and "@MainActor" in node["captures"].get("concurrency.func.modifier", {}).get("text", ""),
            "is_await": "concurrency.await" in node["captures"],
            "is_task": "concurrency.task" in node["captures"],
            "is_actor": "concurrency.actor" in node["captures"],
            "function_name": node["captures"].get("concurrency.func.name", {}).get("text", ""),
            "task_type": node["captures"].get("concurrency.task.func", {}).get("text", ""),
            "actor_name": node["captures"].get("concurrency.actor.name", {}).get("text", ""),
            "pattern_kind": (
                "async_function" if "concurrency.func" in node["captures"] and "async" in node["captures"].get("concurrency.func.modifier", {}).get("text", "") else
                "main_actor_function" if "concurrency.func" in node["captures"] and "@MainActor" in node["captures"].get("concurrency.func.modifier", {}).get("text", "") else
                "await_expression" if "concurrency.await" in node["captures"] else
                "task_creation" if "concurrency.task" in node["captures"] else
                "actor_definition" if "concurrency.actor" in node["captures"] else
                "unknown"
            )
        }
    }
}

SWIFT_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: (simple_identifier) @syntax.function.name
                    parameters: (parameter_clause
                        (parameter
                            name: (simple_identifier) @syntax.function.param.name
                            type: (type_annotation) @syntax.function.param.type
                            default_value: (_)? @syntax.function.param.default)* @syntax.function.params)
                    result: (return_type)? @syntax.function.return
                    body: (statement_block) @syntax.function.body) @syntax.function.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "params": [p.get("text", "") for p in node["captures"].get("syntax.function.param.name", [])],
                "has_return": "syntax.function.return" in node["captures"] and node["captures"].get("syntax.function.return", {}).get("text", "") != ""
            }
        },
        
        "class": {
            "pattern": """
            [
                (class_declaration
                    name: (type_identifier) @syntax.class.name
                    inheritance_clause: (inheritance_clause)? @syntax.class.inheritance
                    body: (declaration_block
                        [(variable_declaration) (property_declaration) (function_declaration) (initializer_declaration)]* @syntax.class.members) @syntax.class.body) @syntax.class.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                "has_inheritance": "syntax.class.inheritance" in node["captures"] and node["captures"].get("syntax.class.inheritance", {}).get("text", "") != ""
            }
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_declaration
                    (pattern_binding
                        pattern: (identifier_pattern) @semantics.variable.name
                        type: (type_annotation)? @semantics.variable.type
                        value: (_)? @semantics.variable.value)+ @semantics.variable.bindings) @semantics.variable.decl,
                
                (property_declaration
                    (pattern_binding
                        pattern: (identifier_pattern) @semantics.property.name
                        type: (type_annotation)? @semantics.property.type
                        value: (_)? @semantics.property.value)+ @semantics.property.bindings) @semantics.property.decl
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.variable.name", {}).get("text", "") or
                       node["captures"].get("semantics.property.name", {}).get("text", ""),
                "type": (node["captures"].get("semantics.variable.type", {}).get("text", "") or
                        node["captures"].get("semantics.property.type", {}).get("text", "")).strip(": ")
            }
        }
    },
    
    "structure": {
        "enum": {
            "pattern": """
            [
                (enum_declaration
                    name: (type_identifier) @structure.enum.name
                    inheritance_clause: (inheritance_clause)? @structure.enum.inheritance
                    body: (declaration_block
                        (enum_case_clause
                            (enum_case
                                name: (simple_identifier) @structure.enum.case.name
                                associated_value: (tuple_type)? @structure.enum.case.value)* @structure.enum.cases)+ @structure.enum.case_clauses) @structure.enum.body) @structure.enum.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("structure.enum.name", {}).get("text", ""),
                "cases": [case.get("text", "") for case in node["captures"].get("structure.enum.case.name", [])]
            }
        }
    },
    
    "documentation": {
        "comment": {
            "pattern": """
            [
                (line_comment) @documentation.line,
                (multiline_comment) @documentation.block,
                (documentation_comment) @documentation.doc
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.line", {}).get("text", "") or
                       node["captures"].get("documentation.block", {}).get("text", "") or
                       node["captures"].get("documentation.doc", {}).get("text", "")
            }
        }
    },
    
    "REPOSITORY_LEARNING": SWIFT_PATTERNS_FOR_LEARNING
} 