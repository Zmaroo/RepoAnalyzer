"""
Query patterns for OCaml interface files (.mli).

These patterns capture top-level declarations from the custom AST produced by our OCaml interface parser.
The custom parser returns an AST with a root node ("ocaml_stream") whose children have types such as
"val_declaration", "type_definition", and "module_declaration". The query patterns below use capture names
(e.g. @val_declaration) to ensure that all pertinent information is extracted.
"""

OCAML_INTERFACE_PATTERNS = {
    "syntax": {
        "function": [
            """
            (val_declaration
                name: (identifier) @name
                type: (_) @type) @function
            """
        ],
        "class": [
            """
            (type_definition
                name: (identifier) @name
                type: (_) @type) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (module_declaration
                name: (identifier) @name
                signature: (_) @signature) @namespace
            """
        ]
    }
} 