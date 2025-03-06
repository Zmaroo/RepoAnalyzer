"""
Query patterns for OCaml interface files (.mli).

These patterns capture top-level declarations from the custom AST produced by our OCaml interface parser.
"""

from typing import Dict, Any, List, Match, Optional
import re
from parsers.types import FileType, QueryPattern, PatternCategory, PatternPurpose

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
        ),
        "module_type": QueryPattern(
            pattern=r'^\s*module\s+type\s+([A-Z][a-zA-Z0-9_\'-]*)',
            extract=lambda m: {
                "type": "module_type",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches module type declarations",
            examples=["module type S = sig"]
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
        ),
        "inline_doc": QueryPattern(
            pattern=r'\(\*\s*(.*?)\s*\*\)',
            extract=lambda m: {
                "type": "inline_doc",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches inline documentation",
            examples=["(* Helper function *)"]
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
        ),
        "type_constraint": QueryPattern(
            pattern=r'^\s*constraint\s+([a-zA-Z0-9_\']+)\s*=\s*([^=\s]+)',
            extract=lambda m: {
                "type": "type_constraint",
                "type_var": m.group(1),
                "constraint": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches type constraints",
            examples=["constraint 'a = int"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "function_type": QueryPattern(
            pattern=r'^\s*val\s+([a-zA-Z0-9_\']+)\s*:\s*([^=]+?)\s*->\s*([^=\s]+)',
            extract=lambda m: {
                "type": "function_type",
                "name": m.group(1),
                "param_type": m.group(2),
                "return_type": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches function type declarations",
            examples=["val map: ('a -> 'b) -> 'a list -> 'b list"]
        ),
        "variant_type": QueryPattern(
            pattern=r'^\s*type\s+([a-zA-Z0-9_\']+)\s*=\s*\|?\s*([A-Z][a-zA-Z0-9_\']*(?:\s+of\s+[^|]+)?(?:\s*\|\s*[A-Z][a-zA-Z0-9_\']*(?:\s+of\s+[^|]+)?)*)',
            extract=lambda m: {
                "type": "variant_type",
                "name": m.group(1),
                "constructors": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches variant type definitions",
            examples=["type color = Red | Green | Blue"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "include": QueryPattern(
            pattern=r'^\s*include\s+([A-Z][a-zA-Z0-9_\'.]*)',
            extract=lambda m: {
                "type": "include",
                "module": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include statements",
            examples=["include List"]
        ),
        "open": QueryPattern(
            pattern=r'^\s*open\s+([A-Z][a-zA-Z0-9_\'.]*)',
            extract=lambda m: {
                "type": "open",
                "module": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches open statements",
            examples=["open String"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "abstract_type": QueryPattern(
            pattern=r'^\s*type\s+([a-zA-Z0-9_\']+)(?!\s*=)',
            extract=lambda m: {
                "type": "abstract_type",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches abstract type declarations",
            examples=["type t"]
        ),
        "private_type": QueryPattern(
            pattern=r'^\s*type\s+([a-zA-Z0-9_\']+)\s*=\s*private\s+([^=\s]+)',
            extract=lambda m: {
                "type": "private_type",
                "name": m.group(1),
                "implementation": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches private type declarations",
            examples=["type t = private int"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "missing_doc": QueryPattern(
            pattern=r'^\s*val\s+[a-zA-Z0-9_\']+(?!\s*:\s*[^=]+\s*\(\*)',
            extract=lambda m: {
                "type": "missing_doc",
                "declaration": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects value declarations without documentation",
            examples=["val x: int"]
        ),
        "incomplete_signature": QueryPattern(
            pattern=r'^\s*sig\s*(?![^=]*end)',
            extract=lambda m: {
                "type": "incomplete_signature",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects incomplete module signatures",
            examples=["sig val x: int"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_operator": QueryPattern(
            pattern=r'^\s*val\s+\(([\+\-\*/<>=@^|&]+)\)',
            extract=lambda m: {
                "type": "custom_operator",
                "operator": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom operator declarations",
            examples=["val (+++) : int -> int -> int"]
        ),
        "labeled_argument": QueryPattern(
            pattern=r'^\s*val\s+[a-zA-Z0-9_\']+\s*:\s*(?:([a-zA-Z0-9_\']+):([^->]+)(?:\s*->)?)+',
            extract=lambda m: {
                "type": "labeled_argument",
                "label": m.group(1),
                "type": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches labeled argument declarations",
            examples=["val f: label:int -> unit"]
        )
    }
}

# Add repository learning patterns
OCAML_INTERFACE_PATTERNS[PatternCategory.LEARNING] = {
    "module_structure": QueryPattern(
        pattern=r'^\s*module\s+([A-Z][a-zA-Z0-9_\']*)\s*:\s*sig(.*?)end',
        extract=lambda m: {
            "type": "module_structure",
            "name": m.group(1),
            "content": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches module structure patterns",
        examples=["module M: sig val x: int end"]
    ),
    "type_patterns": QueryPattern(
        pattern=r'^\s*type\s+([a-zA-Z0-9_\']+)(?:\s*=\s*([^=]+))?',
        extract=lambda m: {
            "type": "type_pattern",
            "name": m.group(1),
            "definition": m.group(2) if m.group(2) else None,
            "is_abstract": not bool(m.group(2)),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches type definition patterns",
        examples=["type t = int", "type t"]
    ),
    "value_patterns": QueryPattern(
        pattern=r'^\s*val\s+([a-zA-Z0-9_\']+)\s*:\s*([^=]+)',
        extract=lambda m: {
            "type": "value_pattern",
            "name": m.group(1),
            "type_sig": m.group(2),
            "is_function": "->" in m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches value declaration patterns",
        examples=["val x: int", "val f: int -> int"]
    )
}

# Function to extract patterns for repository learning
def extract_ocaml_interface_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from OCaml interface content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in OCAML_INTERFACE_PATTERNS:
            category_patterns = OCAML_INTERFACE_PATTERNS[category]
            for pattern_name, pattern in category_patterns.items():
                if isinstance(pattern, QueryPattern):
                    if isinstance(pattern.pattern, str):
                        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
                            pattern_data = pattern.extract(match)
                            patterns.append({
                                "name": pattern_name,
                                "category": category.value,
                                "content": match.group(0),
                                "metadata": pattern_data,
                                "confidence": 0.85
                            })
    
    return patterns

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