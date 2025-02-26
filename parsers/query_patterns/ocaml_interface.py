"""
Query patterns for OCaml interface files (.mli).

These patterns capture top-level declarations from the custom AST produced by our OCaml interface parser.
The custom parser returns an AST with a root node ("ocaml_stream") whose children have types such as
"val_declaration", "type_definition", and "module_declaration". The query patterns below use capture names
(e.g. @val_declaration) to ensure that all pertinent information is extracted.
"""

from typing import Dict, Any, List, Match, Optional
import re
from parsers.types import FileType, QueryPattern, PatternCategory, PatternInfo

# Language identifier
LANGUAGE = "ocaml_interface"

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

# OCaml Interface patterns specifically for repository learning
OCAML_INTERFACE_PATTERNS_FOR_LEARNING = {
    # Value declaration patterns
    'val_declaration': PatternInfo(
        pattern=r'val\s+([a-zA-Z][a-zA-Z0-9_\']*)\s*:\s*([^=]*)',
        extract=lambda match: {
            'name': match.group(1),
            'type_signature': match.group(2).strip(),
            'value_type': 'function' if '->' in match.group(2) else 'value'
        }
    ),
    
    # Type declaration patterns
    'abstract_type': PatternInfo(
        pattern=r'type\s+([a-zA-Z][a-zA-Z0-9_\']*)',
        extract=lambda match: {
            'name': match.group(1),
            'type_kind': 'abstract'
        }
    ),
    
    'concrete_type': PatternInfo(
        pattern=r'type\s+([a-zA-Z][a-zA-Z0-9_\']*)\s*=\s*([^(]*)',
        extract=lambda match: {
            'name': match.group(1),
            'definition': match.group(2).strip(),
            'type_kind': 'concrete'
        }
    ),
    
    # Module declaration patterns
    'module_type': PatternInfo(
        pattern=r'module\s+type\s+([A-Z][a-zA-Z0-9_\']*)',
        extract=lambda match: {
            'name': match.group(1),
            'module_kind': 'type'
        }
    ),
    
    'module_declaration': PatternInfo(
        pattern=r'module\s+([A-Z][a-zA-Z0-9_\']*)\s*:\s*([^=]*)',
        extract=lambda match: {
            'name': match.group(1),
            'signature': match.group(2).strip(),
            'module_kind': 'declaration'
        }
    ),
    
    # Signature structure patterns
    'signature_block': PatternInfo(
        pattern=r'sig\s*(.*?)\s*end',
        extract=lambda match: {
            'content': match.group(1),
            'type': 'signature_block'
        }
    ),
    
    'include_directive': PatternInfo(
        pattern=r'include\s+([A-Z][a-zA-Z0-9_\'\.]*)',
        extract=lambda match: {
            'module': match.group(1),
            'type': 'include'
        }
    ),
    
    # Documentation patterns
    'doc_comment': PatternInfo(
        pattern=r'\(\*\*\s*(.*?)\s*\*\)',
        extract=lambda match: {
            'content': match.group(1),
            'type': 'documentation'
        }
    ),
    
    # Naming conventions
    'identifier': PatternInfo(
        pattern=r'\b([a-zA-Z][a-zA-Z0-9_\']*)\b',
        extract=lambda match: {
            'name': match.group(1),
            'convention': 'camelCase' if match.group(1)[0].islower() and any(c.isupper() for c in match.group(1)) else
                         'snake_case' if '_' in match.group(1) and match.group(1)[0].islower() else
                         'PascalCase' if match.group(1)[0].isupper() else
                         'lowercase' if match.group(1).islower() else
                         'unknown'
        }
    )
}

# Update OCAML_INTERFACE_PATTERNS with learning patterns
OCAML_INTERFACE_PATTERNS[PatternCategory.LEARNING] = OCAML_INTERFACE_PATTERNS_FOR_LEARNING

def extract_ocaml_interface_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """
    Extract OCaml interface patterns from content for repository learning.
    
    Args:
        content: The OCaml interface content to analyze
        
    Returns:
        List of extracted patterns with metadata
    """
    patterns = []
    
    # Compile patterns
    compiled_patterns = {
        name: re.compile(pattern_info.pattern, re.DOTALL | re.MULTILINE)
        for name, pattern_info in OCAML_INTERFACE_PATTERNS_FOR_LEARNING.items()
    }
    
    # Process value declarations
    values = []
    for match in compiled_patterns['val_declaration'].finditer(content):
        extracted = OCAML_INTERFACE_PATTERNS_FOR_LEARNING['val_declaration'].extract(match)
        values.append(extracted)
    
    if values:
        function_values = [v for v in values if v['value_type'] == 'function']
        simple_values = [v for v in values if v['value_type'] == 'value']
        
        if function_values:
            patterns.append({
                'name': 'ocaml_interface_function_signatures',
                'content': f"Function signatures: {', '.join(v['name'] for v in function_values[:3])}",
                'metadata': {
                    'functions': function_values[:10],
                    'count': len(function_values)
                },
                'confidence': 0.9
            })
            
        if simple_values:
            patterns.append({
                'name': 'ocaml_interface_value_signatures',
                'content': f"Value signatures: {', '.join(v['name'] for v in simple_values[:3])}",
                'metadata': {
                    'values': simple_values[:10],
                    'count': len(simple_values)
                },
                'confidence': 0.85
            })
    
    # Process type declarations
    abstract_types = []
    for match in compiled_patterns['abstract_type'].finditer(content):
        extracted = OCAML_INTERFACE_PATTERNS_FOR_LEARNING['abstract_type'].extract(match)
        abstract_types.append(extracted)
    
    concrete_types = []
    for match in compiled_patterns['concrete_type'].finditer(content):
        extracted = OCAML_INTERFACE_PATTERNS_FOR_LEARNING['concrete_type'].extract(match)
        concrete_types.append(extracted)
    
    if abstract_types or concrete_types:
        patterns.append({
            'name': 'ocaml_interface_type_declarations',
            'content': f"Type declarations: {', '.join(t['name'] for t in (abstract_types + concrete_types)[:3])}",
            'metadata': {
                'abstract_types': abstract_types[:5],
                'concrete_types': concrete_types[:5],
                'abstract_count': len(abstract_types),
                'concrete_count': len(concrete_types)
            },
            'confidence': 0.9
        })
    
    # Process module declarations
    module_types = []
    for match in compiled_patterns['module_type'].finditer(content):
        extracted = OCAML_INTERFACE_PATTERNS_FOR_LEARNING['module_type'].extract(match)
        module_types.append(extracted)
    
    module_declarations = []
    for match in compiled_patterns['module_declaration'].finditer(content):
        extracted = OCAML_INTERFACE_PATTERNS_FOR_LEARNING['module_declaration'].extract(match)
        module_declarations.append(extracted)
    
    if module_types or module_declarations:
        patterns.append({
            'name': 'ocaml_interface_module_declarations',
            'content': f"Module declarations: {', '.join(m['name'] for m in (module_types + module_declarations)[:3])}",
            'metadata': {
                'module_types': module_types[:5],
                'module_declarations': module_declarations[:5],
                'module_type_count': len(module_types),
                'module_declaration_count': len(module_declarations)
            },
            'confidence': 0.9
        })
    
    # Process signature structures
    signature_blocks = []
    for match in compiled_patterns['signature_block'].finditer(content):
        extracted = OCAML_INTERFACE_PATTERNS_FOR_LEARNING['signature_block'].extract(match)
        signature_blocks.append(extracted)
    
    includes = []
    for match in compiled_patterns['include_directive'].finditer(content):
        extracted = OCAML_INTERFACE_PATTERNS_FOR_LEARNING['include_directive'].extract(match)
        includes.append(extracted)
    
    if signature_blocks:
        patterns.append({
            'name': 'ocaml_interface_signature_blocks',
            'content': f"Signature blocks: {len(signature_blocks)}",
            'metadata': {
                'signature_blocks': [s['content'][:50] + '...' for s in signature_blocks[:3]],
                'count': len(signature_blocks)
            },
            'confidence': 0.85
        })
    
    if includes:
        patterns.append({
            'name': 'ocaml_interface_includes',
            'content': f"Include directives: {', '.join(i['module'] for i in includes[:3])}",
            'metadata': {
                'includes': [i['module'] for i in includes],
                'count': len(includes)
            },
            'confidence': 0.8
        })
    
    # Process documentation
    doc_comments = []
    for match in compiled_patterns['doc_comment'].finditer(content):
        extracted = OCAML_INTERFACE_PATTERNS_FOR_LEARNING['doc_comment'].extract(match)
        doc_comments.append(extracted)
    
    if doc_comments:
        patterns.append({
            'name': 'ocaml_interface_documentation',
            'content': f"Documentation comments: {len(doc_comments)}",
            'metadata': {
                'doc_comments': [d['content'][:50] + '...' for d in doc_comments[:5]],
                'count': len(doc_comments)
            },
            'confidence': 0.8
        })
    
    # Process naming conventions
    conventions = {}
    for match in compiled_patterns['identifier'].finditer(content):
        extracted = OCAML_INTERFACE_PATTERNS_FOR_LEARNING['identifier'].extract(match)
        convention = extracted.get('convention')
        if convention != 'unknown':
            conventions[convention] = conventions.get(convention, 0) + 1
    
    if conventions:
        dominant = max(conventions.items(), key=lambda x: x[1])
        if dominant[1] >= 5:  # Only if we have enough examples
            patterns.append({
                'name': f'ocaml_interface_naming_convention_{dominant[0]}',
                'content': f"Naming convention: {dominant[0]}",
                'metadata': {
                    'convention': dominant[0],
                    'count': dominant[1],
                    'all_conventions': conventions
                },
                'confidence': min(0.7 + (dominant[1] / 20), 0.95)  # Higher confidence with more instances
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