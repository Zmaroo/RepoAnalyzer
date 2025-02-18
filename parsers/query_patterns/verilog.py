"""
Query patterns for Verilog files.
"""

VERILOG_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_declaration
                name: (identifier) @name
                ports: (port_list)? @ports
                body: (_) @body) @function
            """,
            """
            (task_declaration
                name: (identifier) @name
                ports: (port_list)? @ports
                body: (_) @body) @function
            """
        ],
        "class": [
            """
            (module_declaration
                name: (identifier) @name
                ports: (port_list)? @ports
                body: (_) @body) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (package_declaration
                name: (identifier) @name) @namespace
            """
        ],
        "import": [
            """
            (include_statement
                path: (string_literal) @path) @import
            """,
            """
            (import_declaration
                package: (identifier) @package) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (net_declaration
                type: (_) @type
                name: (identifier) @name) @variable
            """,
            """
            (reg_declaration
                name: (identifier) @name) @variable
            """
        ],
        "type": [
            """
            (parameter_declaration
                name: (identifier) @name
                value: (_) @value) @type
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 