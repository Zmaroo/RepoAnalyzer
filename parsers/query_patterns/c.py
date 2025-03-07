"""Query patterns for C files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose, 
    QueryPattern, PatternDefinition
)

C_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                (function_definition
                    type: (_) @syntax.function.type
                    declarator: (function_declarator
                        declarator: (_) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params)
                    body: (compound_statement) @syntax.function.body) @syntax.function
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": node["captures"].get("syntax.function.type", {}).get("text", ""),
                    "parameters": node["captures"].get("syntax.function.params", {}).get("text", ""),
                    "body": node["captures"].get("syntax.function.body", {}).get("text", "")
                },
                description="Matches C function definitions",
                examples=[
                    "void func(int x) { }",
                    "int* get_array(size_t size) { }"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "struct": QueryPattern(
                pattern="""
                (struct_specifier
                    name: (type_identifier)? @syntax.struct.name
                    body: (field_declaration_list)? @syntax.struct.body) @syntax.struct
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.struct.name", {}).get("text", ""),
                    "body": node["captures"].get("syntax.struct.body", {}).get("text", "")
                },
                description="Matches C struct definitions",
                examples=[
                    "struct Point { int x; int y; };",
                    "struct { char data[64]; } AnonymousStruct;"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "enum": QueryPattern(
                pattern="""
                (enum_specifier
                    name: (type_identifier)? @syntax.enum.name
                    body: (enumerator_list)? @syntax.enum.body
                    underlying_type: (primitive_type)? @syntax.enum.type) @syntax.enum
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.enum.name", {}).get("text", ""),
                    "body": node["captures"].get("syntax.enum.body", {}).get("text", ""),
                    "type": node["captures"].get("syntax.enum.type", {}).get("text", "")
                },
                description="Matches C enum definitions",
                examples=[
                    "enum Color { RED, GREEN, BLUE };",
                    "enum Flags : unsigned int { FLAG1 = 1, FLAG2 = 2 };"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "preprocessor": QueryPattern(
                pattern="""[
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
                extract=lambda node: {
                    "type": node["node"].type,
                    "name": node["captures"].get("structure.ifdef.name", {}).get("text", "") or 
                           node["captures"].get("structure.define.name", {}).get("text", "") or
                           node["captures"].get("structure.macro.name", {}).get("text", ""),
                    "value": node["captures"].get("structure.define.value", {}).get("text", "") or
                            node["captures"].get("structure.macro.value", {}).get("text", ""),
                    "condition": node["captures"].get("structure.if.condition", {}).get("text", "")
                },
                description="Matches C preprocessor directives",
                examples=[
                    "#ifdef DEBUG",
                    "#define MAX_SIZE 100",
                    "#define SQUARE(x) ((x) * (x))"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "include": QueryPattern(
                pattern="""
                (preproc_include
                    path: [(system_lib_string) (string_literal)] @structure.include.path) @structure.include
                """,
                extract=lambda node: {
                    "path": node["captures"].get("structure.include.path", {}).get("text", "").strip('"<>')
                },
                description="Matches C include directives",
                examples=[
                    "#include <stdio.h>",
                    "#include \"myheader.h\""
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                (declaration
                    type: (_) @semantics.variable.type
                    declarator: (init_declarator
                        declarator: (identifier) @semantics.variable.name
                        value: (_)? @semantics.variable.value)) @semantics.variable
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                    "type": node["captures"].get("semantics.variable.type", {}).get("text", ""),
                    "value": node["captures"].get("semantics.variable.value", {}).get("text", "")
                },
                description="Matches C variable declarations",
                examples=[
                    "int count = 0;",
                    "char* name = \"John\";"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "typedef": QueryPattern(
                pattern="""
                (type_definition
                    type: (_) @semantics.typedef.type
                    declarator: (_) @semantics.typedef.name) @semantics.typedef
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.typedef.name", {}).get("text", ""),
                    "type": node["captures"].get("semantics.typedef.type", {}).get("text", "")
                },
                description="Matches C typedef declarations",
                examples=[
                    "typedef int Integer;",
                    "typedef struct Point Point;"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [(comment) (comment_multiline)] @documentation.comment
                """,
                extract=lambda node: {
                    "text": node["node"].text.decode('utf8'),
                    "type": "multiline" if node["node"].type == "comment_multiline" else "single",
                    "is_doc": node["node"].text.decode('utf8').startswith(('/**', '/*!', '//!', '///<'))
                },
                description="Matches C comments",
                examples=[
                    "// Single line comment",
                    "/* Multi-line comment */",
                    "/** Documentation comment */"
                ],
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    }
}

# Repository learning patterns for C
C_PATTERNS_FOR_LEARNING = {
    PatternCategory.LEARNING: {
        PatternPurpose.LEARNING: {
            "naming_conventions": QueryPattern(
                pattern="""
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
                extract=lambda node: {
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
                },
                description="Matches C naming conventions",
                examples=[
                    "void process_data(void);",
                    "struct LinkedList { };",
                    "int maxCount;"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "error_handling": QueryPattern(
                pattern="""
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
                extract=lambda node: {
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
                },
                description="Matches C error handling patterns",
                examples=[
                    "if (ptr == NULL) { return -1; }",
                    "if (result < 0) { perror(\"Error\"); }"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "include_patterns": QueryPattern(
                pattern="""
                [
                    (preproc_include
                        path: [(system_lib_string) @include.system
                               (string_literal) @include.local]) @include
                ]
                """,
                extract=lambda node: {
                    "type": "include_pattern",
                    "is_system": "include.system" in node["captures"],
                    "is_local": "include.local" in node["captures"],
                    "path": (node["captures"].get("include.system", {}).get("text", "") or
                            node["captures"].get("include.local", {}).get("text", "")).strip('"<>')
                },
                description="Matches C include patterns",
                examples=[
                    "#include <stdio.h>",
                    "#include \"mylib.h\""
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            )
        }
    }
}

# Add the repository learning patterns to the main patterns
C_PATTERNS.update(C_PATTERNS_FOR_LEARNING) 