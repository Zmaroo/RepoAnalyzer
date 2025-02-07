"""TOML-specific Tree-sitter patterns."""

TOML_PATTERNS = {
    # Document patterns
    "document": """
        [
          (document
            (pair)* @document.pairs
            (table)* @document.tables
            (table_array_element)* @document.table_arrays) @document
        ]
    """,

    # Table patterns
    "table": """
        [
          (table
            name: (bare_key) @table.name.bare
            name: (quoted_key) @table.name.quoted
            name: (dotted_key) @table.name.dotted
            (pair)* @table.pairs) @table,
          (table_array_element
            name: (bare_key) @table.array.name.bare
            name: (quoted_key) @table.array.name.quoted
            name: (dotted_key) @table.array.name.dotted
            (pair)* @table.array.pairs) @table.array
        ]
    """,

    # Key patterns
    "key": """
        [
          (bare_key) @key.bare,
          (quoted_key
            (escape_sequence)* @key.quoted.escape) @key.quoted,
          (dotted_key
            (bare_key)* @key.dotted.bare
            (quoted_key)* @key.dotted.quoted) @key.dotted
        ]
    """,

    # Value patterns
    "value": """
        [
          (string
            (escape_sequence)* @value.string.escape) @value.string,
          (integer) @value.integer,
          (float) @value.float,
          (boolean) @value.boolean,
          (array) @value.array,
          (inline_table) @value.inline_table,
          (local_date) @value.date,
          (local_time) @value.time,
          (local_date_time) @value.datetime,
          (offset_date_time) @value.datetime_offset
        ]
    """,

    # Array patterns
    "array": """
        [
          (array
            (_)* @array.items) @array
        ]
    """,

    # Table patterns (inline)
    "inline_table": """
        [
          (inline_table
            (pair)* @inline_table.pairs) @inline_table
        ]
    """,

    # Pair patterns
    "pair": """
        [
          (pair
            key: (_) @pair.key
            value: (_) @pair.value) @pair
        ]
    """,

    # Date/Time patterns
    "datetime": """
        [
          (local_date) @datetime.date,
          (local_time) @datetime.time,
          (local_date_time) @datetime.local,
          (offset_date_time) @datetime.offset
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 