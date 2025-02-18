"""Query patterns for Vue files."""

VUE_PATTERNS = {
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
            (template_element
                (start_tag)
                (_)* @content
                (end_tag)) @namespace
            """
        ]
    },
    "semantics": {
        "expression": [
            """
            (interpolation
                (raw_text)? @expr) @expression
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