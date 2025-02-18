"""
Query patterns for JSON files with enhanced documentation support.
"""

JSON_PATTERNS = {
    "syntax": {
        "object": """
            (object
                path: (_) @syntax.object.path
                keys: (_)* @syntax.object.keys) @syntax.object
        """,
        "array": """
            (array
                path: (_) @syntax.array.path
                length: (_) @syntax.array.length) @syntax.array
        """,
        "value": """
            (value
                path: (_) @syntax.value.path
                type: (_) @syntax.value.type) @syntax.value
        """,
        "type": """
            (type
                path: (_) @syntax.type.path
                name: (_) @syntax.type.name) @syntax.type
        """
    },
    "structure": {
        "root": """
            (json_document
                root: (_) @structure.root.node) @structure.root
        """,
        "path": """
            (path
                segments: (_)* @structure.path.segments) @structure.path
        """,
        "reference": """
            (reference
                path: (_) @structure.reference.path
                target: (_) @structure.reference.target) @structure.reference
        """
    },
    "semantics": {
        "definition": """
            (definition
                path: (_) @semantics.definition.path
                schema: (_) @semantics.definition.schema) @semantics.definition
        """,
        "variable": """
            (variable
                path: (_) @semantics.variable.path
                name: (_) @semantics.variable.name) @semantics.variable
        """,
        "pattern": """
            (pattern
                path: (_) @semantics.pattern.path
                regex: (_) @semantics.pattern.regex) @semantics.pattern
        """
    },
    "documentation": {
        "comment": """
            [
                (comment_single
                    content: (_) @documentation.comment.content
                    line: (_) @documentation.comment.line) @documentation.comment.single
                
                (comment_multi
                    content: (_) @documentation.comment.content
                    start: (_) @documentation.comment.start
                    end: (_) @documentation.comment.end) @documentation.comment.multi
            ]
        """,
        "schema": """
            (schema
                type: (_) @documentation.schema.type
                title: (_)? @documentation.schema.title
                description: (_)? @documentation.schema.description) @documentation.schema
        """,
        "description": """
            (description
                path: (_) @documentation.description.path
                content: (_) @documentation.description.content) @documentation.description
        """
    }
} 