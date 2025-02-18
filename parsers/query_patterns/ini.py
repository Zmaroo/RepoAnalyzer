"""Query patterns for INI/Properties files with enhanced documentation support."""

INI_PATTERNS = {
    "syntax": {
        "section": """
            (section
                name: (_) @syntax.section.name
                properties: (_)* @syntax.section.properties) @syntax.section
        """,
        "property": """
            (property
                key: (_) @syntax.property.key
                value: (_) @syntax.property.value
                section: (_) @syntax.property.section) @syntax.property
        """,
        "include": """
            (include
                path: (_) @syntax.include.path) @syntax.include
        """,
        "variable": """
            (variable
                name: (_) @syntax.variable.name
                value: (_) @syntax.variable.value) @syntax.variable
        """
    },
    "structure": {
        "root": """
            (ini_document
                children: (_)* @structure.root.children) @structure.root
        """,
        "hierarchy": """
            (section
                name: (_) @structure.hierarchy.name
                line: (_) @structure.hierarchy.line) @structure.hierarchy
        """,
        "reference": """
            (reference
                from: (_) @structure.reference.from
                to: (_) @structure.reference.to) @structure.reference
        """
    },
    "semantics": {
        "definition": """
            (property
                key: (_) @semantics.definition.key
                value: (_) @semantics.definition.value) @semantics.definition
        """,
        "environment": """
            (environment
                variable: (_) @semantics.environment.variable
                section: (_) @semantics.environment.section
                key: (_) @semantics.environment.key) @semantics.environment
        """,
        "path": """
            (path
                path: (_) @semantics.path.value
                section: (_) @semantics.path.section
                key: (_) @semantics.path.key) @semantics.path
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
                section: (_) @documentation.description.section
                key: (_)? @documentation.description.key
                content: (_) @documentation.description.content
                line: (_) @documentation.description.line) @documentation.description
        """,
        "metadata": """
            (section
                name: (_) @documentation.metadata.section
                comments: (_)* @documentation.metadata.comments) @documentation.metadata
        """
    }
} 