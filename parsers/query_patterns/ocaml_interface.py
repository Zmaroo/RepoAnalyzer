"""
Query patterns for OCaml interface files (.mli).

These patterns capture top-level declarations from the custom AST produced by our OCaml interface parser.
The custom parser returns an AST with a root node ("ocaml_stream") whose children have types such as
"val_declaration", "type_definition", and "module_declaration". The query patterns below use capture names
(e.g. @val_declaration) to ensure that all pertinent information is extracted.
"""

OCAML_INTERFACE_PATTERNS = [
    # Match value declarations
    "(ocaml_stream (val_declaration) @val_declaration)",
    
    # Match type definitions
    "(ocaml_stream (type_definition) @type_definition)",
    
    # Match module declarations
    "(ocaml_stream (module_declaration) @module_declaration)"
] 