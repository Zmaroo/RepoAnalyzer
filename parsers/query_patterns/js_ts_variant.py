JS_VARIANT_PATTERNS = {
    "javascript": {
        "function": """
            [
              (function_declaration)
              (function_expression)
              (arrow_function)
              (method_definition)
            ] @function
        """
    },
    "typescript": {
        "function": """
            [
              (function_declaration)
              (function_expression)
              (arrow_function)
              (method_definition)
            ] @function
        """
    }
}