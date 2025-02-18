"""
Query patterns for LaTeX files.
"""

LATEX_PATTERNS = {
    "syntax": {
        "function": [
            """
            (command_name) @function
            """,
            """
            (environment_name) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (document_class) @namespace
            """,
            """
            (package_include) @namespace
            """
        ],
        "import": [
            """
            (usepackage_command) @import
            """,
            """
            (input_command) @import
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