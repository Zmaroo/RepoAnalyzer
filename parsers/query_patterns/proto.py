"""Protocol Buffers-specific Tree-sitter patterns."""

PROTO_PATTERNS = {
    # File-level patterns
    "file": """
        [
          (source_file
            (syntax)? @file.syntax
            (package)? @file.package
            (import)* @file.imports
            (_)* @file.content) @file
        ]
    """,

    # Package patterns
    "package": """
        [
          (package
            (full_ident) @package.name) @package
        ]
    """,

    # Import patterns
    "import": """
        [
          (import
            path: (string) @import.path) @import
        ]
    """,

    # Message patterns
    "message": """
        [
          (message
            name: (message_name) @message.name
            body: (message_body
              (field)* @message.fields
              (enum)* @message.enums
              (message)* @message.nested
              (option)* @message.options)?) @message
        ]
    """,

    # Field patterns
    "field": """
        [
          (field
            type: (type) @field.type
            name: (identifier) @field.name
            number: (field_number) @field.number
            options: (field_options)? @field.options) @field,
          (map_field
            key_type: (key_type) @field.map.key_type
            type: (type) @field.map.value_type
            name: (identifier) @field.map.name
            number: (field_number) @field.map.number) @field.map
        ]
    """,

    # Enum patterns
    "enum": """
        [
          (enum
            name: (enum_name) @enum.name
            body: (enum_body
              (enum_field)* @enum.fields
              (option)* @enum.options)?) @enum
        ]
    """,

    # Service patterns
    "service": """
        [
          (service
            name: (service_name) @service.name
            (option)* @service.options
            (rpc)* @service.rpcs) @service
        ]
    """,

    # RPC patterns
    "rpc": """
        [
          (rpc
            name: (rpc_name) @rpc.name
            request_type: (message_or_enum_type) @rpc.request
            response_type: (message_or_enum_type) @rpc.response
            (option)* @rpc.options) @rpc
        ]
    """,

    # Option patterns
    "option": """
        [
          (option
            name: (_) @option.name
            value: (constant) @option.value) @option
        ]
    """,

    # Extension patterns
    "extension": """
        [
          (extend
            target: (full_ident) @extend.target
            body: (message_body) @extend.body) @extend
        ]
    """,

    # Reserved patterns
    "reserved": """
        [
          (reserved
            (ranges) @reserved.ranges) @reserved.numbers,
          (reserved
            (reserved_field_names) @reserved.names) @reserved.fields
        ]
    """,

    # Value patterns
    "value": """
        [
          (int_lit) @value.int,
          (float_lit) @value.float,
          (string) @value.string,
          (bool) @value.bool,
          (constant) @value.constant
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 