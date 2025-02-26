"""Query patterns for Squirrel files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

SQUIRREL_PATTERNS_FOR_LEARNING = {
    "functional_patterns": {
        "pattern": """
        [
            (function_expression
                parameters: (parameter_list) @function.params
                body: (block) @function.body) @function.anonymous,
                
            (lambda
                parameters: (parameter_list) @function.lambda.params
                body: (_) @function.lambda.body) @function.lambda,
                
            (call_expression
                function: [(identifier) @function.call.name (member_expression)] @function.call.func
                arguments: (argument_list) @function.call.args) @function.call,
                
            (method
                name: (identifier) @function.method.name
                parameters: (parameter_list) @function.method.params
                body: (block) @function.method.body) @function.method
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional_patterns",
            "node_type": (
                "anonymous_function" if "function.anonymous" in node["captures"] else
                "lambda" if "function.lambda" in node["captures"] else
                "function_call" if "function.call" in node["captures"] else
                "method" if "function.method" in node["captures"] else
                "unknown"
            ),
            "function_name": node["captures"].get("function.call.name", {}).get("text", "") or
                            node["captures"].get("function.method.name", {}).get("text", ""),
            "has_parameters": (
                "function.params" in node["captures"] or
                "function.lambda.params" in node["captures"] or
                "function.method.params" in node["captures"]
            ),
            "num_arguments": len([arg for arg in node["captures"].get("function.call.args", {}).get("children", [])
                                if arg.get("type") not in ["(", ")", ","]])
                             if "function.call.args" in node["captures"] else 0
        }
    },
    
    "oop_patterns": {
        "pattern": """
        [
            (class_definition
                name: (identifier) @class.name
                extends_clause: (extends_clause
                    class: (_) @class.parent)? @class.extends
                body: (class_body) @class.body) @class.def,
                
            (class_body
                [(method
                    name: (identifier) @class.method.name
                    parameters: (parameter_list) @class.method.params
                    body: (block) @class.method.body) @class.method
                 (property
                    name: (identifier) @class.property.name
                    value: (_) @class.property.value) @class.property]+) @class.methods_props,
                
            (new_expression
                class: (_) @instance.class
                arguments: (argument_list) @instance.args) @instance.creation,
                
            (member_expression
                object: (_) @member.object
                property: (identifier) @member.property) @member.access
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "oop_patterns",
            "node_type": (
                "class_definition" if "class.def" in node["captures"] else
                "class_body" if "class.methods_props" in node["captures"] else
                "object_instantiation" if "instance.creation" in node["captures"] else
                "member_access" if "member.access" in node["captures"] else
                "unknown"
            ),
            "class_name": node["captures"].get("class.name", {}).get("text", ""),
            "parent_class": node["captures"].get("class.parent", {}).get("text", ""),
            "method_name": node["captures"].get("class.method.name", {}).get("text", ""),
            "property_name": node["captures"].get("class.property.name", {}).get("text", "") or
                            node["captures"].get("member.property", {}).get("text", ""),
            "has_inheritance": "class.extends" in node["captures"] and node["captures"].get("class.parent", {}).get("text", "") != ""
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (try_statement
                body: (block) @error.try.body
                catch_clauses: [(catch_clause
                    parameter: (parameter) @error.catch.param
                    body: (block) @error.catch.body) @error.catch]+
                finally_clause: (finally_clause
                    body: (block) @error.finally.body)? @error.finally) @error.try,
                
            (throw_statement
                expression: (_) @error.throw.expr) @error.throw,
                
            (conditional_expression
                condition: (_) @error.check.cond
                consequence: (_) @error.check.then
                alternative: (_) @error.check.else) @error.check
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "error_handling",
            "node_type": (
                "try_catch" if "error.try" in node["captures"] else
                "throw" if "error.throw" in node["captures"] else
                "conditional_check" if "error.check" in node["captures"] else
                "unknown"
            ),
            "has_catch": "error.catch" in node["captures"],
            "has_finally": "error.finally" in node["captures"] and node["captures"].get("error.finally.body", {}).get("text", "") != "",
            "exception_type": node["captures"].get("error.catch.param", {}).get("text", ""),
            "thrown_expression": node["captures"].get("error.throw.expr", {}).get("text", "")
        }
    },
    
    "data_structures": {
        "pattern": """
        [
            (array
                elements: [(number) (string) (identifier) (_)]* @data.array.elements) @data.array,
                
            (table
                entries: [(pair
                    key: (_) @data.table.entry.key
                    value: (_) @data.table.entry.value) @data.table.entry]* @data.table.entries) @data.table,
                
            (pair
                key: (_) @data.pair.key
                value: (_) @data.pair.value) @data.pair,
                
            (clone_expression
                expression: (_) @data.clone.expr) @data.clone
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "data_structures",
            "node_type": (
                "array" if "data.array" in node["captures"] else
                "table" if "data.table" in node["captures"] else
                "pair" if "data.pair" in node["captures"] else
                "clone" if "data.clone" in node["captures"] else
                "unknown"
            ),
            "array_size": len([el for el in node["captures"].get("data.array.elements", [])]) if "data.array" in node["captures"] else 0,
            "table_size": len([entry for entry in node["captures"].get("data.table.entry", [])]) if "data.table" in node["captures"] else 0,
            "key_type": node["captures"].get("data.pair.key", {}).get("type", "") if "data.pair" in node["captures"] else "",
            "value_type": node["captures"].get("data.pair.value", {}).get("type", "") if "data.pair" in node["captures"] else ""
        }
    }
}

SQUIRREL_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list
                        [(parameter
                            name: (identifier) @syntax.function.param.name
                            default_value: (_)? @syntax.function.param.default)]*) @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "params": [p.get("text", "") for p in node["captures"].get("syntax.function.param.name", [])],
                "body": node["captures"].get("syntax.function.body", {}).get("text", ""),
            }
        },
        
        "variable": {
            "pattern": """
            [
                (local_declaration
                    name: (identifier) @syntax.variable.name
                    value: (_)? @syntax.variable.value) @syntax.variable.decl,
                
                (assignment_expression
                    left: [(identifier) @syntax.variable.assign.name (member_expression)]
                    right: (_) @syntax.variable.assign.value) @syntax.variable.assign
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.variable.name", {}).get("text", "") or
                       node["captures"].get("syntax.variable.assign.name", {}).get("text", ""),
                "type": "declaration" if "syntax.variable.decl" in node["captures"] else "assignment"
            }
        }
    },
    
    "semantics": {
        "class": {
            "pattern": """
            [
                (class_definition
                    name: (identifier) @semantics.class.name
                    extends_clause: (extends_clause
                        class: (_) @semantics.class.parent)? @semantics.class.extends
                    body: (class_body) @semantics.class.body) @semantics.class.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.class.name", {}).get("text", ""),
                "parent": node["captures"].get("semantics.class.parent", {}).get("text", "")
            }
        }
    },
    
    "structure": {
        "import": {
            "pattern": """
            [
                (import_statement
                    path: (string) @structure.import.path) @structure.import
            ]
            """,
            "extract": lambda node: {
                "path": node["captures"].get("structure.import.path", {}).get("text", "")
            }
        }
    },
    
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (multiline_comment) @documentation.multiline
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "") or
                       node["captures"].get("documentation.multiline", {}).get("text", "")
            }
        }
    },
    
    "REPOSITORY_LEARNING": SQUIRREL_PATTERNS_FOR_LEARNING
} 