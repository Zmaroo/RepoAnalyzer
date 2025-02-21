"""Purescript-specific Tree-sitter patterns.

These queries capture key constructs in Purescript:
  - Module declarations.
  - Value declarations (used for functions).
  - Data declarations.
  - Class declarations.
  
Adjust node names as needed to match your Purescript grammar.
"""

PURESCRIPT_PATTERNS = {
    "syntax": {
        "class": {
            "pattern": """
            [
                (class_declaration
                    name: (type_name) @syntax.class.name
                    type_vars: [(type_variable) (annotated_type_variable)]* @syntax.class.type_vars
                    constraints: (constraints)? @syntax.class.constraints
                    fundeps: (fundeps)? @syntax.class.fundeps
                    members: (class_member_list)? @syntax.class.members) @syntax.class.def,
                
                (class_instance
                    name: (instance_name)? @syntax.instance.name
                    head: (instance_head) @syntax.instance.head) @syntax.instance.def
            ]
            """
        },
        "function": {
            "pattern": """
            [
                (value_declaration
                    name: (identifier) @syntax.function.name
                    type: (type_signature)? @syntax.function.type
                    value: (expression) @syntax.function.body) @syntax.function.def,
                
                (function
                    name: (identifier) @syntax.function.name
                    params: [(identifier) (pattern)]* @syntax.function.params
                    guards: (guards)? @syntax.function.guards
                    body: (expression) @syntax.function.body) @syntax.function.def
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (data
                    name: (type) @syntax.type.data.name
                    vars: [(type_variable) (annotated_type_variable)]* @syntax.type.data.vars
                    constructors: (data_constructors)? @syntax.type.data.constructors) @syntax.type.data.def,
                
                (newtype
                    name: (type) @syntax.type.newtype.name
                    vars: [(type_variable) (annotated_type_variable)]* @syntax.type.newtype.vars
                    constructor: (newtype_constructor) @syntax.type.newtype.constructor) @syntax.type.newtype.def,
                
                (type_signature
                    name: (identifier) @syntax.type.sig.name
                    type: (type) @syntax.type.sig.value) @syntax.type.sig.def
            ]
            """
        }
    },
    "structure": {
        "module": {
            "pattern": """
            [
                (purescript
                    name: (qualified_module) @structure.module.name
                    exports: (exports)? @structure.module.exports) @structure.module.def,
                
                (import
                    module: (qualified_module) @structure.import.module
                    imports: (import_list)? @structure.import.list) @structure.import.def
            ]
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    }
}