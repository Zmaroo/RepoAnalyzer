"""
Query patterns for VHDL files.
"""

from .common import COMMON_PATTERNS

VHDL_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "entity": {
            "pattern": """
            (entity_declaration
                name: (identifier) @syntax.entity.name
                ports: (port_clause)? @syntax.entity.ports) @syntax.entity.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.entity.name", {}).get("text", ""),
                "type": "entity"
            }
        },
        "architecture": {
            "pattern": """
            (architecture_body
                name: (identifier) @syntax.architecture.name
                entity: (identifier) @syntax.architecture.entity
                body: (_) @syntax.architecture.body) @syntax.architecture.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.architecture.name", {}).get("text", ""),
                "type": "architecture"
            }
        },
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list)? @syntax.function.params
                    return_type: (_) @syntax.function.return_type) @syntax.function.def,
                (procedure_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list)? @syntax.function.params) @syntax.function.def,
                (process_statement
                    name: (identifier)? @syntax.function.name
                    sensitivity_list: (_)? @syntax.function.sensitivity
                    body: (_) @syntax.function.body) @syntax.function.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "type": "function"
            }
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (signal_declaration
                    names: (identifier_list) @semantics.variable.names
                    type: (_) @semantics.variable.type) @semantics.variable.def,
                (variable_declaration
                    names: (identifier_list) @semantics.variable.names
                    type: (_) @semantics.variable.type) @semantics.variable.def,
                (constant_declaration
                    names: (identifier_list) @semantics.variable.names
                    type: (_) @semantics.variable.type
                    value: (_)? @semantics.variable.value) @semantics.variable.def
            ]
            """,
            "extract": lambda node: {
                "names": node["captures"].get("semantics.variable.names", {}).get("text", ""),
                "type": "variable"
            }
        },
        "type": {
            "pattern": """
            [
                (type_declaration
                    name: (identifier) @semantics.type.name
                    definition: (_) @semantics.type.definition) @semantics.type.def,
                (subtype_declaration
                    name: (identifier) @semantics.type.name
                    type: (_) @semantics.type.base) @semantics.type.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                "type": "type"
            }
        }
    },

    "structure": {
        "package": {
            "pattern": """
            (package_declaration
                name: (identifier) @structure.package.name) @structure.package.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("structure.package.name", {}).get("text", ""),
                "type": "package"
            }
        },
        "import": {
            "pattern": """
            [
                (library_clause
                    names: (identifier_list) @structure.import.library) @structure.import.def,
                (use_clause
                    names: (selected_name)+ @structure.import.names) @structure.import.def
            ]
            """,
            "extract": lambda node: {
                "names": node["captures"].get("structure.import.names", {}).get("text", ""),
                "type": "import"
            }
        }
    },

    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "")
            }
        }
    }
} 