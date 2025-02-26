"""Query patterns for C files."""

C_PATTERNS = {
    "syntax": {
        "function": {
            "pattern": """
            (function_definition
                type: (_) @syntax.function.type
                declarator: (function_declarator
                    declarator: (_) @syntax.function.name
                    parameters: (parameter_list) @syntax.function.params)
                body: (compound_statement) @syntax.function.body) @syntax.function
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "type": node["captures"].get("syntax.function.type", {}).get("text", ""),
                "parameters": node["captures"].get("syntax.function.params", {}).get("text", ""),
                "body": node["captures"].get("syntax.function.body", {}).get("text", "")
            }
        },
        "struct": {
            "pattern": """
            (struct_specifier
                name: (type_identifier)? @syntax.struct.name
                body: (field_declaration_list)? @syntax.struct.body) @syntax.struct
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.struct.name", {}).get("text", ""),
                "body": node["captures"].get("syntax.struct.body", {}).get("text", "")
            }
        },
        "enum": {
            "pattern": """
            (enum_specifier
                name: (type_identifier)? @syntax.enum.name
                body: (enumerator_list)? @syntax.enum.body
                underlying_type: (primitive_type)? @syntax.enum.type) @syntax.enum
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.enum.name", {}).get("text", ""),
                "body": node["captures"].get("syntax.enum.body", {}).get("text", ""),
                "type": node["captures"].get("syntax.enum.type", {}).get("text", "")
            }
        }
    },
    "structure": {
        "preprocessor": {
            "pattern": """[
                (preproc_ifdef
                    name: (identifier) @structure.ifdef.name) @structure.ifdef,
                (preproc_if
                    condition: (_) @structure.if.condition) @structure.if,
                (preproc_def
                    name: (identifier) @structure.define.name
                    value: (preproc_arg)? @structure.define.value) @structure.define,
                (preproc_function_def
                    name: (identifier) @structure.macro.name
                    parameters: (preproc_params) @structure.macro.params
                    value: (preproc_arg)? @structure.macro.value) @structure.macro
            ]""",
            "extract": lambda node: {
                "type": node["node"].type,
                "name": node["captures"].get("structure.ifdef.name", {}).get("text", "") or 
                       node["captures"].get("structure.define.name", {}).get("text", "") or
                       node["captures"].get("structure.macro.name", {}).get("text", ""),
                "value": node["captures"].get("structure.define.value", {}).get("text", "") or
                        node["captures"].get("structure.macro.value", {}).get("text", ""),
                "condition": node["captures"].get("structure.if.condition", {}).get("text", "")
            }
        },
        "include": {
            "pattern": """
            (preproc_include
                path: [(system_lib_string) (string_literal)] @structure.include.path) @structure.include
            """,
            "extract": lambda node: {
                "path": node["captures"].get("structure.include.path", {}).get("text", "").strip('"<>')
            }
        }
    },
    "semantics": {
        "variable": {
            "pattern": """
            (declaration
                type: (_) @semantics.variable.type
                declarator: (init_declarator
                    declarator: (identifier) @semantics.variable.name
                    value: (_)? @semantics.variable.value)) @semantics.variable
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                "type": node["captures"].get("semantics.variable.type", {}).get("text", ""),
                "value": node["captures"].get("semantics.variable.value", {}).get("text", "")
            }
        },
        "typedef": {
            "pattern": """
            (type_definition
                type: (_) @semantics.typedef.type
                declarator: (_) @semantics.typedef.name) @semantics.typedef
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.typedef.name", {}).get("text", ""),
                "type": node["captures"].get("semantics.typedef.type", {}).get("text", "")
            }
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            [(comment) (comment_multiline)] @documentation.comment
            """,
            "extract": lambda node: {
                "text": node["node"].text.decode('utf8'),
                "type": "multiline" if node["node"].type == "comment_multiline" else "single",
                "is_doc": node["node"].text.decode('utf8').startswith(('/**', '/*!', '//!', '///<'))
            }
        }
    }
} 

# Repository learning patterns for C
C_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (function_definition
                declarator: (function_declarator
                    declarator: (_) @naming.function.name)) @naming.function,
                    
            (struct_specifier
                name: (type_identifier) @naming.struct.name) @naming.struct,
                
            (enum_specifier
                name: (type_identifier) @naming.enum.name) @naming.enum,
                
            (declaration
                type: (_) @naming.variable.type
                declarator: (init_declarator
                    declarator: (identifier) @naming.variable.name)) @naming.variable
        ]
        """,
        "extract": lambda node: {
            "type": "naming_convention_pattern",
            "entity_type": ("function" if "naming.function.name" in node["captures"] else
                            "struct" if "naming.struct.name" in node["captures"] else
                            "enum" if "naming.enum.name" in node["captures"] else
                            "variable"),
            "name": (node["captures"].get("naming.function.name", {}).get("text", "") or
                     node["captures"].get("naming.struct.name", {}).get("text", "") or
                     node["captures"].get("naming.enum.name", {}).get("text", "") or
                     node["captures"].get("naming.variable.name", {}).get("text", "")),
            "is_snake_case": "_" in (node["captures"].get("naming.function.name", {}).get("text", "") or 
                                      node["captures"].get("naming.variable.name", {}).get("text", "")),
            "is_camel_case": not "_" in (node["captures"].get("naming.function.name", {}).get("text", "") or 
                                          node["captures"].get("naming.variable.name", {}).get("text", ""))
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (if_statement
                condition: (parenthesized_expression
                    (binary_expression
                        left: (_) @error.check.left
                        operator: (_) @error.check.op
                        right: (_) @error.check.right)) @error.check.condition
                consequence: (_) @error.check.consequence) @error.check,
                
            (call_expression
                function: (identifier) @error.handle.func
                (#match? @error.handle.func "^(exit|abort|perror|fprintf|NULL)$")
                arguments: (_) @error.handle.args) @error.handle
        ]
        """,
        "extract": lambda node: {
            "type": "error_handling_pattern",
            "is_null_check": "error.check" in node["captures"] and 
                           (node["captures"].get("error.check.op", {}).get("text", "") == "==" or 
                            node["captures"].get("error.check.op", {}).get("text", "") == "!=") and
                           ("NULL" in node["captures"].get("error.check.left", {}).get("text", "") or
                            "NULL" in node["captures"].get("error.check.right", {}).get("text", "")),
            "is_error_val": "error.check" in node["captures"] and 
                          any(val in (node["captures"].get("error.check.left", {}).get("text", "") or 
                                     node["captures"].get("error.check.right", {}).get("text", ""))
                              for val in ["-1", "NULL", "0", "EOF"]),
            "error_handler": node["captures"].get("error.handle.func", {}).get("text", "")
        }
    },
    
    "include_patterns": {
        "pattern": """
        [
            (preproc_include
                path: [(system_lib_string) @include.system
                       (string_literal) @include.local]) @include
        ]
        """,
        "extract": lambda node: {
            "type": "include_pattern",
            "is_system": "include.system" in node["captures"],
            "is_local": "include.local" in node["captures"],
            "path": (node["captures"].get("include.system", {}).get("text", "") or
                    node["captures"].get("include.local", {}).get("text", "")).strip('"<>')
        }
    }
}

# Add the repository learning patterns to the main patterns
C_PATTERNS['REPOSITORY_LEARNING'] = C_PATTERNS_FOR_LEARNING 