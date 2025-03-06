"""
Query patterns for Nim files with enhanced pattern support.
"""

from typing import Dict, Any, List, Match, Optional
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternPurpose
import re

# Language identifier
LANGUAGE = "nim"

def extract_proc(match: Match) -> Dict[str, Any]:
    """Extract procedure information."""
    return {
        "type": "proc",
        "name": match.group(1),
        "parameters": match.group(2) if match.group(2) else "",
        "return_type": match.group(3) if match.group(3) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_type(match: Match) -> Dict[str, Any]:
    """Extract type information."""
    return {
        "type": "type_def",
        "name": match.group(1),
        "definition": match.group(2) if match.group(2) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

# Nim patterns for all categories
NIM_PATTERNS = {
    PatternCategory.SYNTAX: {
        "proc": QueryPattern(
            pattern=r'proc\s+([a-zA-Z0-9_]+)\s*(?:\[.*?\])?\s*(\(.*?\))?\s*(?::\s*([^=]+))?',
            extract=extract_proc,
            description="Matches procedure declarations",
            examples=["proc add(x, y: int): int"]
        ),
        "type_def": QueryPattern(
            pattern=r'type\s+([a-zA-Z0-9_]+)\s*(?:=\s*([^=\n]+))?',
            extract=extract_type,
            description="Matches type definitions",
            examples=["type Person = object"]
        ),
        "const_def": QueryPattern(
            pattern=r'const\s+([a-zA-Z0-9_]+)\s*(?::\s*[^=]+)?\s*=\s*([^=\n]+)',
            extract=lambda m: {
                "type": "const_def",
                "name": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches constant definitions",
            examples=["const MaxValue = 100"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "module": QueryPattern(
            pattern=r'(?:import|include|from)\s+([a-zA-Z0-9_/]+)',
            extract=lambda m: {
                "type": "module",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches module imports",
            examples=["import strutils"]
        ),
        "object_def": QueryPattern(
            pattern=r'type\s+([a-zA-Z0-9_]+)\s*=\s*object\s*(?:of\s+([a-zA-Z0-9_]+))?\s*([\s\S]*?)(?:^\S|$)',
            extract=lambda m: {
                "type": "object_def",
                "name": m.group(1),
                "parent": m.group(2) if m.group(2) else None,
                "fields": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches object definitions",
            examples=["type Person = object\n  name: string\n  age: int"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "doc_comment": QueryPattern(
            pattern=r'##\s*([^\n]+)',
            extract=lambda m: {
                "type": "doc_comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches documentation comments",
            examples=["## This is a doc comment"]
        ),
        "pragma": QueryPattern(
            pattern=r'\{\.([a-zA-Z0-9_]+)(?::\s*([^}]+))?\.\}',
            extract=lambda m: {
                "type": "pragma",
                "name": m.group(1),
                "value": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches pragmas",
            examples=["{.deprecated.}", "{.raises: [IOError].}"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "generic": QueryPattern(
            pattern=r'([a-zA-Z0-9_]+)\s*\[([^\]]+)\]',
            extract=lambda m: {
                "type": "generic",
                "name": m.group(1),
                "params": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches generic type usage",
            examples=["seq[int]", "Table[string, int]"]
        ),
        "enum_def": QueryPattern(
            pattern=r'type\s+([a-zA-Z0-9_]+)\s*=\s*enum\s*([\s\S]*?)(?:^\S|$)',
            extract=lambda m: {
                "type": "enum_def",
                "name": m.group(1),
                "values": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches enum definitions",
            examples=["type Color = enum\n  Red, Green, Blue"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "iterator_def": QueryPattern(
            pattern=r'iterator\s+([a-zA-Z0-9_]+)\s*(\(.*?\))?\s*(?::\s*([^=]+))?\s*=',
            extract=lambda m: {
                "type": "iterator_def",
                "name": m.group(1),
                "params": m.group(2) if m.group(2) else "",
                "return_type": m.group(3) if m.group(3) else "",
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches iterator definitions",
            examples=["iterator items(x: seq[int]): int ="]
        ),
        "template_def": QueryPattern(
            pattern=r'template\s+([a-zA-Z0-9_]+)\s*(\(.*?\))?\s*(?::\s*([^=]+))?\s*=',
            extract=lambda m: {
                "type": "template_def",
                "name": m.group(1),
                "params": m.group(2) if m.group(2) else "",
                "return_type": m.group(3) if m.group(3) else "",
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches template definitions",
            examples=["template debug(x: untyped) ="]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "import": QueryPattern(
            pattern=r'import\s+([a-zA-Z0-9_,\s/]+)',
            extract=lambda m: {
                "type": "import",
                "modules": [mod.strip() for mod in m.group(1).split(',')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches import statements",
            examples=["import os, strutils"]
        ),
        "include": QueryPattern(
            pattern=r'include\s+([a-zA-Z0-9_,\s/]+)',
            extract=lambda m: {
                "type": "include",
                "files": [f.strip() for f in m.group(1).split(',')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include statements",
            examples=["include common"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "error_handling": QueryPattern(
            pattern=r'try:[\s\S]*?except\s+([^:]+):',
            extract=lambda m: {
                "type": "error_handling",
                "exception": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches error handling patterns",
            examples=["try:\n  readFile(\"file.txt\")\nexcept IOError:\n  echo \"Error\""]
        ),
        "defer": QueryPattern(
            pattern=r'defer:\s*([\s\S]*?)(?:^\S|$)',
            extract=lambda m: {
                "type": "defer",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches defer blocks",
            examples=["defer:\n  file.close()"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "mutable_param": QueryPattern(
            pattern=r'proc\s+[a-zA-Z0-9_]+\s*\([^)]*var\s+[^)]+\)',
            extract=lambda m: {
                "type": "mutable_param",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects mutable parameters",
            examples=["proc modify(var x: int)"]
        ),
        "unsafe_pragma": QueryPattern(
            pattern=r'\{\.(?:checks|boundChecks|overflowChecks):\s*off\.\}',
            extract=lambda m: {
                "type": "unsafe_pragma",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects unsafe pragma usage",
            examples=["{.checks: off.}"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_pragma": QueryPattern(
            pattern=r'\{\.([a-zA-Z0-9_]+)\.}',
            extract=lambda m: {
                "type": "custom_pragma",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom pragmas",
            examples=["{.custom.}"]
        ),
        "custom_operator": QueryPattern(
            pattern=r'proc\s*`([^`]+)`\s*(\(.*?\))?\s*(?::\s*([^=]+))?\s*=',
            extract=lambda m: {
                "type": "custom_operator",
                "operator": m.group(1),
                "params": m.group(2) if m.group(2) else "",
                "return_type": m.group(3) if m.group(3) else "",
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom operator definitions",
            examples=["proc `++`(x, y: int): int ="]
        )
    }
}

# Add repository learning patterns
NIM_PATTERNS[PatternCategory.LEARNING] = {
    "module_structure": QueryPattern(
        pattern=r'(?:type|proc|const|var|let)\s+[a-zA-Z0-9_]+[^=]*=(?:[^=]|$)',
        extract=lambda m: {
            "type": "module_structure",
            "content": m.group(0),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches module structure patterns",
        examples=["type Person = object", "proc add(x, y: int): int ="]
    ),
    "type_patterns": QueryPattern(
        pattern=r'type\s+([a-zA-Z0-9_]+)(?:\s*=\s*([^=\n]+))?',
        extract=lambda m: {
            "type": "type_pattern",
            "name": m.group(1),
            "definition": m.group(2) if m.group(2) else None,
            "is_object": "object" in (m.group(2) or ""),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches type definition patterns",
        examples=["type MyType = int", "type Person = object"]
    ),
    "proc_patterns": QueryPattern(
        pattern=r'proc\s+([a-zA-Z0-9_]+)\s*(?:\[.*?\])?\s*(\(.*?\))?\s*(?::\s*([^=]+))?\s*=',
        extract=lambda m: {
            "type": "proc_pattern",
            "name": m.group(1),
            "is_generic": "[" in m.group(0),
            "has_params": bool(m.group(2)),
            "has_return_type": bool(m.group(3)),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches procedure definition patterns",
        examples=["proc add[T](x, y: T): T ="]
    )
}

# Function to extract patterns for repository learning
def extract_nim_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Nim content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in NIM_PATTERNS:
            category_patterns = NIM_PATTERNS[category]
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
    "module": {
        "can_contain": ["proc", "type", "const", "var", "let", "iterator", "template"],
        "can_be_contained_by": []
    },
    "proc": {
        "can_contain": ["pragma", "doc_comment"],
        "can_be_contained_by": ["module", "type"]
    },
    "type": {
        "can_contain": ["proc", "pragma", "doc_comment"],
        "can_be_contained_by": ["module"]
    }
} 