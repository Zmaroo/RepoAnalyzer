"""Query patterns for C++ files using native tree-sitter syntax."""

from parsers.file_classification import FileType

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