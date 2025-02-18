"""Query patterns for Objective-C files."""

OBJECTIVEC_PATTERNS = {
    "syntax": {
        "function": [
            """
            (method_declaration
                receiver: (object)?
                selector: (selector) @name
                parameters: (parameter_list)? @params
                body: (compound_statement) @body) @function
            """
        ],
        "class": [
            """
            (class_interface
                name: (identifier) @name
                superclass: (superclass_reference)? @super
                protocols: (protocol_reference_list)? @protocols) @class
            """
        ]
    },
    "structure": {
        "import": [
            """
            (preproc_include
                path: (string_literal) @path) @import
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