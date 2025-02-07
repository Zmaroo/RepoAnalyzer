"""R-specific Tree-sitter patterns."""

R_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_definition
            parameters: (parameters) @function.params
            body: (_) @function.body) @function.def,
          (call
            function: (_) @function.name
            arguments: (arguments) @function.args) @function.call
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (_) @if.condition
            consequence: (_) @if.consequence
            alternative: (_)? @if.alternative) @if,
          (while_statement
            condition: (_) @while.condition
            body: (_) @while.body) @while,
          (for_statement
            variable: (_) @for.var
            iterator: (_) @for.iterator
            body: (_) @for.body) @for,
          (repeat_statement
            body: (_) @repeat.body) @repeat,
          (break) @break,
          (next) @next,
          (return) @return
        ]
    """,

    # Operator patterns
    "operator": """
        [
          (binary_operator
            operator: (_) @operator.binary.op
            lhs: (_) @operator.binary.left
            rhs: (_) @operator.binary.right) @operator.binary,
          (unary_operator
            operator: (_) @operator.unary.op
            operand: (_) @operator.unary.operand) @operator.unary
        ]
    """,

    # Assignment patterns
    "assignment": """
        [
          (binary_operator
            operator: ["<-" "=" "<<-" ":=" "->>" "->"] @assign.op
            lhs: (_) @assign.target
            rhs: (_) @assign.value) @assign
        ]
    """,

    # Subset/Extract patterns
    "subset": """
        [
          (subset
            function: (_) @subset.expr
            arguments: (arguments) @subset.args) @subset,
          (subset2
            function: (_) @subset2.expr
            arguments: (arguments) @subset2.args) @subset2,
          (extract_operator
            operator: (_) @extract.op
            lhs: (_) @extract.target
            rhs: (_) @extract.index) @extract
        ]
    """,

    # Namespace patterns
    "namespace": """
        [
          (namespace_operator
            package: (_) @namespace.package
            name: (_) @namespace.name) @namespace
        ]
    """,

    # Value patterns
    "value": """
        [
          (integer) @value.integer,
          (float) @value.float,
          (complex) @value.complex,
          (string) @value.string,
          (true) @value.true,
          (false) @value.false,
          (null) @value.null,
          (na) @value.na,
          (nan) @value.nan,
          (inf) @value.inf
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (parenthesized_expression
            body: (_) @expr.paren.body) @expr.paren,
          (braced_expression
            body: (_) @expr.brace.body) @expr.brace
        ]
    """,

    # Special syntax patterns
    "special": """
        [
          (dots) @special.dots,
          (dot_dot_i) @special.dot_dot_i
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 