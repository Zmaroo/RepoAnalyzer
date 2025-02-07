"""Elixir-specific Tree-sitter patterns."""

ELIXIR_PATTERNS = {
    # Function patterns
    "function": """
        [
          (stab_clause
            left: (arguments) @function.params
            operator: (_) @function.operator
            right: (body) @function.body) @function.def
        ]
    """,

    # Block patterns
    "block": """
        [
          (do_block
            (stab_clause)* @block.clauses) @block,
          (block
            (_)* @block.content) @block.def
        ]
    """,

    # String patterns
    "string": """
        [
          (string
            quoted_content: (_)? @string.content
            interpolation: (_)* @string.interpolation) @string,
          (charlist
            quoted_content: (_)? @charlist.content
            interpolation: (_)* @charlist.interpolation) @charlist
        ]
    """,

    # Map/Struct patterns
    "map": """
        [
          (map
            (pair
              key: (_) @map.key
              value: (_) @map.value)*) @map,
          (struct
            name: (_) @struct.name) @struct
        ]
    """,

    # List patterns
    "list": """
        [
          (list
            (_)* @list.elements) @list
        ]
    """,

    # Tuple patterns
    "tuple": """
        [
          (tuple
            (_)* @tuple.elements) @tuple
        ]
    """,

    # Operator patterns
    "operator": """
        [
          (binary_operator
            left: (_) @operator.left
            right: (_) @operator.right) @operator.binary,
          (unary_operator
            operand: (_) @operator.operand) @operator.unary,
          (operator_identifier) @operator.identifier
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (else_block
            (_)* @else.body) @else,
          (rescue_block
            (_)* @rescue.body) @rescue
        ]
    """,

    # Atom patterns
    "atom": """
        [
          (atom) @atom,
          (quoted_atom
            quoted_content: (_)? @atom.content
            interpolation: (_)* @atom.interpolation) @atom.quoted
        ]
    """,

    # Interpolation patterns
    "interpolation": """
        [
          (interpolation
            (_) @interpolation.expr) @interpolation
        ]
    """,

    # Value patterns
    "value": """
        [
          (integer) @value.integer,
          (float) @value.float,
          (boolean) @value.boolean,
          (nil) @value.nil,
          (char) @value.char
        ]
    """,

    # Identifier patterns
    "identifier": """
        [
          (identifier) @identifier,
          (alias) @identifier.alias
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 