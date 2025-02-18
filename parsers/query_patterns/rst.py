"""Query patterns for reStructuredText files with enhanced documentation support."""

RST_PATTERNS = {
    "syntax": {
        "section": """
            (section
                title: (_) @syntax.section.title
                level: (_) @syntax.section.level) @syntax.section
        """,
        "directive": """
            (directive
                name: (_) @syntax.directive.name
                content: (_) @syntax.directive.content) @syntax.directive
        """,
        "role": """
            (role
                type: (_) @syntax.role.type
                content: (_) @syntax.role.content) @syntax.role
        """,
        "code_block": """
            (code_block
                language: (_) @syntax.code_block.language) @syntax.code_block
        """,
        "literal": """
            (literal
                content: (_) @syntax.literal.content) @syntax.literal
        """
    },
    "structure": {
        "hierarchy": """
            (section
                title: (_) @structure.hierarchy.title
                level: (_) @structure.hierarchy.level
                parent: (_)? @structure.hierarchy.parent) @structure.hierarchy
        """,
        "reference": """
            (reference
                target: (_) @structure.reference.target) @structure.reference
        """,
        "include": """
            (include
                path: (_) @structure.include.path) @structure.include
        """,
        "toc": """
            (toc
                entries: (_)* @structure.toc.entries) @structure.toc
        """
    },
    "semantics": {
        "link": """
            (link
                text: (_) @semantics.link.text) @semantics.link
        """,
        "definition": """
            (definition
                term: (_) @semantics.definition.term
                content: (_) @semantics.definition.content) @semantics.definition
        """,
        "citation": """
            (citation
                key: (_) @semantics.citation.key
                text: (_) @semantics.citation.text) @semantics.citation
        """,
        "substitution": """
            (substitution
                name: (_) @semantics.substitution.name
                value: (_) @semantics.substitution.value) @semantics.substitution
        """
    },
    "documentation": {
        "metadata": """
            (field_list
                fields: (_)* @documentation.metadata.fields) @documentation.metadata
        """,
        "comment": """
            (comment
                content: (_) @documentation.comment.content) @documentation.comment
        """,
        "admonition": """
            (admonition
                type: (_) @documentation.admonition.type
                content: (_) @documentation.admonition.content) @documentation.admonition
        """,
        "field": """
            (field
                name: (_) @documentation.field.name
                content: (_) @documentation.field.content) @documentation.field
        """
    }
} 