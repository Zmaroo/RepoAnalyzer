"""
Query patterns for Protocol Buffers files.
"""

PROTO_PATTERNS = {
    "syntax": {
        "class": {
            "pattern": """
            [
                (message
                    name: (message_name) @syntax.class.name
                    body: (message_body) @syntax.class.body) @syntax.class.def,
                (enum
                    name: (enum_name) @syntax.enum.name
                    body: (enum_body) @syntax.enum.body) @syntax.enum.def,
                (service
                    name: (service_name) @syntax.service.name
                    body: (_) @syntax.service.body) @syntax.service.def
            ]
            """
        },
        "function": {
            "pattern": """
            [
                (rpc
                    name: (rpc_name) @syntax.function.name
                    input_type: (message_or_enum_type) @syntax.function.input
                    output_type: (message_or_enum_type) @syntax.function.output
                    options: (option)* @syntax.function.options) @syntax.function.def
            ]
            """
        },
        "field": {
            "pattern": """
            [
                (field
                    type: (type) @syntax.field.type
                    name: (identifier) @syntax.field.name
                    number: (field_number) @syntax.field.number
                    options: (field_options)? @syntax.field.options) @syntax.field.def,
                (map_field
                    key_type: (key_type) @syntax.field.map.key_type
                    type: (type) @syntax.field.map.value_type
                    name: (identifier) @syntax.field.map.name
                    number: (field_number) @syntax.field.map.number) @syntax.field.map.def,
                (oneof
                    name: (identifier) @syntax.field.oneof.name
                    fields: (oneof_field)* @syntax.field.oneof.fields) @syntax.field.oneof.def
            ]
            """
        }
    },
    "structure": {
        "namespace": {
            "pattern": """
            [
                (package
                    name: (full_ident) @structure.namespace.name) @structure.namespace.def,
                (source_file
                    syntax: (syntax) @structure.file.syntax
                    edition: (edition)? @structure.file.edition) @structure.file
            ]
            """
        },
        "import": {
            "pattern": """
            (import
                path: (string) @structure.import.path) @structure.import.def
            """
        },
        "option": {
            "pattern": """
            (option
                name: [(full_ident) (identifier)] @structure.option.name
                value: (constant) @structure.option.value) @structure.option.def
            """
        }
    },
    "semantics": {
        "variable": [
            """
            (field
                name: (identifier) @name
                type: (_) @type
                number: (_) @number) @variable
            """
        ],
        "type": [
            """
            (message_type
                name: (identifier) @name) @type
            """
        ]
    },
    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    }
} 