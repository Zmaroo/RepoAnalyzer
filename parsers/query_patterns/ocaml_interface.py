"""
Query patterns for OCaml interface files (.mli).

These patterns capture top-level declarations from the custom AST produced by our OCaml interface parser.
The custom parser returns an AST with a root node ("ocaml_stream") whose children have types such as
"val_declaration", "type_definition", and "module_declaration". The query patterns below use capture names
(e.g. @val_declaration) to ensure that all pertinent information is extracted.
"""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory

def extract_val_declaration(match: Match) -> Dict[str, Any]:
    """Extract value declaration information."""
    return {
        "type": "val_declaration",
        "name": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

OCAML_INTERFACE_PATTERNS = {
    PatternCategory.SYNTAX: {
        "val_declaration": QueryPattern(
            pattern=r'^\s*val\s+([a-zA-Z0-9_\'-]+)',
            extract=extract_val_declaration,
            description="Matches value declarations",
            examples=["val x: int"]
        ),
        "type_definition": QueryPattern(
            pattern=r'^\s*type\s+([a-zA-Z0-9_\'-]+)',
            extract=lambda m: {
                "type": "type_definition",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches type definitions",
            examples=["type person"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "module_declaration": QueryPattern(
            pattern=r'^\s*module\s+([A-Z][a-zA-Z0-9_\'-]*)',
            extract=lambda m: {
                "type": "module_declaration",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches module declarations",
            examples=["module MyModule: sig"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "doc_comment": QueryPattern(
            pattern=r'^\s*\(\*\*\s*(.*?)\s*\*\)',
            extract=lambda m: {
                "type": "doc_comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches documentation comments",
            examples=["(** Interface documentation *)"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "signature": QueryPattern(
            pattern=r'^\s*sig\s*(.*?)\s*end',
            extract=lambda m: {
                "type": "signature",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches module signatures",
            examples=["sig val x: int end"]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "interface": {
        "can_contain": ["val_declaration", "type_definition", "module_declaration"],
        "can_be_contained_by": []
    },
    "val_declaration": {
        "can_contain": ["doc_comment"],
        "can_be_contained_by": ["interface", "signature"]
    },
    "type_definition": {
        "can_contain": ["doc_comment"],
        "can_be_contained_by": ["interface", "signature"]
    }
} 