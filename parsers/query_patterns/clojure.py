"""Tree-sitter patterns for Clojure programming language."""

CLOJURE_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (defn_declaration)
          (anonymous_function)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (defn_declaration
             name: (symbol) @function.name
             parameters: (vector) @function.params
            body: (expression) @function.body) @function.def,
          (anonymous_function
             parameters: (vector) @function.params
            body: (expression) @function.body) @function.def
        ]
    """
} 