"""Query patterns for Nim files."""

from typing import Dict, Any, List, Match, Optional
import re
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternInfo

# Language identifier
LANGUAGE = "nim"

def extract_proc(match: Match) -> Dict[str, Any]:
    """Extract procedure information."""
    return {
        "type": "proc",
        "name": match.group(1),
        "parameters": match.group(2),
        "return_type": match.group(3),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_type(match: Match) -> Dict[str, Any]:
    """Extract type information."""
    return {
        "type": "type",
        "name": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

NIM_PATTERNS = {
    PatternCategory.SYNTAX: {
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
    
    PatternCategory.STRUCTURE: {
        "import": QueryPattern(
            pattern=r'^import\s+(.*?)(?:\s+except\s+.*)?$',
            extract=lambda m: {
                "type": "import",
                "modules": [mod.strip() for mod in m.group(1).split(',')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches import statements",
            examples=["import strutils, sequtils"]
        ),
        "module": QueryPattern(
            pattern=r'^module\s+(\w+)',
            extract=lambda m: {
                "type": "module",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches module declarations",
            examples=["module mymodule"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "docstring": QueryPattern(
            pattern=r'^##\s*(.*)$',
            extract=lambda m: {
                "type": "docstring",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches documentation strings",
            examples=["## This is a docstring"]
        ),
        "comment": QueryPattern(
            pattern=r'^#\s*(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches comments",
            examples=["# This is a comment"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "variable": QueryPattern(
            pattern=r'^(var|let|const)\s+(\w+)\*?\s*(?::\s*(\w+))?\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "variable",
                "kind": m.group(1),
                "name": m.group(2),
                "value_type": m.group(3),
                "value": m.group(4),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches variable declarations",
            examples=["var x: int = 42", "let name = \"John\""]
        ),
        "parameter": QueryPattern(
            pattern=r'(\w+)(?:\s*:\s*(\w+))?',
            extract=lambda m: {
                "type": "parameter",
                "name": m.group(1),
                "value_type": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches procedure parameters",
            examples=["x: int", "name: string"]
        )
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
    }
} 