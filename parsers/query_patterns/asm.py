"""Query patterns for Assembly files."""

ASM_PATTERNS = {
    "syntax": {
        "function": [
            """
            (instruction
                kind: (word) @name
                [
                    (ident) @operand
                    (int) @immediate
                    (ptr) @pointer
                    (reg) @register
                    (string) @string
                    (tc_infix) @expression
                ]*) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (program
                [
                    (const) @program.const
                    (instruction) @program.instruction
                    (label) @program.label
                    (meta) @program.meta
                ]*) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (const
                name: (word) @name
                value: [
                    (ident) @const.ident
                    (int) @const.int
                    (string) @const.string
                    (tc_infix) @const.expr
                ]) @variable
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            (line_comment) @comment
            """,
            """
            (block_comment) @comment
            """
        ]
    }
} 