"""Query patterns for Starlark files."""

from .common import COMMON_PATTERNS

STARLARK_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (parameters
                        [(parameter
                            name: (identifier) @syntax.function.param.name
                            default: (_)? @syntax.function.param.default)
                         (typed_parameter
                            name: (identifier) @syntax.function.param.typed.name
                            type: (_) @syntax.function.param.typed.type)
                         (typed_default_parameter
                            name: (identifier) @syntax.function.param.typed_default.name
                            type: (_) @syntax.function.param.typed_default.type
                            default: (_) @syntax.function.param.typed_default.value)]*) @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def,
                
                (lambda
                    parameters: (lambda_parameters
                        (parameter
                            name: (identifier) @syntax.function.lambda.param.name)*)? @syntax.function.lambda.params
                    body: (expression) @syntax.function.lambda.body) @syntax.function.lambda
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "parameters": [p.get("text", "") for p in node["captures"].get("syntax.function.param.name", [])]
            }
        }
    },
    
    "structure": {
        "module": {
            "pattern": """
            [
                (import_statement
                    name: (dotted_name) @structure.import.module) @structure.import,
                
                (import_from_statement
                    module_name: (dotted_name) @structure.import.from.module
                    name: (dotted_name) @structure.import.from.name) @structure.import.from,
                
                (expression_statement
                    (assignment
                        left: (identifier) @structure.module.attr.name
                        right: (_) @structure.module.attr.value)) @structure.module.attr
            ]
            """,
            "extract": lambda node: {
                "module": node["captures"].get("structure.import.module", {}).get("text", "") or
                         node["captures"].get("structure.import.from.module", {}).get("text", ""),
                "name": node["captures"].get("structure.import.from.name", {}).get("text", "")
            }
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (assignment
                    left: [(identifier) @semantics.variable.name
                          (list_pattern) @semantics.variable.list_pattern
                          (tuple_pattern) @semantics.variable.tuple_pattern
                          (dict_pattern) @semantics.variable.dict_pattern]
                    right: (_) @semantics.variable.value) @semantics.variable.assignment,
                
                (for_statement
                    left: [(identifier) @semantics.variable.loop.name
                          (pattern) @semantics.variable.loop.pattern]
                    right: (_) @semantics.variable.loop.iterable) @semantics.variable.loop
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                "value": node["captures"].get("semantics.variable.value", {}).get("text", "")
            }
        }
    },
    
    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "")
            }
        }
    }
} 