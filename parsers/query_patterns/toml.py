"""
Query patterns for TOML files with enhanced documentation support.
"""

TOML_PATTERNS = {
    "syntax": {
        "table": """
            (table
                path: (_) @syntax.table.path
                keys: (_)* @syntax.table.keys) @syntax.table
        """,
        "array": """
            (array
                path: (_) @syntax.array.path
                length: (_) @syntax.array.length) @syntax.array
        """,
        "value": """
            (value
                path: (_) @syntax.value.path
                value_type: (_) @syntax.value.type) @syntax.value
        """,
        "inline": """
            [
                (inline_table
                    path: (_) @syntax.inline.path
                    keys: (_)* @syntax.inline.keys) @syntax.inline.table
                
                (inline_array
                    path: (_) @syntax.inline.path
                    items: (_)* @syntax.inline.items) @syntax.inline.array
            ]
        """
    },
    "structure": {
        "section": """
            (section
                name: (_) @structure.section.name
                line: (_) @structure.section.line) @structure.section
        """,
        "subsection": """
            (section
                parent: (_) @structure.subsection.parent
                name: (_) @structure.subsection.name
                line: (_) @structure.subsection.line) @structure.subsection
        """,
        "reference": """
            (value
                path: (_) @structure.reference.path
                [contains "."]) @structure.reference
        """
    },
    "semantics": {
        "definition": """
            (value
                path: (_) @semantics.definition.path
                value_type: (_) @semantics.definition.type) @semantics.definition
        """,
        "type": """
            (type
                path: (_) @semantics.type.path
                type: (_) @semantics.type.name) @semantics.type
        """,
        "path": """
            (path
                segments: (_)* @semantics.path.segments) @semantics.path
        """
    },
    "documentation": {
        "comment": """
            (comment
                content: (_) @documentation.comment.content
                line: (_) @documentation.comment.line) @documentation.comment
        """,
        "description": """
            (description
                content: (_) @documentation.description.content
                line: (_) @documentation.description.line) @documentation.description
        """,
        "metadata": """
            (comment
                [starts-with "@"]
                content: (_) @documentation.metadata.content
                line: (_) @documentation.metadata.line) @documentation.metadata
        """
    }
} 