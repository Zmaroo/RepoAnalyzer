"""Assembly-specific Tree-sitter patterns."""

ASM_PATTERNS = {
    # Instruction patterns
    "instruction": """
        [
          (instruction
            kind: (word) @instruction.name
            [
              (ident) @instruction.operand
              (int) @instruction.immediate
              (ptr) @instruction.pointer
              (reg) @instruction.register
              (string) @instruction.string
              (tc_infix) @instruction.expression
            ]*) @instruction.def
        ]
    """,

    # Label patterns
    "label": """
        [
          (label
            name: (word)? @label.name
            [
              (ident) @label.reference
              (meta_ident) @label.meta
            ]*) @label.def
        ]
    """,

    # Constant definition patterns
    "constant": """
        [
          (const
            name: (word) @const.name
            value: [
              (ident) @const.ident
              (int) @const.int
              (string) @const.string
              (tc_infix) @const.expr
            ]) @const.def
        ]
    """,

    # Register patterns
    "register": """
        [
          (reg
            [
              (word) @reg.name
              (address) @reg.addr
            ]?) @reg.def
        ]
    """,

    # Pointer patterns
    "pointer": """
        [
          (ptr
            [
              (ident) @ptr.base
              (int) @ptr.offset
              (reg) @ptr.register
            ]+) @ptr.def
        ]
    """,

    # Meta directive patterns
    "meta": """
        [
          (meta
            kind: (meta_ident) @meta.kind
            [
              (float) @meta.float
              (ident) @meta.ident
              (int) @meta.int
              (string) @meta.string
            ]*) @meta.def
        ]
    """,

    # Program structure
    "program": """
        [
          (program
            [
              (const) @program.const
              (instruction) @program.instruction
              (label) @program.label
              (meta) @program.meta
            ]*) @program.def
        ]
    """,

    # Comment patterns
    "comment": """
        [
          (line_comment) @comment.line
          (block_comment) @comment.block
        ]
    """
} 