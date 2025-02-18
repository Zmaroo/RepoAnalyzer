"""
Query patterns for Regular Expression patterns.
"""

REGEX_PATTERNS = {
    "syntax": {
        "function": [
            """
            (group
                (pattern) @pattern) @function
            """,
            """
            (named_capturing_group
                name: (group_name) @name
                pattern: (pattern) @pattern) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (pattern) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (character_class
                (class_range)? @range
                (class_character)* @chars) @variable
            """
        ],
        "expression": [
            """
            (quantifier
                (pattern) @pattern
                (quantity) @quantity) @expression
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