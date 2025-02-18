"""Query patterns for Svelte files."""

SVELTE_PATTERNS = {
    "syntax": {
        "function": [
            """
            (script_element
                (start_tag)
                (raw_text)? @body
                (end_tag)) @function
            """
        ],
        "class": [
            """
            (style_element
                (start_tag)
                (raw_text)? @body
                (end_tag)) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (element
                (start_tag
                    (tag_name) @name
                    (attribute)* @attrs)
                (_)* @content
                (end_tag)?) @namespace
            """
        ]
    },
    "semantics": {
        "expression": [
            """
            (expression
                (_) @content) @expression
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 