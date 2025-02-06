"""Go-specific Tree-sitter patterns."""

GO_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_declaration)
          (method_declaration)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
        (function_declaration
           name: (identifier) @function.name
            parameters: (parameter_list
              (parameter_declaration
                name: (identifier) @function.param.name
                type: (_) @function.param.type)*) @function.params
            result: (parameter_list)? @function.return_type
            body: (block) @function.body) @function.def,
          (method_declaration
            receiver: (parameter_list
              (parameter_declaration
                name: (identifier)? @function.receiver.name
                type: (_) @function.receiver.type)) @function.receiver
            name: (identifier) @function.name
            parameters: (parameter_list
              (parameter_declaration
                name: (identifier) @function.param.name
                type: (_) @function.param.type)*) @function.params
            result: (parameter_list)? @function.return_type
            body: (block) @function.body) @function.def
        ]
    """,
    # Type patterns
    "type": """
        [
          (type_declaration
            (type_spec
              name: (type_identifier) @type.name
              type: (_) @type.value)) @type.def,
          (type_identifier) @type.ref
        ]
    """,
    # Interface patterns
    "interface": """
        (interface_type
          (method_spec
            name: (identifier) @interface.method.name
            parameters: (parameter_list) @interface.method.params
            result: (parameter_list)? @interface.method.return_type)*) @interface
    """,
    # Struct patterns
    "struct": """
        (struct_type
          (field_declaration_list
            (field_declaration
              name: (field_identifier) @struct.field.name
              type: (_) @struct.field.type
              tag: (raw_string_literal)? @struct.field.tag)*)) @struct
    """,
    # Package patterns
    "package": """
        [
          (package_clause
            (package_identifier) @package.name) @package,
        (import_declaration
            (import_spec_list
              (import_spec
                name: (identifier)? @import.alias
                path: (interpreted_string_literal) @import.path)*)) @import
        ]
    """,
    # Variable declaration patterns
    "variable": """
        [
          (var_declaration
            (var_spec
              name: (identifier) @variable.name
              type: (_)? @variable.type
              value: (_)? @variable.value)) @variable.def,
        (short_var_declaration
            left: (expression_list
              (identifier) @variable.name)
            right: (expression_list
              (_) @variable.value)) @variable.short_def
        ]
    """,
    # Control flow patterns
    "control_flow": """
        [
        (if_statement
            condition: (_) @if.condition
            body: (block) @if.body
            else: (block)? @if.else) @if,
          (for_statement
            clause: (_)? @for.clause
            body: (block) @for.body) @for,
          (range_statement
            left: (_)? @range.vars
            right: (_) @range.expr
            body: (block) @range.body) @range
        ]
    """,
    # Channel operation patterns
    "channel": """
        [
          (channel_type) @channel.type,
          (send_statement
            channel: (_) @channel.name
            value: (_) @channel.value) @channel.send,
          (receive_statement
            left: (_) @channel.receiver
            right: (_) @channel.source) @channel.receive
        ]
    """,
    # Error handling patterns
    "error_handling": """
        [
          (defer_statement
            (_) @defer.expr) @defer,
          (go_statement
            (_) @go.expr) @go,
          (return_statement
            (_)* @return.values) @return
        ]
    """,
    "build_tags": """
        (comment
            text: (comment) @build.tag.text
            (#match? @build.tag.text "^//\\s*\\+build.*$")) @build.tag
    """,
    "generate": """
        (comment
            text: (comment) @generate.text
            (#match? @generate.text "^//go:generate.*$")) @generate
    """
} 