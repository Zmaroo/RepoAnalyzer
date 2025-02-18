"""Variant-specific patterns for JavaScript and TypeScript."""

from .js_base import JS_BASE_PATTERNS

JS_VARIANT_PATTERNS = {
    "javascript": {
        **JS_BASE_PATTERNS,
        # Syntax category
        "function": """
            [
              (function_declaration) @syntax.function.def,
              (function_expression) @syntax.function.expr,
              (arrow_function) @syntax.function.arrow,
              (method_definition) @syntax.function.method
            ]
        """,
        
        # Structure category
        "module": """
            [
              (program
                (import_statement)* @structure.module.imports
                (export_statement)* @structure.module.exports) @structure.module
            ]
        """
    },
    
    "typescript": {
        **JS_BASE_PATTERNS,
        # Syntax category
        "function": """
            [
              (function_declaration
                type_parameters: (type_parameters)? @syntax.function.type_params) @syntax.function.def,
              (function_expression
                type_parameters: (type_parameters)? @syntax.function.type_params) @syntax.function.expr,
              (arrow_function
                type_parameters: (type_parameters)? @syntax.function.type_params) @syntax.function.arrow,
              (method_definition
                type_parameters: (type_parameters)? @syntax.function.type_params) @syntax.function.method
            ]
        """,
        
        # Structure category
        "module": """
            [
              (program
                (import_statement)* @structure.module.imports
                (export_statement)* @structure.module.exports
                (ambient_declaration)* @structure.module.ambient) @structure.module
            ]
        """
    }
}