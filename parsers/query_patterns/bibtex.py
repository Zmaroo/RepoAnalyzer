"""Query patterns for BibTeX files."""

from .common import COMMON_PATTERNS

BIBTEX_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "entry": {
            "pattern": """
            [
                (entry
                    ty: (entry_type) @syntax.entry.type
                    key: [
                        (key_brace) @syntax.entry.key.brace
                        (key_paren) @syntax.entry.key.paren
                    ]
                    field: (field)* @syntax.entry.fields) @syntax.entry.def,
                
                (string
                    ty: (string_type) @syntax.string.type
                    name: (identifier) @syntax.string.name
                    value: (value) @syntax.string.value) @syntax.string.def
            ]
            """,
            "extract": lambda node: {
                "type": node["captures"].get("syntax.entry.type", {}).get("text", "") or
                        node["captures"].get("syntax.string.type", {}).get("text", ""),
                "key": node["captures"].get("syntax.entry.key.brace", {}).get("text", "") or
                       node["captures"].get("syntax.entry.key.paren", {}).get("text", "")
            }
        }
    },
    
    "semantics": {
        "field": {
            "pattern": """
            [
                (field
                    name: (identifier) @semantics.field.name
                    value: (value) @semantics.field.value) @semantics.field.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.field.name", {}).get("text", ""),
                "value": node["captures"].get("semantics.field.value", {}).get("text", "")
            }
        }
    },
    
    "structure": {
        "document": {
            "pattern": """
            [
                (document
                    [(entry) @structure.document.entry
                     (string) @structure.document.string
                     (preamble) @structure.document.preamble
                     (comment) @structure.document.comment]*) @structure.document.def
            ]
            """,
            "extract": lambda node: {
                "entries": [e.get("text", "") for e in node["captures"].get("structure.document.entry", [])],
                "strings": [s.get("text", "") for s in node["captures"].get("structure.document.string", [])]
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "")
            }
        }
    }
} 