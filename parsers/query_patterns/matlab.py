"""
Query patterns for MATLAB files.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

MATLAB_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (function_arguments)? @syntax.function.params
                    outputs: (function_output)? @syntax.function.returns
                    body: (block) @syntax.function.body) @syntax.function.def,
                    
                (lambda
                    parameters: (parameter_list)? @syntax.function.lambda.params
                    body: (_) @syntax.function.lambda.body) @syntax.function.lambda
            ]
            """
        },
        "class": {
            "pattern": """
            (class_definition
                name: (identifier) @syntax.class.name
                superclasses: (superclass_list)? @syntax.class.superclass
                body: (block
                    [(properties_block
                        attributes: (attributes)? @syntax.class.property.attrs
                        properties: (_)* @syntax.class.property.list) @syntax.class.properties
                     (methods_block
                        attributes: (attributes)? @syntax.class.method.attrs
                        methods: (_)* @syntax.class.method.list) @syntax.class.methods
                     (events_block
                        attributes: (attributes)? @syntax.class.event.attrs
                        events: (_)* @syntax.class.event.list) @syntax.class.events]*) @syntax.class.body) @syntax.class.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (assignment
                    left: [(identifier) @semantics.variable.name
                          (field_expression) @semantics.variable.field]
                    right: (_) @semantics.variable.value) @semantics.variable.def,
                (global_operator
                    variables: (identifier)* @semantics.variable.global.name) @semantics.variable.global,
                (persistent_operator
                    variables: (identifier)* @semantics.variable.persistent.name) @semantics.variable.persistent
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (function_call
                    name: (identifier) @semantics.type.check.name
                    (#match? @semantics.type.check.name "^(isa|class)$")
                    arguments: (arguments) @semantics.type.check.args) @semantics.type.check,
                (metaclass_operator
                    class: (identifier) @semantics.type.meta.name) @semantics.type.meta
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (comment) @documentation.help {
                    match: "^%[%\\s]"
                }
            ]
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            [
                (source_file) @structure.module,
                (function_file
                    function: (function_definition) @structure.module.function) @structure.module.file
            ]
            """
        },
        "import": {
            "pattern": """
            (import_statement
                path: (_) @structure.import.path) @structure.import.def
            """
        }
    }
} 