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

# Repository learning patterns for BibTeX
BIBTEX_PATTERNS_FOR_LEARNING = {
    "entry_type_patterns": {
        "pattern": """
        [
            (entry
                ty: (entry_type) @entry.type) @entry.def
        ]
        """,
        "extract": lambda node: {
            "type": "entry_type_pattern",
            "entry_type": node["captures"].get("entry.type", {}).get("text", "").lower(),
            "is_article": node["captures"].get("entry.type", {}).get("text", "").lower() == "article",
            "is_book": node["captures"].get("entry.type", {}).get("text", "").lower() == "book",
            "is_conference": node["captures"].get("entry.type", {}).get("text", "").lower() in ["inproceedings", "conference", "proceedings"]
        }
    },
    
    "citation_key_patterns": {
        "pattern": """
        [
            (entry
                key: [(key_brace) (key_paren)] @citation.key) @citation.entry
        ]
        """,
        "extract": lambda node: {
            "type": "citation_key_pattern",
            "key": node["captures"].get("citation.key", {}).get("text", ""),
            "has_year": any(y in node["captures"].get("citation.key", {}).get("text", "") for y in 
                          ["19", "20", "21", "22", "23"]),
            "has_author": any(node["captures"].get("citation.key", {}).get("text", "").lower().startswith(prefix) 
                            for prefix in ["auth", "smith", "jones", "wang", "zhang", "lee"])
        }
    },
    
    "field_usage_patterns": {
        "pattern": """
        [
            (field
                name: (identifier) @field.name) @field.def
        ]
        """,
        "extract": lambda node: {
            "type": "field_usage_pattern",
            "field": node["captures"].get("field.name", {}).get("text", "").lower(),
            "is_required": node["captures"].get("field.name", {}).get("text", "").lower() in 
                          ["author", "title", "journal", "year", "booktitle", "editor", "publisher"],
            "is_optional": node["captures"].get("field.name", {}).get("text", "").lower() in 
                          ["volume", "number", "pages", "month", "note", "abstract", "keywords"]
        }
    }
}

# Add the repository learning patterns to the main patterns
BIBTEX_PATTERNS['REPOSITORY_LEARNING'] = BIBTEX_PATTERNS_FOR_LEARNING 