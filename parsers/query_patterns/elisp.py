"""Query patterns for Emacs Lisp files."""

ELISP_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (symbol) @function.name
                parameters: (_)? @function.params
                docstring: (string)? @function.doc
                [
                    (bytecode) @function.bytecode
                    (list) @function.body
                    (special_form) @function.special
                ]*) @function.def
            """
        ],
        "class": [
            """
            (macro_definition
                name: (symbol) @macro.name
                parameters: (_)? @macro.params
                docstring: (string)? @macro.doc
                [
                    (list) @macro.body
                    (special_form) @macro.special
                ]*) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (source_file
                [
                    (function_definition) @source.function
                    (macro_definition) @source.macro
                    (special_form) @source.special
                    (list) @source.list
                    (comment) @source.comment
                ]*) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (list
                [
                    (symbol) @list.symbol
                    (string) @list.string
                    (integer) @list.integer
                    (float) @list.float
                    (char) @list.char
                    (list) @list.nested
                    (quote) @list.quote
                    (unquote) @list.unquote
                    (unquote_splice) @list.splice
                ]*) @variable
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