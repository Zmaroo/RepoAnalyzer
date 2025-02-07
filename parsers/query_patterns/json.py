"""JSON-specific Tree-sitter patterns."""

JSON_PATTERNS = {
    # Document pattern
    "document": """
        (document
          (_)* @document.content) @document
    """,

    # Object patterns
    "object": """
        [
          (object
            (pair
              key: (string) @object.key
              value: (_) @object.value)*) @object
        ]
    """,

    # Array patterns
    "array": """
        [
          (array
            (_)* @array.elements) @array
        ]
    """,

    # Value patterns
    "value": """
        [
          (string) @value.string,
          (number) @value.number,
          (true) @value.true,
          (false) @value.false,
          (null) @value.null
        ]
    """,

    # String patterns
    "string": """
        [
          (string
            (string_content)? @string.content
            (escape_sequence)* @string.escape) @string
        ]
    """,

    # Pair patterns
    "pair": """
        [
          (pair
            key: (string) @pair.key
            value: (_) @pair.value) @pair
        ]
    """
} 