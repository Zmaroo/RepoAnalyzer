"""Query patterns for C++ files using native tree-sitter syntax."""

from parsers.models import FileType, FileClassification

CPP_PATTERNS = {
    "syntax": {
        "function": {
            "pattern": """
            (function_definition
                type: (_) @function.return_type
                declarator: (function_declarator
                    declarator: (_) @function.name
                    parameters: (parameter_list) @function.params)
                body: (compound_statement) @function.body) @function
                
                ; Match storage and specifiers as optional captures
                (#match? @function "static|virtual|inline")?
            """,
            "extract": lambda node: {
                "name": node["captures"].get("function.name", {}).get("text", ""),
                "return_type": node["captures"].get("function.return_type", {}).get("text", ""),
                "parameters": node["captures"].get("function.params", {}).get("text", ""),
                "specifiers": [
                    spec["text"] for spec in node["node"].children 
                    if spec.type in ["static", "virtual", "inline"]
                ]
            }
        },
        "class": {
            "pattern": """
            (class_specifier
                name: (type_identifier) @class.name
                base_class_clause: (base_class_clause)? @class.bases
                body: (field_declaration_list) @class.body) @class
            """,
            "extract": lambda node: {
                "name": node["captures"].get("class.name", {}).get("text", ""),
                "bases": node["captures"].get("class.bases", {}).get("text", ""),
                "body": node["captures"].get("class.body", {}).get("text", "")
            }
        },
        "template": {
            "pattern": """
                (template_declaration
                    parameters: (template_parameter_list) @syntax.template.params
                    declaration: (_) @syntax.template.declaration) @syntax.template
            """,
            "extract": lambda node: {
                "parameters": [p.get("text", "") for p in node.get("params", [])],
                "declaration": node.get("declaration", {}).get("text", "")
            }
        }
    },
    "structure": {
        "namespace": {
            "pattern": """
            (namespace_definition
                name: (identifier) @namespace.name
                body: (declaration_list) @namespace.body) @namespace
            """,
            "extract": lambda node: {
                "name": node["captures"].get("namespace.name", {}).get("text", ""),
                "body": node["captures"].get("namespace.body", {}).get("text", "")
            }
        },
        "include": {
            "pattern": """
                (preproc_include 
                    path: (string_literal) @structure.include.path) @structure.include
            """,
            "extract": lambda node: {
                "path": node.get("path", {}).get("text", "").strip('"<>')
            }
        },
        "preprocessor": {
            "pattern": """[
                (preproc_ifdef
                    name: (identifier) @preproc.ifdef.name) @preproc.ifdef
                (preproc_def
                    name: (identifier) @preproc.def.name
                    value: (_)? @preproc.def.value) @preproc.def
            ]""",
            "extract": lambda node: {
                "type": node["node"].type,
                "name": node["captures"].get("preproc.ifdef.name", {}).get("text", "") or 
                       node["captures"].get("preproc.def.name", {}).get("text", ""),
                "value": node["captures"].get("preproc.def.value", {}).get("text", "")
            }
        }
    },
    "semantics": {
        "variable": {
            "pattern": """
                (declaration
                    type: (_) @semantics.variable.type
                    declarator: (identifier) @semantics.variable.name
                    default_value: (_)? @semantics.variable.value) @semantics.variable
            """,
            "extract": lambda node: {
                "name": node.get("name", {}).get("text", ""),
                "type": node.get("type", {}).get("text", ""),
                "value": node.get("value", {}).get("text", "")
            }
        },
        "type": {
            "pattern": """[
                (type_definition
                    type: (_) @semantics.type.original
                    name: (type_identifier) @semantics.type.alias) @semantics.type.def
                (enum_specifier
                    name: (type_identifier) @semantics.type.enum.name
                    body: (enumerator_list) @semantics.type.enum.values) @semantics.type.enum
            ]""",
            "extract": lambda node: {
                "kind": node.get("type"),
                "name": node.get("name", {}).get("text", ""),
                "values": [v.get("text", "") for v in node.get("values", [])]
            }
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            (comment) @doc.comment
            """,
            "extract": lambda node: {
                "text": node["node"].text.decode('utf8'),
                "type": "comment",
                "is_doxygen": node["node"].text.decode('utf8').startswith(('///', '//!', '/*!', '/**'))
            }
        }
    }
} 

# Repository learning patterns for C++
CPP_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (function_definition
                declarator: (function_declarator
                    declarator: (_) @naming.function.name)) @naming.function,
                    
            (class_specifier
                name: (type_identifier) @naming.class.name) @naming.class,
                
            (namespace_definition
                name: (identifier) @naming.namespace.name) @naming.namespace,
                
            (declaration
                type: (_) @naming.variable.type
                declarator: (identifier) @naming.variable.name) @naming.variable
        ]
        """,
        "extract": lambda node: {
            "type": "naming_convention_pattern",
            "entity_type": ("function" if "naming.function.name" in node["captures"] else
                           "class" if "naming.class.name" in node["captures"] else
                           "namespace" if "naming.namespace.name" in node["captures"] else
                           "variable"),
            "name": (node["captures"].get("naming.function.name", {}).get("text", "") or
                    node["captures"].get("naming.class.name", {}).get("text", "") or
                    node["captures"].get("naming.namespace.name", {}).get("text", "") or
                    node["captures"].get("naming.variable.name", {}).get("text", "")),
            "is_camel_case": not "_" in (node["captures"].get("naming.function.name", {}).get("text", "") or 
                                       node["captures"].get("naming.variable.name", {}).get("text", "")),
            "is_pascal_case": not "_" in (node["captures"].get("naming.class.name", {}).get("text", "")) and
                             (node["captures"].get("naming.class.name", {}).get("text", "").strip() and
                              node["captures"].get("naming.class.name", {}).get("text", "")[0].isupper()),
            "is_snake_case": "_" in (node["captures"].get("naming.function.name", {}).get("text", "") or 
                                   node["captures"].get("naming.variable.name", {}).get("text", ""))
        }
    },
    
    "template_usage": {
        "pattern": """
        [
            (template_declaration
                parameters: (template_parameter_list) @template.params
                declaration: (_) @template.declaration) @template.def
        ]
        """,
        "extract": lambda node: {
            "type": "template_usage_pattern",
            "parameter_count": len(node["captures"].get("template.params", {}).get("text", "").split(",")),
            "is_class_template": "class" in node["captures"].get("template.declaration", {}).get("text", ""),
            "is_function_template": "(" in node["captures"].get("template.declaration", {}).get("text", "")
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (try_statement
                body: (compound_statement) @error.try.body
                [(catch_clause
                    type: (_) @error.catch.type
                    name: (identifier)? @error.catch.name
                    body: (compound_statement) @error.catch.body) @error.catch]) @error.try,
                    
            (throw_expression
                value: (_)? @error.throw.value) @error.throw
        ]
        """,
        "extract": lambda node: {
            "type": "error_handling_pattern",
            "has_try_catch": "error.try" in node["captures"],
            "has_catch": "error.catch" in node["captures"],
            "is_throw": "error.throw" in node["captures"],
            "exception_type": node["captures"].get("error.catch.type", {}).get("text", "")
        }
    },
    
    "memory_management": {
        "pattern": """
        [
            (call_expression
                function: (identifier) @memory.allocator
                (#match? @memory.allocator "^(new|malloc|calloc|realloc)$")
                arguments: (_)? @memory.alloc.args) @memory.allocation,
                
            (call_expression
                function: (identifier) @memory.deallocator
                (#match? @memory.deallocator "^(delete|free)$")
                arguments: (_)? @memory.dealloc.args) @memory.deallocation,
                
            (destructor_name) @memory.destructor
        ]
        """,
        "extract": lambda node: {
            "type": "memory_management_pattern",
            "is_allocation": "memory.allocation" in node["captures"],
            "is_deallocation": "memory.deallocation" in node["captures"],
            "has_destructor": "memory.destructor" in node["captures"],
            "allocator": node["captures"].get("memory.allocator", {}).get("text", ""),
            "deallocator": node["captures"].get("memory.deallocator", {}).get("text", "")
        }
    }
}

# Add the repository learning patterns to the main patterns
CPP_PATTERNS['REPOSITORY_LEARNING'] = CPP_PATTERNS_FOR_LEARNING 