"""
Nim-specific query patterns for our custom Nim parser.
These patterns capture procedure and type definitions within Nim source files.
"""

NIM_PATTERNS = [
    # Capture procedure definitions
    "(nim (proc) @proc)",
    # Capture type definitions
    "(nim (type) @type)"
] 