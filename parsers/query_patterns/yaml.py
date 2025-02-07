"""YAML-specific Tree-sitter patterns."""

YAML_PATTERNS = {
    # Document patterns
    "document": """
        [
          (stream
            (document) @document.content) @document
        ]
    """,

    # Mapping patterns
    "mapping": """
        [
          (block_mapping_pair
            key: (_) @mapping.key
            value: (_) @mapping.value) @mapping.block,
          (flow_mapping
            (flow_pair
              key: (_) @mapping.flow.key
              value: (_) @mapping.flow.value)*) @mapping.flow
        ]
    """,

    # Sequence patterns
    "sequence": """
        [
          (block_sequence
            (block_sequence_item
              (_) @sequence.item)*) @sequence.block,
          (flow_sequence
            (_)* @sequence.flow.items) @sequence.flow
        ]
    """,

    # Value patterns
    "value": """
        [
          (string_scalar) @value.string,
          (double_quote_scalar) @value.string.double,
          (single_quote_scalar) @value.string.single,
          (block_scalar) @value.block,
          (integer_scalar) @value.integer,
          (float_scalar) @value.float,
          (boolean_scalar) @value.boolean,
          (null_scalar) @value.null,
          (timestamp_scalar) @value.timestamp
        ]
    """,

    # Anchor/Alias patterns
    "reference": """
        [
          (anchor
            name: (anchor_name) @anchor.name) @anchor,
          (alias
            name: (alias_name) @alias.name) @alias
        ]
    """,

    # Tag patterns
    "tag": """
        [
          (tag
            handle: (_)? @tag.handle
            suffix: (_) @tag.suffix) @tag
        ]
    """,

    # Directive patterns
    "directive": """
        [
          (directive
            name: (_) @directive.name
            value: (_)? @directive.value) @directive
        ]
    """,

    # Comment patterns
    "comment": """
        [
          (comment) @comment
        ]
    """,

    # Error patterns
    "error": """
        [
          (ERROR) @error
        ]
    """
} 