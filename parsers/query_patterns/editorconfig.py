"""
Query patterns for EditorConfig files.

These patterns target the custom AST produced by our custom editorconfig parser.
"""

EDITORCONFIG_PATTERNS = {
    "documentation": """
        [
          (editorconfig (documentation) @documentation)
        ]
    """,
    
    "section": """
        [
          (editorconfig (section) @section),
          (section (property) @property)
        ]
    """
} 