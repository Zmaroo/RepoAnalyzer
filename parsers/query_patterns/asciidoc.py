"""Query patterns for AsciiDoc files with enhanced documentation support."""

ASCIIDOC_PATTERNS = {
    "syntax": {
        "section": """
            (section
                title: (_) @syntax.section.title
                level: (_) @syntax.section.level) @syntax.section
        """,
        "block": """
            (block
                type: (_) @syntax.block.type
                content: (_) @syntax.block.content) @syntax.block
        """,
        "macro": """
            (macro
                name: (_) @syntax.macro.name
                target: (_) @syntax.macro.target
                attributes: (_)? @syntax.macro.attributes) @syntax.macro
        """,
        "attribute": """
            (attribute
                name: (_) @syntax.attribute.name
                value: (_) @syntax.attribute.value) @syntax.attribute
        """,
        "list": """
            (list
                type: (_) @syntax.list.type
                items: (_)* @syntax.list.items) @syntax.list
        """
    },
    "structure": {
        "hierarchy": """
            (section
                title: (_) @structure.hierarchy.title
                level: (_) @structure.hierarchy.level
                parent: (_)? @structure.hierarchy.parent) @structure.hierarchy
        """,
        "include": """
            (include
                path: (_) @structure.include.path
                options: (_)? @structure.include.options) @structure.include
        """,
        "reference": """
            (reference
                target: (_) @structure.reference.target) @structure.reference
        """,
        "anchor": """
            (anchor
                id: (_) @structure.anchor.id) @structure.anchor
        """
    },
    "semantics": {
        "link": """
            (link
                url: (_) @semantics.link.url
                text: (_)? @semantics.link.text) @semantics.link
        """,
        "callout": """
            (callout
                number: (_) @semantics.callout.number) @semantics.callout
        """,
        "footnote": """
            (footnote
                id: (_)? @semantics.footnote.id
                content: (_) @semantics.footnote.content) @semantics.footnote
        """,
        "term": """
            (term
                name: (_) @semantics.term.name
                definition: (_) @semantics.term.definition) @semantics.term
        """
    },
    "documentation": {
        "metadata": """
            (header
                title: (_) @documentation.metadata.title
                attributes: (_)* @documentation.metadata.attributes) @documentation.metadata
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
        "annotation": """
            (annotation
                type: (_) @documentation.annotation.type
                content: (_) @documentation.annotation.content) @documentation.annotation
        """
    }
} 