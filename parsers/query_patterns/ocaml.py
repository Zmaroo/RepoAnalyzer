"""
Query patterns for OCaml implementation files.

These patterns capture top-level declarations from the custom AST produced by our OCaml parser.
The custom parser produces an AST with a root of type "ocaml_stream" whose children have types
such as "let_binding", "type_definition", "module_declaration", "open_statement", and
"exception_declaration". The patterns below use capture names (e.g. @let_binding) so that our
downstream processing can store all key pieces of information.
"""

from typing import Dict, Any, List, Match, Optional
import re
from parsers.types import FileType, QueryPattern, PatternCategory, PatternInfo
from .common import COMMON_PATTERNS

# Language identifier
LANGUAGE = "ocaml"

def extract_let_binding(match: Match) -> Dict[str, Any]:
    """Extract let binding information."""
    return {
        "type": "let_binding",
        "name": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_type_definition(match: Match) -> Dict[str, Any]:
    """Extract type definition information."""
    return {
        "type": "type_definition",
        "name": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

OCAML_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (let_binding
            pattern: (value_pattern) @syntax.function.function) @syntax.function.binding,
          
          ; Rich function patterns
          (let_binding
            rec: (rec)? @syntax.function.rec
            pattern: (value_pattern
              name: (value_name) @syntax.function.name
              parameters: [(pattern) @syntax.function.param.pattern
                         (typed_pattern
                           pattern: (pattern) @syntax.function.param.pattern
                           type: (_) @syntax.function.param.type)]* @syntax.function.params)
            type_constraint: (type_constraint
              type: (_) @syntax.function.return_type)? @syntax.function.type
            body: (_) @syntax.function.body
            attributes: (attribute)* @syntax.function.attributes) @syntax.function.def,
            
          ; Method patterns
          (method_definition
            name: (method_name) @syntax.function.method.name
            parameters: [(pattern) @syntax.function.method.param]* @syntax.function.method.params
            type_constraint: (type_constraint)? @syntax.function.method.type
            body: (_) @syntax.function.method.body) @syntax.function.method
        ]
    """,
    
    # Type patterns
    "type": """
        [
          ; Type definition patterns
          (type_definition
            params: (type_params
              params: [(type_param
                        variance: [(pos) (neg)]? @syntax.type.param.variance
                        name: (type_variable) @syntax.type.param.name)]* @syntax.type.params)?
            name: (type_constructor) @syntax.type.name
            manifest: (type_equation
              type: (_) @syntax.type.equation)? @syntax.type.manifest
            kind: [(variant_declaration
                    constructors: [(constructor_declaration
                                   name: (constructor_name) @syntax.type.variant.ctor.name
                                   arguments: [(constructor_argument
                                              type: (_) @syntax.type.variant.ctor.arg)]*) @syntax.type.variant.ctor]* @syntax.type.variant.ctors) @syntax.type.variant
                   (record_declaration
                    fields: [(field_declaration
                             mutable: (mutable)? @syntax.type.record.field.mut
                             name: (field_name) @syntax.type.record.field.name
                             type: (_) @syntax.type.record.field.type)]* @syntax.type.record.fields) @syntax.type.record]
            constraints: [(type_constraint
                          variable: (type_variable) @syntax.type.constraint.var
                          type: (_) @syntax.type.constraint.type)]* @syntax.type.constraints) @syntax.type.def,
                          
          ; Module type patterns
          (module_type_definition
            name: (module_type_name) @syntax.type.module.name
            body: (_) @syntax.type.module.body) @syntax.type.module
        ]
    """,
    
    # Module patterns
    "module": """
        [
          (module_definition
            name: (module_name) @structure.module.name
            type_constraint: (module_type_constraint
              type: (_) @structure.module.type)? @structure.module.constraint
            body: (_) @structure.module.body) @structure.module,
            
          (module_binding
            name: (module_name) @structure.module.binding.name
            body: (_) @structure.module.binding.body) @structure.module.binding,
            
          (open_statement
            module: (_) @structure.open.module) @structure.open
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": {
        "doc_comment": QueryPattern(
            pattern=r'^\s*\(\*\*\s*(.*?)\s*\*\)',
            extract=lambda m: {
                "type": "doc_comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches documentation comments",
            examples=["(** This is a doc comment *)"]
        ),
        "comment": {
            "pattern": r'^\s*\(\*\s*(.*?)\s*\*\)',
            "extract": lambda match: {
                "type": "comment",
                "content": match.group(1)
            }
        }
    },
    
    # Pattern matching patterns
    "pattern": """
        [
          (match_expression
            value: (_) @semantics.pattern.match.expr
            cases: [(match_case
                     pattern: (_) @semantics.pattern.match.pattern
                     guard: (when_clause
                       expr: (_) @semantics.pattern.match.guard)? @semantics.pattern.match.when
                     body: (_) @semantics.pattern.match.body)]*) @semantics.pattern.match,
                     
          (function_expression
            cases: [(match_case
                     pattern: (_) @semantics.pattern.function.pattern
                     body: (_) @semantics.pattern.function.body)]*) @semantics.pattern.function
        ]
    """,
    
    # Object-oriented patterns
    "object": """
        [
          (class_definition
            params: (class_params
              params: [(pattern) @syntax.object.class.param]*) @syntax.object.class.params
            name: (class_name) @syntax.object.class.name
            type_params: (type_params)? @syntax.object.class.type_params
            body: (class_body
              [(method_definition) @syntax.object.class.method
               (value_definition) @syntax.object.class.value
               (initializer_definition) @syntax.object.class.init]*) @syntax.object.class.body) @syntax.object.class,
               
          (object_expression
            body: (object_body
              [(method_definition) @syntax.object.method
               (value_definition) @syntax.object.value]*) @syntax.object.body) @syntax.object
        ]
    """,
    
    # Functor patterns
    "functor": """
        [
          (functor_definition
            params: [(functor_parameter
                      name: (module_name) @semantics.functor.param.name
                      type: (_) @semantics.functor.param.type)]* @semantics.functor.params
            body: (_) @semantics.functor.body) @semantics.functor,
            
          (functor_application
            functor: (_) @semantics.functor.app.name
            argument: (_) @semantics.functor.app.arg) @semantics.functor.app
        ]
    """,
    
    # Exception patterns
    "exception": """
        [
          (exception_definition
            name: (constructor_name) @semantics.exception.name
            arguments: [(constructor_argument
                        type: (_) @semantics.exception.arg)]*) @semantics.exception.def,
                        
          (try_expression
            body: (_) @semantics.exception.try.body
            cases: [(match_case
                     pattern: (_) @semantics.exception.try.pattern
                     body: (_) @semantics.exception.try.handler)]*) @semantics.exception.try
        ]
    """,
    
    PatternCategory.SYNTAX: {
        "let_binding": QueryPattern(
            pattern=r'^\s*(let(?:\s+rec)?\s+[a-zA-Z0-9_\'-]+)',
            extract=extract_let_binding,
            description="Matches OCaml let bindings",
            examples=["let x = 5", "let rec factorial n ="]
        ),
        "type_definition": QueryPattern(
            pattern=r'^\s*type\s+([a-zA-Z0-9_\'-]+)',
            extract=extract_type_definition,
            description="Matches type definitions",
            examples=["type person = {name: string}"]
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
            examples=["module MyModule = struct"]
        ),
        "open_statement": QueryPattern(
            pattern=r'^\s*open\s+([A-Z][a-zA-Z0-9_.]*)',
            extract=lambda m: {
                "type": "open_statement",
                "module": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches open statements",
            examples=["open List"]
        )
    },
    PatternCategory.SEMANTICS: {
        "exception_declaration": QueryPattern(
            pattern=r'^\s*exception\s+([A-Z][a-zA-Z0-9_\'-]*)',
            extract=lambda m: {
                "type": "exception_declaration",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches exception declarations",
            examples=["exception MyError"]
        )
    }
}

# OCaml patterns specifically for repository learning
OCAML_PATTERNS_FOR_LEARNING = {
    # Function/binding patterns
    'function_binding': PatternInfo(
        pattern=r'let\s+(rec\s+)?([a-zA-Z][a-zA-Z0-9_\']*)\s+([a-zA-Z][a-zA-Z0-9_\']*(?:\s+[a-zA-Z][a-zA-Z0-9_\']*)*)(?:\s*:\s*([a-zA-Z][a-zA-Z0-9_\'\s\.]*))?\s*=',
        extract=lambda match: {
            'is_recursive': bool(match.group(1)),
            'name': match.group(2),
            'parameters': [p.strip() for p in match.group(3).split()],
            'return_type': match.group(4),
            'type': 'function'
        }
    ),
    
    'value_binding': PatternInfo(
        pattern=r'let\s+([a-zA-Z][a-zA-Z0-9_\']*)\s*(?::\s*([a-zA-Z][a-zA-Z0-9_\'\s\.]*))?\s*=\s*([^=]*)',
        extract=lambda match: {
            'name': match.group(1),
            'value_type': match.group(2),
            'value': match.group(3).strip(),
            'type': 'value'
        }
    ),
    
    # Type patterns
    'record_type': PatternInfo(
        pattern=r'type\s+([a-zA-Z][a-zA-Z0-9_\']*)\s*=\s*\{\s*([^}]*)',
        extract=lambda match: {
            'name': match.group(1),
            'fields_text': match.group(2),
            'type_kind': 'record'
        }
    ),
    
    'variant_type': PatternInfo(
        pattern=r'type\s+([a-zA-Z][a-zA-Z0-9_\']*)\s*=\s*\|?\s*([A-Z][a-zA-Z0-9_\']*(?:\s+of\s+[^|]*)?(?:\s*\|\s*[A-Z][a-zA-Z0-9_\']*(?:\s+of\s+[^|]*)?)*)',
        extract=lambda match: {
            'name': match.group(1),
            'variants_text': match.group(2),
            'type_kind': 'variant'
        }
    ),
    
    # Module patterns
    'module_definition': PatternInfo(
        pattern=r'module\s+([A-Z][a-zA-Z0-9_\']*)\s*=\s*(?:struct|sig)',
        extract=lambda match: {
            'name': match.group(1),
            'module_type': 'struct' if 'struct' in match.group(0) else 'sig'
        }
    ),
    
    'open_statement': PatternInfo(
        pattern=r'open\s+([A-Z][a-zA-Z0-9_\'\.]*)',
        extract=lambda match: {
            'module': match.group(1)
        }
    ),
    
    # Pattern matching
    'match_expression': PatternInfo(
        pattern=r'match\s+([^\s]+)\s+with(?:\s*\|)?',
        extract=lambda match: {
            'matched_value': match.group(1),
            'type': 'match'
        }
    ),
    
    'function_match': PatternInfo(
        pattern=r'function(?:\s*\|)?',
        extract=lambda match: {
            'type': 'function_match'
        }
    ),
    
    # Error handling
    'try_expression': PatternInfo(
        pattern=r'try\s+([^\s]+)\s+with(?:\s*\|)?',
        extract=lambda match: {
            'tried_expression': match.group(1),
            'type': 'error_handling'
        }
    ),
    
    'exception_definition': PatternInfo(
        pattern=r'exception\s+([A-Z][a-zA-Z0-9_\']*)',
        extract=lambda match: {
            'name': match.group(1),
            'type': 'error_handling'
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

# Update OCAML_PATTERNS with learning patterns
OCAML_PATTERNS[PatternCategory.LEARNING] = OCAML_PATTERNS_FOR_LEARNING

def extract_ocaml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """
    Extract OCaml patterns from content for repository learning.
    
    Args:
        content: The OCaml content to analyze
        
    Returns:
        List of extracted patterns with metadata
    """
    patterns = []
    
    # Compile patterns
    compiled_patterns = {
        name: re.compile(pattern_info.pattern, re.DOTALL | re.MULTILINE)
        for name, pattern_info in OCAML_PATTERNS_FOR_LEARNING.items()
    }
    
    # Process function/binding patterns
    functions = []
    for match in compiled_patterns['function_binding'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['function_binding'].extract(match)
        functions.append(extracted)
    
    values = []
    for match in compiled_patterns['value_binding'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['value_binding'].extract(match)
        values.append(extracted)
    
    if functions:
        patterns.append({
            'name': 'ocaml_function_style',
            'content': f"Functions: {', '.join(f['name'] for f in functions[:3])}",
            'metadata': {
                'functions': functions[:10],
                'recursive_count': sum(1 for f in functions if f.get('is_recursive', False)),
                'total_count': len(functions)
            },
            'confidence': 0.9
        })
    
    if values:
        patterns.append({
            'name': 'ocaml_value_style',
            'content': f"Values: {', '.join(v['name'] for v in values[:3])}",
            'metadata': {
                'values': values[:10],
                'typed_count': sum(1 for v in values if v.get('value_type')),
                'total_count': len(values)
            },
            'confidence': 0.85
        })
    
    # Process type patterns
    record_types = []
    for match in compiled_patterns['record_type'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['record_type'].extract(match)
        record_types.append(extracted)
    
    variant_types = []
    for match in compiled_patterns['variant_type'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['variant_type'].extract(match)
        variant_types.append(extracted)
    
    if record_types or variant_types:
        patterns.append({
            'name': 'ocaml_type_style',
            'content': f"Types: {', '.join(t['name'] for t in (record_types + variant_types)[:3])}",
            'metadata': {
                'record_types': record_types[:5],
                'variant_types': variant_types[:5],
                'record_count': len(record_types),
                'variant_count': len(variant_types)
            },
            'confidence': 0.9
        })
    
    # Process module patterns
    modules = []
    for match in compiled_patterns['module_definition'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['module_definition'].extract(match)
        modules.append(extracted)
    
    opens = []
    for match in compiled_patterns['open_statement'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['open_statement'].extract(match)
        opens.append(extracted)
    
    if modules:
        patterns.append({
            'name': 'ocaml_module_style',
            'content': f"Modules: {', '.join(m['name'] for m in modules[:3])}",
            'metadata': {
                'modules': modules[:5],
                'count': len(modules)
            },
            'confidence': 0.9
        })
    
    if opens:
        patterns.append({
            'name': 'ocaml_open_style',
            'content': f"Open statements: {', '.join(o['module'] for o in opens[:3])}",
            'metadata': {
                'opened_modules': [o['module'] for o in opens],
                'count': len(opens)
            },
            'confidence': 0.85
        })
    
    # Process pattern matching
    match_expressions = []
    for match in compiled_patterns['match_expression'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['match_expression'].extract(match)
        match_expressions.append(extracted)
    
    function_matches = []
    for match in compiled_patterns['function_match'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['function_match'].extract(match)
        function_matches.append(extracted)
    
    if match_expressions or function_matches:
        patterns.append({
            'name': 'ocaml_pattern_matching',
            'content': f"Pattern matching: {len(match_expressions)} match expressions, {len(function_matches)} function matches",
            'metadata': {
                'match_expressions': match_expressions[:5],
                'function_matches': function_matches[:5],
                'total_count': len(match_expressions) + len(function_matches)
            },
            'confidence': 0.85
        })
    
    # Process error handling
    try_expressions = []
    for match in compiled_patterns['try_expression'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['try_expression'].extract(match)
        try_expressions.append(extracted)
    
    exceptions = []
    for match in compiled_patterns['exception_definition'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['exception_definition'].extract(match)
        exceptions.append(extracted)
    
    if try_expressions or exceptions:
        patterns.append({
            'name': 'ocaml_error_handling',
            'content': f"Error handling: {len(try_expressions)} try expressions, {len(exceptions)} exception definitions",
            'metadata': {
                'try_expressions': try_expressions[:5],
                'exceptions': exceptions[:5],
                'total_count': len(try_expressions) + len(exceptions)
            },
            'confidence': 0.85
        })
    
    # Process documentation patterns
    doc_comments = []
    for match in compiled_patterns['doc_comment'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['doc_comment'].extract(match)
        doc_comments.append(extracted)
    
    if doc_comments:
        patterns.append({
            'name': 'ocaml_documentation_style',
            'content': f"Documentation: {len(doc_comments)} doc comments",
            'metadata': {
                'doc_comments': doc_comments[:5],
                'count': len(doc_comments)
            },
            'confidence': 0.8
        })
    
    # Process naming conventions
    conventions = {}
    for match in compiled_patterns['identifier'].finditer(content):
        extracted = OCAML_PATTERNS_FOR_LEARNING['identifier'].extract(match)
        convention = extracted.get('convention')
        if convention != 'unknown':
            conventions[convention] = conventions.get(convention, 0) + 1
    
    if conventions:
        dominant = max(conventions.items(), key=lambda x: x[1])
        if dominant[1] >= 5:  # Only if we have enough examples
            patterns.append({
                'name': f'ocaml_naming_convention_{dominant[0]}',
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
    "module": {
        "can_contain": ["let_binding", "type_definition", "module_declaration", "exception_declaration"],
        "can_be_contained_by": []
    },
    "let_binding": {
        "can_contain": ["doc_comment"],
        "can_be_contained_by": ["module"]
    },
    "type_definition": {
        "can_contain": ["doc_comment"],
        "can_be_contained_by": ["module"]
    }
} 