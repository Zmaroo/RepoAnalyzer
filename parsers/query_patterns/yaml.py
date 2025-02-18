"""
Query patterns for YAML files with enhanced documentation support.
"""

YAML_PATTERNS = {
    "syntax": {
        "mapping": """
            (mapping
                keys: (_)* @syntax.mapping.keys
                children: (_)* @syntax.mapping.children) @syntax.mapping
        """,
        "sequence": """
            (sequence
                items: (_)* @syntax.sequence.items) @syntax.sequence
        """,
        "scalar": """
            (scalar
                value: (_) @syntax.scalar.value) @syntax.scalar
        """,
        "anchor": """
            (anchor
                name: (_) @syntax.anchor.name) @syntax.anchor
        """
    },
    "structure": {
        "document": """
            (yaml_file
                children: (_)* @structure.document.children) @structure.document
        """,
        "section": """
            (mapping
                path: (_) @structure.section.path
                keys: (_)* @structure.section.keys) @structure.section
        """,
        "include": """
            (include
                path: (_) @structure.include.path) @structure.include
        """
    },
    "semantics": {
        "definition": """
            (mapping
                key: (_) @semantics.definition.key
                value: (_) @semantics.definition.value) @semantics.definition
        """,
        "reference": """
            (alias
                name: (_) @semantics.reference.name) @semantics.reference
        """,
        "environment": """
            (scalar
                value: (_) @semantics.environment.value
                [contains "${"] @semantics.environment) @semantics.environment.variable
        """
    },
    "documentation": {
        "comment": """
            (comment
                content: (_) @documentation.comment.content) @documentation.comment
        """,
        "metadata": """
            (mapping
                key: (_) @documentation.metadata.key
                [ends-with "_doc" "_description"]
                value: (_) @documentation.metadata.value) @documentation.metadata
        """,
        "description": """
            (mapping
                path: (_) @documentation.description.path
                content: (_) @documentation.description.content) @documentation.description
        """
    }
} 