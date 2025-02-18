"""Query patterns for BibTeX files."""

BIBTEX_PATTERNS = {
    "syntax": {
        "function": [
            """
            (entry
                ty: (entry_type) @entry.type
                key: [
                    (key_brace) @entry.key.brace
                    (key_paren) @entry.key.paren
                ]
                field: (field)* @entry.fields) @function
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (field
                name: (identifier) @field.name
                value: (value) @field.value) @variable
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (document
                [
                    (entry) @doc.entry
                    (string) @doc.string
                    (preamble) @doc.preamble
                    (comment) @doc.comment
                ]*) @namespace
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 