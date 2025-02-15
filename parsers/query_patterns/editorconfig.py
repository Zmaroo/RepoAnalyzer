"""
Query patterns for EditorConfig files.

These patterns target the custom AST produced by our custom editorconfig parser.
"""

EDITORCONFIG_PATTERNS = [
    # Capture documentation if available (assuming you embed it as a node)
    "(editorconfig (documentation) @documentation)",
    # Capture EditorConfig sections and their properties.
    "(editorconfig (section) @section)",
    "(section (property) @property)"
] 