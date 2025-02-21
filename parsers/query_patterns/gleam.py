"""Query patterns for Gleam files."""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

GLEAM_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (function_parameters) @syntax.function.params
                    return_type: (_)? @syntax.function.return_type
                    body: (function_body) @syntax.function.body) @syntax.function.def,
                (anonymous_function
                    parameters: (function_parameters) @syntax.function.anon.params
                    return_type: (_)? @syntax.function.anon.return_type
                    body: (function_body) @syntax.function.anon.body) @syntax.function.anon
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_definition
                    name: (type_name) @syntax.type.name
                    parameters: (type_parameters)? @syntax.type.params
                    constructors: (data_constructors)? @syntax.type.constructors) @syntax.type.def,
                (type_alias
                    name: (type_name) @syntax.type.alias.name
                    parameters: (type_parameters)? @syntax.type.alias.params
                    value: (_) @syntax.type.alias.value) @syntax.type.alias.def
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            (let
                pattern: (_) @semantics.variable.pattern
                type: (_)? @semantics.variable.type
                value: (_) @semantics.variable.value) @semantics.variable.def
            """
        },
        "expression": {
            "pattern": """
            [
                (function_call
                    function: (_) @semantics.expression.name
                    arguments: (_)? @semantics.expression.args) @semantics.expression.call,
                (case
                    subject: (_) @semantics.expression.case.subject
                    clauses: (_) @semantics.expression.case.clauses) @semantics.expression.case
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (module_comment) @documentation.comment.module,
                (statement_comment) @documentation.comment.statement
            ]
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            (source_file
                imports: (import)* @structure.module.imports
                definitions: (_)* @structure.module.definitions) @structure.module.def
            """
        },
        "import": {
            "pattern": """
            (import
                module: (_) @structure.import.module
                unqualified: (unqualified_imports)? @structure.import.unqualified) @structure.import.def
            """
        }
    }
} 