"""Nim language patterns."""

from typing import Dict, Any, List, Match, Optional
import re
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternPurpose, PatternInfo
from parsers.models import PATTERN_CATEGORIES

# Language identifier
LANGUAGE = "nim"

def extract_proc(match: Match) -> Dict[str, Any]:
    """Extract procedure information."""
    return {
        "name": match.group(1),
        "parameters": match.group(2),
        "return_type": match.group(3),
        "category": PatternCategory.SYNTAX,
        "purpose": PatternPurpose.UNDERSTANDING
    }

def extract_type(match: Match) -> Dict[str, Any]:
    """Extract type information."""
    return {
        "name": match.group(1),
        "category": PatternCategory.SEMANTICS,
        "purpose": PatternPurpose.UNDERSTANDING
    }

# Nim patterns organized by category and purpose
NIM_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "proc": QueryPattern(
                pattern=r'^proc\s+(\w+)\*?\s*\((.*?)\)(?:\s*:\s*(\w+))?\s*=',
                extract=extract_proc,
                description="Matches Nim procedure definitions",
                examples=["proc add*(x, y: int): int ="]
            ),
            "type": QueryPattern(
                pattern=r'^type\s+(\w+)\*?\s*=\s*(?:object|enum|tuple|ref\s+object)',
                extract=extract_type,
                description="Matches Nim type definitions",
                examples=["type Person* = object"]
            )
        },
        PatternPurpose.MODIFICATION: {
            "proc_body": QueryPattern(
                pattern=r'proc\s+\w+[^=]+=\s*(.*?)(?:\n\s*\w+|$)',
                description="Matches procedure bodies for modification",
                examples=["proc test = echo \"test\""]
            )
        },
        PatternPurpose.VALIDATION: {
            "naming_convention": QueryPattern(
                pattern=r'^(?:proc|type|var|let|const)\s+([A-Z]\w+|\w+)',
                description="Validates Nim naming conventions",
                examples=["proc PascalCase", "var camelCase"]
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern=r'^(?:var|let|const)\s+(\w+)\*?\s*(?::\s*([^=]+))?\s*(?:=\s*(.+))?$',
                description="Matches variable declarations",
                examples=["var x: int = 5"]
            )
        },
        PatternPurpose.VALIDATION: {
            "type_check": QueryPattern(
                pattern=r':\s*([^=\s]+)(?:\s*=|$)',
                description="Validates type annotations",
                examples=["x: int", "y: seq[string]"]
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "docstring": QueryPattern(
                pattern=r'##\s*(.+)$',
                description="Matches Nim documentation strings",
                examples=["## This is a docstring"]
            ),
            "comment": QueryPattern(
                pattern=r'#\s*(.+)$',
                description="Matches single-line comments",
                examples=["# This is a comment"]
            )
        },
        PatternPurpose.VALIDATION: {
            "missing_doc": QueryPattern(
                pattern=r'^proc\s+\w+\*[^#\n]+\n',
                description="Detects exported procs without documentation",
                examples=["proc public* = echo \"no docs\""]
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "import": QueryPattern(
                pattern=r'^import\s+(.*?)(?:\s+except\s+.*)?$',
                description="Matches import statements",
                examples=["import strutils, sequtils"]
            ),
            "module": QueryPattern(
                pattern=r'^module\s+(\w+)',
                description="Matches module declarations",
                examples=["module mymodule"]
            )
        },
        PatternPurpose.VALIDATION: {
            "circular_import": QueryPattern(
                pattern=r'(?:^|\n)import\s+([^#\n]+)',
                description="Detects potential circular imports",
                examples=["import a, b, a"]
            )
        }
    },
    
    PatternCategory.CODE_PATTERNS: {
        PatternPurpose.UNDERSTANDING: {
            "error_handling": QueryPattern(
                pattern=r'try:.*?except\s+(\w+):\s*\n',
                description="Identifies error handling patterns",
                examples=["try: doSomething()\nexcept IOError: discard"]
            )
        },
        PatternPurpose.MODIFICATION: {
            "refactoring": QueryPattern(
                pattern=r'(?:proc|type|var)\s+(\w+)\*?\s*=',
                description="Identifies elements that might need refactoring",
                examples=["proc longFunction = ..."]
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.LEARNING: {
            "best_practice": QueryPattern(
                pattern=r'proc\s+\w+\*.*?=.*?(?:result|return)',
                description="Identifies common Nim idioms and practices",
                examples=["proc calc*: int = result = 42"]
            ),
            "anti_pattern": QueryPattern(
                pattern=r'var\s+\w+\s*(?!:)',
                description="Identifies potential anti-patterns",
                examples=["var x = 5  # missing type annotation"]
            )
        }
    },
    
    PatternCategory.CONTEXT: {
        PatternPurpose.EXPLANATION: {
            "code_context": QueryPattern(
                pattern=r'(?:type|proc|var|let|const)\s+(\w+).*?(?:=|\{|\()',
                description="Identifies context for code explanations",
                examples=["type Person = object", "proc add(x, y: int) = x + y"]
            ),
            "usage_context": QueryPattern(
                pattern=r'(\w+)\s*(?:\(|=|\.)',
                description="Identifies usage context",
                examples=["person.name", "add(1, 2)"]
            )
        }
    },
    
    PatternCategory.DEPENDENCIES: {
        PatternPurpose.UNDERSTANDING: {
            "direct_imports": QueryPattern(
                pattern=r'^import\s+(.*?)$',
                description="Identifies direct dependencies",
                examples=["import strutils"]
            ),
            "package_refs": QueryPattern(
                pattern=r'(?:from|import)\s+(\w+)/\w+',
                description="Identifies package references",
                examples=["from nimble/pkgs import pkg"]
            )
        }
    },
    
    PatternCategory.BEST_PRACTICES: {
        PatternPurpose.SUGGESTION: {
            "type_hints": QueryPattern(
                pattern=r'(?:proc|var|let)\s+\w+\s*(?!:)',
                description="Suggests adding type hints",
                examples=["var x = 5  # Missing type hint"]
            ),
            "export_hints": QueryPattern(
                pattern=r'^(?:proc|type)\s+\w+[^*\n]*$',
                description="Suggests considering exports",
                examples=["proc publicApi = discard  # Consider exporting"]
            )
        }
    },
    
    PatternCategory.COMMON_ISSUES: {
        PatternPurpose.DEBUGGING: {
            "nil_access": QueryPattern(
                pattern=r'(\w+)(?:\.\w+|\[\w+\])',
                description="Potential nil access points",
                examples=["obj.field", "arr[idx]"]
            ),
            "resource_cleanup": QueryPattern(
                pattern=r'(?:open|new)\s*\(',
                description="Resource allocation without cleanup",
                examples=["open(\"file.txt\")", "new(obj)"]
            )
        }
    },
    
    PatternCategory.USER_PATTERNS: {
        PatternPurpose.COMPLETION: {
            "common_completions": QueryPattern(
                pattern=r'(\w+)(?:\.|:|\()',
                description="Common completion points",
                examples=["obj.", "proc("]
            )
        },
        PatternPurpose.UNDERSTANDING: {
            "coding_style": QueryPattern(
                pattern=r'(?:proc|type|var|let|const)\s+([A-Z]\w+|\w+)',
                description="User's naming style",
                examples=["proc myFunction", "type MyType"]
            )
        }
    }
}

# Nim patterns specifically for repository learning
NIM_PATTERNS_FOR_LEARNING = {
    # Procedure patterns
    'proc_pattern': PatternInfo(
        pattern=r'^proc\s+(\w+)\*?\s*\((.*?)\)(?:\s*:\s*(\w+))?\s*=',
        extract=lambda match: {
            'name': match.group(1),
            'parameters': match.group(2),
            'return_type': match.group(3),
            'exported': '*' in match.group(0)
        }
    ),
    
    # Type patterns
    'object_type': PatternInfo(
        pattern=r'^type\s+(\w+)\*?\s*=\s*object\s*(?:of\s+(\w+))?\s*:?',
        extract=lambda match: {
            'name': match.group(1),
            'parent': match.group(2),
            'kind': 'object',
            'exported': '*' in match.group(0)
        }
    ),
    
    'enum_type': PatternInfo(
        pattern=r'^type\s+(\w+)\*?\s*=\s*enum\s*',
        extract=lambda match: {
            'name': match.group(1),
            'kind': 'enum',
            'exported': '*' in match.group(0)
        }
    ),
    
    # Variable declarations
    'var_declaration': PatternInfo(
        pattern=r'^(var|let|const)\s+(\w+)\*?\s*(?::\s*(\w+))?\s*=\s*(.+)$',
        extract=lambda match: {
            'kind': match.group(1),
            'name': match.group(2),
            'type': match.group(3),
            'value': match.group(4),
            'exported': '*' in match.group(0)
        }
    ),
    
    # Module structure patterns
    'module_imports': PatternInfo(
        pattern=r'^import\s+(.*?)(?:\s+except\s+.*)?$',
        extract=lambda match: {
            'modules': [mod.strip() for mod in match.group(1).split(',')],
            'type': 'import'
        }
    ),
    
    'module_exports': PatternInfo(
        pattern=r'^export\s+(.*?)$',
        extract=lambda match: {
            'modules': [mod.strip() for mod in match.group(1).split(',')],
            'type': 'export'
        }
    ),
    
    # Error handling patterns
    'try_except': PatternInfo(
        pattern=r'^try\s*:',
        extract=lambda match: {
            'type': 'error_handling',
            'mechanism': 'try_except'
        }
    ),
    
    'raise_exception': PatternInfo(
        pattern=r'^(?:\s*)raise\s+(?:new)?(\w+)',
        extract=lambda match: {
            'type': 'error_handling',
            'mechanism': 'raise',
            'exception_type': match.group(1)
        }
    ),
    
    # Naming conventions
    'identifier_pattern': PatternInfo(
        pattern=r'\b([a-zA-Z]\w*)\b',
        extract=lambda match: {
            'identifier': match.group(1),
            'convention': 'camelCase' if match.group(1)[0].islower() and any(c.isupper() for c in match.group(1)) else
                         'snake_case' if '_' in match.group(1) else
                         'PascalCase' if match.group(1)[0].isupper() else
                         'lowercase' if match.group(1).islower() else
                         'UPPERCASE' if match.group(1).isupper() else
                         'unknown'
        }
    )
}

# Update NIM_PATTERNS with learning patterns
NIM_PATTERNS[PatternCategory.LEARNING] = NIM_PATTERNS_FOR_LEARNING

def extract_nim_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """
    Extract Nim patterns from content for repository learning.
    
    Args:
        content: The Nim content to analyze
        
    Returns:
        List of extracted patterns with metadata
    """
    patterns = []
    
    # Compile patterns
    compiled_patterns = {
        name: re.compile(pattern_info.pattern, re.MULTILINE)
        for name, pattern_info in NIM_PATTERNS_FOR_LEARNING.items()
    }
    
    # Process procedure patterns
    procs = []
    for match in compiled_patterns['proc_pattern'].finditer(content):
        extracted = NIM_PATTERNS_FOR_LEARNING['proc_pattern'].extract(match)
        procs.append(extracted)
    
    if procs:
        patterns.append({
            'name': 'nim_procedure_style',
            'content': f"Procedures: {', '.join(p['name'] for p in procs[:3])}",
            'metadata': {
                'procedures': procs[:10],
                'exported_count': sum(1 for p in procs if p.get('exported', False)),
                'total_count': len(procs)
            },
            'confidence': 0.9
        })
    
    # Process type patterns
    object_types = []
    for match in compiled_patterns['object_type'].finditer(content):
        extracted = NIM_PATTERNS_FOR_LEARNING['object_type'].extract(match)
        object_types.append(extracted)
    
    enum_types = []
    for match in compiled_patterns['enum_type'].finditer(content):
        extracted = NIM_PATTERNS_FOR_LEARNING['enum_type'].extract(match)
        enum_types.append(extracted)
    
    if object_types or enum_types:
        patterns.append({
            'name': 'nim_type_style',
            'content': f"Types: {', '.join(t['name'] for t in (object_types + enum_types)[:3])}",
            'metadata': {
                'object_types': object_types,
                'enum_types': enum_types,
                'exported_count': sum(1 for t in (object_types + enum_types) if t.get('exported', False)),
                'total_count': len(object_types) + len(enum_types)
            },
            'confidence': 0.85
        })
    
    # Process variable declaration patterns
    vars_by_kind = {}
    for match in compiled_patterns['var_declaration'].finditer(content):
        extracted = NIM_PATTERNS_FOR_LEARNING['var_declaration'].extract(match)
        kind = extracted['kind']
        if kind not in vars_by_kind:
            vars_by_kind[kind] = []
        vars_by_kind[kind].append(extracted)
    
    for kind, vars_list in vars_by_kind.items():
        if vars_list:
            patterns.append({
                'name': f'nim_{kind}_style',
                'content': f"{kind} declarations: {', '.join(v['name'] for v in vars_list[:3])}",
                'metadata': {
                    'variables': vars_list[:10],
                    'kind': kind,
                    'count': len(vars_list)
                },
                'confidence': 0.8
            })
    
    # Process module structure patterns
    imports = []
    for match in compiled_patterns['module_imports'].finditer(content):
        extracted = NIM_PATTERNS_FOR_LEARNING['module_imports'].extract(match)
        imports.extend(extracted.get('modules', []))
    
    if imports:
        patterns.append({
            'name': 'nim_import_pattern',
            'content': f"Imports: {', '.join(imports[:5])}",
            'metadata': {
                'imports': imports,
                'count': len(imports)
            },
            'confidence': 0.9
        })
    
    # Process error handling patterns
    error_mechanisms = []
    for pattern_name in ['try_except', 'raise_exception']:
        for match in compiled_patterns[pattern_name].finditer(content):
            extracted = NIM_PATTERNS_FOR_LEARNING[pattern_name].extract(match)
            error_mechanisms.append(extracted)
    
    if error_mechanisms:
        patterns.append({
            'name': 'nim_error_handling',
            'content': f"Error handling mechanisms: {len(error_mechanisms)} occurrences",
            'metadata': {
                'mechanisms': error_mechanisms,
                'count': len(error_mechanisms)
            },
            'confidence': 0.85
        })
    
    # Process naming conventions
    conventions = {}
    for match in compiled_patterns['identifier_pattern'].finditer(content):
        extracted = NIM_PATTERNS_FOR_LEARNING['identifier_pattern'].extract(match)
        conv = extracted.get('convention')
        if conv and conv != 'unknown':
            conventions[conv] = conventions.get(conv, 0) + 1
    
    if conventions:
        dominant_convention = max(conventions.items(), key=lambda x: x[1])
        if dominant_convention[1] >= 5:  # Only include if we have enough examples
            patterns.append({
                'name': f'nim_naming_convention_{dominant_convention[0]}',
                'content': f"Naming convention: {dominant_convention[0]}",
                'metadata': {
                    'convention': dominant_convention[0],
                    'count': dominant_convention[1],
                    'all_conventions': conventions
                },
                'confidence': min(0.7 + (dominant_convention[1] / 20), 0.95)  # Higher confidence with more examples
            })
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "module": {
        "can_contain": ["proc", "type", "import", "variable"],
        "can_be_contained_by": []
    },
    "proc": {
        "can_contain": ["parameter", "docstring"],
        "can_be_contained_by": ["module"]
    },
    "type": {
        "can_contain": ["docstring"],
        "can_be_contained_by": ["module"]
    },
    "variable": {
        "can_contain": ["docstring"],
        "can_be_contained_by": ["module", "proc"]
    },
    "context": {
        "influences": ["explanation", "suggestion", "completion"],
        "depends_on": ["module", "proc", "type"]
    },
    "best_practice": {
        "influences": ["suggestion", "validation"],
        "applies_to": ["proc", "type", "variable"]
    },
    "common_issue": {
        "influences": ["debugging", "validation"],
        "relates_to": ["error_handling", "resource_management"]
    },
    "user_style": {
        "influences": ["completion", "suggestion"],
        "learns_from": ["naming", "formatting", "documentation"]
    }
} 