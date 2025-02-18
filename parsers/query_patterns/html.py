"""Query patterns for HTML files with enhanced documentation support."""

HTML_PATTERNS = {
    "syntax": {
        "element": """
            (element
                tag: (_) @syntax.element.tag
                path: (_) @syntax.element.path
                depth: (_) @syntax.element.depth
                attributes: (_)* @syntax.element.attributes
                children: (_)* @syntax.element.children) @syntax.element
        """,
        "script": """
            (script
                content: (_) @syntax.script.content
                start: (_) @syntax.script.start
                end: (_) @syntax.script.end) @syntax.script
        """,
        "style": """
            (style
                content: (_) @syntax.style.content
                start: (_) @syntax.style.start
                end: (_) @syntax.style.end) @syntax.style
        """,
        "template": """
            (template
                content: (_) @syntax.template.content
                start: (_) @syntax.template.start
                end: (_) @syntax.template.end) @syntax.template
        """
    },
    "structure": {
        "head": """
            (head
                children: (_)* @structure.head.children) @structure.head
        """,
        "body": """
            (body
                children: (_)* @structure.body.children) @structure.body
        """,
        "section": """
            (section
                path: (_) @structure.section.path
                children: (_)* @structure.section.children) @structure.section
        """,
        "form": """
            (form
                path: (_) @structure.form.path
                children: (_)* @structure.form.children) @structure.form
        """
    },
    "semantics": {
        "meta": """
            (meta
                attributes: (_)* @semantics.meta.attributes) @semantics.meta
        """,
        "link": """
            (link
                attributes: (_)* @semantics.link.attributes) @semantics.link
        """,
        "schema": """
            (element
                attributes: (_)* @semantics.schema.attributes
                [has-attr "itemscope" "itemtype" "itemprop"]) @semantics.schema
        """,
        "aria": """
            (element
                attributes: (_)* @semantics.aria.attributes
                [has-attr-prefix "aria-"]) @semantics.aria
        """
    },
    "documentation": {
        "comment": """
            (comment
                content: (_) @documentation.comment.content
                start: (_) @documentation.comment.start
                end: (_) @documentation.comment.end) @documentation.comment
        """,
        "doctype": """
            (doctype
                content: (_) @documentation.doctype.content
                start: (_) @documentation.doctype.start
                end: (_) @documentation.doctype.end) @documentation.doctype
        """,
        "metadata": """
            (meta
                [has-attr "name" "description" "keywords"]
                attributes: (_)* @documentation.metadata.attributes) @documentation.metadata
        """
    }
}