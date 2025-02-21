"""Query patterns for QML/JS files."""

QMLJS_PATTERNS = {
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (formal_parameters) @syntax.function.params
                    body: (statement_block) @syntax.function.body) @syntax.function.def,
                
                (generator_function_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (formal_parameters) @syntax.function.params
                    body: (statement_block) @syntax.function.body) @syntax.function.generator.def
            ]
            """
        },
        "class": {
            "pattern": """
            [
                (ui_object_definition
                    type_name: (identifier) @syntax.class.name
                    members: (ui_object_initializer
                        (_ui_object_member)* @syntax.class.members)) @syntax.class.def,
                
                (enum_declaration
                    name: (identifier) @syntax.enum.name
                    body: (_)* @syntax.enum.body) @syntax.enum.def
            ]
            """
        }
    },
    "structure": {
        "import": {
            "pattern": """
            [
                (ui_import
                    source: (string) @structure.import.source
                    version: (ui_version_specifier)? @structure.import.version) @structure.import.def,
                
                (import_statement
                    source: (string) @structure.import.source
                    clause: (import_clause)? @structure.import.clause) @structure.import.js.def
            ]
            """
        },
        "property": {
            "pattern": """
            [
                (ui_property
                    name: (identifier) @structure.property.name
                    type: (_)? @structure.property.type
                    value: (_)? @structure.property.value) @structure.property.def,
                
                (ui_binding
                    name: [(identifier) (nested_identifier)] @structure.binding.name
                    value: (_) @structure.binding.value) @structure.binding.def
            ]
            """
        }
    },
    "semantics": {
        "signal": {
            "pattern": """
            (ui_signal
                name: (identifier) @semantics.signal.name
                parameters: (formal_parameters)? @semantics.signal.params) @semantics.signal.def
            """
        },
        "variable": {
            "pattern": """
            [
                (variable_declaration
                    name: (identifier) @semantics.variable.name
                    type: (type_annotation)? @semantics.variable.type
                    value: (_)? @semantics.variable.value) @semantics.variable.def,
                
                (lexical_declaration
                    kind: ["const" "let"] @semantics.variable.kind
                    declarator: (variable_declarator) @semantics.variable.declarator) @semantics.variable.def
            ]
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (ui_pragma) @documentation.pragma
            ]
            """
        }
    }
} 