"""Zig-specific Tree-sitter patterns."""

ZIG_PATTERNS = {
    # Function patterns
    "function": """
        [
          (FnProto
            name: (IDENTIFIER) @function.name
            params: (ParamDeclList) @function.params
            return_type: (_)? @function.return_type) @function.def,
          (FnCallArguments
            (_)* @function.args) @function.call
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (IfExpr
            condition: (_) @if.condition
            body: (_) @if.body
            alternative: (_)? @if.alternative) @if,
          (WhileExpr
            condition: (_) @while.condition
            body: (_) @while.body
            continue: (WhileContinueExpr)? @while.continue) @while,
          (ForExpr
            arguments: (ForArgumentsList) @for.args
            body: (_) @for.body) @for,
          (SwitchExpr
            condition: (_) @switch.condition
            cases: (SwitchProng)* @switch.cases) @switch
        ]
    """,

    # Variable/Constant patterns
    "variable": """
        [
          (VarDecl
            name: (IDENTIFIER) @var.name
            type: (_)? @var.type
            value: (_)? @var.value) @var.def,
          (Decl
            value: (_) @const.value) @const.def
        ]
    """,

    # Type patterns
    "type": """
        [
          (ErrorSetDecl
            fields: (IDENTIFIER)* @type.error.fields) @type.error,
          (ContainerField
            name: (IDENTIFIER) @type.field.name
            type: (_) @type.field.type) @type.field
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (BinaryExpr
            left: (_) @expr.binary.left
            right: (_) @expr.binary.right) @expr.binary,
          (UnaryExpr
            operand: (_) @expr.unary.operand) @expr.unary,
          (GroupedExpr
            (_) @expr.group.inner) @expr.group
        ]
    """,

    # Block patterns
    "block": """
        [
          (Block
            statements: (_)* @block.statements) @block,
          (BlockExpr
            label: (BlockLabel)? @block.label
            body: (_) @block.body) @block.expr
        ]
    """,

    # Assembly patterns
    "assembly": """
        [
          (AsmExpr
            inputs: (_)* @asm.inputs
            outputs: (_)* @asm.outputs
            clobbers: (AsmClobbers)? @asm.clobbers) @asm
        ]
    """,

    # Error handling patterns
    "error": """
        [
          (ErrorUnionExpr
            primary: (_) @error.primary
            exception: (_)? @error.exception) @error.union
        ]
    """,

    # Test patterns
    "test": """
        [
          (TestDecl
            name: (_) @test.name
            body: (_) @test.body) @test
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (doc_comment) @doc.comment,
          (line_comment) @doc.line,
          (container_doc_comment) @doc.container
        ]
    """,

    # Value patterns
    "value": """
        [
          (FLOAT) @value.float,
          (INTEGER) @value.integer,
          (STRINGLITERALSINGLE) @value.string,
          (LINESTRING) @value.line
        ]
    """
} 