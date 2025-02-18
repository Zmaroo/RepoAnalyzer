"""Query patterns for Zig files."""

ZIG_PATTERNS = {
    "syntax": {
        "function": [
            """
            (FnProto
                name: (IDENTIFIER) @name
                params: (ParamDeclList) @params
                return_type: (_)? @return_type) @function
            """
        ],
        "class": [
            """
            (ContainerDecl
                name: (IDENTIFIER) @name
                members: (_)* @members) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (Block
                statements: (_)* @statements) @namespace
            """
        ],
        "import": [
            """
            (TopLevelDecl
                name: (IDENTIFIER) @name
                value: (_) @value) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (VarDecl
                name: (IDENTIFIER) @name
                type: (_)? @type
                value: (_)? @value) @variable
            """
        ],
        "type": [
            """
            (ErrorSetDecl
                fields: (IDENTIFIER)* @fields) @type
            """
        ]
    },
    "documentation": {
        "docstring": [
            """
            (container_doc_comment) @docstring
            """
        ],
        "comment": [
            """
            (doc_comment) @comment
            """,
            """
            (line_comment) @comment
            """
        ]
    }
} 