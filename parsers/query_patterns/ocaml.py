"""
Query patterns for OCaml implementation files.

These patterns capture top-level declarations from the custom AST produced by our OCaml parser.
The custom parser produces an AST with a root of type "ocaml_stream" whose children have types
such as "let_binding", "type_definition", "module_declaration", "open_statement", and
"exception_declaration". The patterns below use capture names (e.g. @let_binding) so that our
downstream processing can store all key pieces of information.
"""

OCAML_PATTERNS = [
    # Match let-bindings (including recursive ones)
    "(ocaml_stream (let_binding) @let_binding)",
    
    # Match type definitions
    "(ocaml_stream (type_definition) @type_definition)",
    
    # Match module declarations
    "(ocaml_stream (module_declaration) @module_declaration)",
    
    # Match open statements
    "(ocaml_stream (open_statement) @open_statement)",
    
    # Match exception declarations
    "(ocaml_stream (exception_declaration) @exception_declaration)"
]

# Add the rest of the original patterns
OCAML_PATTERNS.extend([
    "value",
    "module",
    "type",
    "structure",
    "comment"
]) 