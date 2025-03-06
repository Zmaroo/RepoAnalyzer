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
from parsers.types import FileType, QueryPattern, PatternCategory, PatternPurpose
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
        ),
        "function_binding": QueryPattern(
            pattern=r'^\s*let\s+([a-zA-Z0-9_\'-]+)\s+([a-zA-Z0-9_\'-]+(?:\s+[a-zA-Z0-9_\'-]+)*)\s*=',
            extract=lambda m: {
                "type": "function_binding",
                "name": m.group(1),
                "parameters": m.group(2).split(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches function bindings",
            examples=["let add x y ="]
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
        ),
        "include_statement": QueryPattern(
            pattern=r'^\s*include\s+([A-Z][a-zA-Z0-9_.]*)',
            extract=lambda m: {
                "type": "include_statement",
                "module": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include statements",
            examples=["include MyModule"]
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
        "match_expression": QueryPattern(
            pattern=r'^\s*match\s+([^\s]+)\s+with\s*\|?([^=]+)',
            extract=lambda m: {
                "type": "match_expression",
                "value": m.group(1),
                "patterns": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches pattern matching expressions",
            examples=["match x with | Some y -> y | None -> 0"]
        ),
        "try_expression": QueryPattern(
            pattern=r'^\s*try\s+([^\s]+)\s+with\s*\|?([^=]+)',
            extract=lambda m: {
                "type": "try_expression",
                "expression": m.group(1),
                "handlers": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches try expressions",
            examples=["try f x with | Not_found -> 0"]
        )
    },
    PatternCategory.DEPENDENCIES: {
        "external_declaration": QueryPattern(
            pattern=r'^\s*external\s+([a-zA-Z0-9_\']+)\s*:\s*([^=]+)\s*=\s*"([^"]+)"',
            extract=lambda m: {
                "type": "external_declaration",
                "name": m.group(1),
                "type_sig": m.group(2),
                "primitive": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches external declarations",
            examples=["external sqrt : float -> float = \"caml_sqrt\""]
        ),
        "module_type": QueryPattern(
            pattern=r'^\s*module\s+type\s+([A-Z][a-zA-Z0-9_\']*)\s*=\s*([A-Z][a-zA-Z0-9_\']*)',
            extract=lambda m: {
                "type": "module_type",
                "name": m.group(1),
                "definition": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches module type definitions",
            examples=["module type S = Comparable"]
        )
    },
    PatternCategory.BEST_PRACTICES: {
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
        ),
        "abstract_type": QueryPattern(
            pattern=r'^\s*type\s+([a-zA-Z0-9_\']+)(?!\s*=)',
            extract=lambda m: {
                "type": "abstract_type",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches abstract type declarations",
            examples=["type t"]
        )
    },
    PatternCategory.COMMON_ISSUES: {
        "missing_rec": QueryPattern(
            pattern=r'^\s*let\s+([a-zA-Z0-9_\']+)(?:\s+[a-zA-Z0-9_\']+)*\s*=\s*.*?\1',
            extract=lambda m: {
                "type": "missing_rec",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects potentially missing rec keyword",
            examples=["let factorial n = if n = 0 then 1 else n * factorial (n-1)"]
        ),
        "incomplete_match": QueryPattern(
            pattern=r'^\s*match\s+([^\s]+)\s+with(?!\s*\|)',
            extract=lambda m: {
                "type": "incomplete_match",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects incomplete pattern matching",
            examples=["match x with Some y -> y"]
        )
    },
    PatternCategory.USER_PATTERNS: {
        "custom_operator": QueryPattern(
            pattern=r'^\s*let\s+\(([\+\-\*/<>=@^|&]+)\)',
            extract=lambda m: {
                "type": "custom_operator",
                "operator": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom operator definitions",
            examples=["let (+++) a b = a + b + 1"]
        ),
        "labeled_argument": QueryPattern(
            pattern=r'^\s*let\s+[a-zA-Z0-9_\']+\s+~([a-zA-Z0-9_\']+)(?::\s*[^=]+)?\s*=',
            extract=lambda m: {
                "type": "labeled_argument",
                "label": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches labeled argument definitions",
            examples=["let f ~label x = x + 1"]
        )
    }
}

# Add repository learning patterns
OCAML_PATTERNS[PatternCategory.LEARNING] = {
    "module_structure": QueryPattern(
        pattern=r'^\s*module\s+([A-Z][a-zA-Z0-9_\']*)\s*=\s*struct(.*?)end',
        extract=lambda m: {
            "type": "module_structure",
            "name": m.group(1),
            "content": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches module structure patterns",
        examples=["module M = struct let x = 1 end"]
    ),
    "function_patterns": QueryPattern(
        pattern=r'^\s*let\s+([a-zA-Z0-9_\']+)\s+([a-zA-Z0-9_\']+(?:\s+[a-zA-Z0-9_\']+)*)\s*=\s*([^=]+)',
        extract=lambda m: {
            "type": "function_pattern",
            "name": m.group(1),
            "parameters": m.group(2).split(),
            "body": m.group(3),
            "is_recursive": "rec" in m.group(0),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches function definition patterns",
        examples=["let add x y = x + y"]
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
    )
}

# Function to extract patterns for repository learning
def extract_ocaml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from OCaml content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in OCAML_PATTERNS:
            category_patterns = OCAML_PATTERNS[category]
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