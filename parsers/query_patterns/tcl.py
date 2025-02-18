"""Tcl-specific Tree-sitter patterns.

This module defines basic queries for capturing Tcl constructs, most notably procedure definitions.
"""

TCL_PATTERNS = {
    "default": r"""
        (procedure
            name: (simple_word) @procedure.name
            arguments: (arguments) @procedure.arguments
            body: (block)? @procedure.body)
    """
} 