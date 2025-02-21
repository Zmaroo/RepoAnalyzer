"""
Query patterns for Verilog files.
"""

from .common import COMMON_PATTERNS

VERILOG_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "module": {
            "pattern": """
            (module_declaration
                name: (identifier) @syntax.module.name
                ports: (port_list)? @syntax.module.ports
                body: (_) @syntax.module.body) @syntax.module.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.module.name", {}).get("text", ""),
                "type": "module"
            }
        },
        "interface": {
            "pattern": """
            (interface_declaration
                name: (identifier) @syntax.interface.name
                ports: (port_list)? @syntax.interface.ports
                body: (_) @syntax.interface.body) @syntax.interface.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.interface.name", {}).get("text", ""),
                "type": "interface"
            }
        },
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: (identifier) @syntax.function.name
                    ports: (port_list)? @syntax.function.params
                    body: (_) @syntax.function.body) @syntax.function.def,
                (task_declaration
                    name: (identifier) @syntax.function.name
                    ports: (port_list)? @syntax.function.params
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
                (net_declaration
                    type: (_) @semantics.variable.type
                    name: (identifier) @semantics.variable.name) @semantics.variable.def,
                (reg_declaration
                    name: (identifier) @semantics.variable.name) @semantics.variable.def,
                (parameter_declaration
                    name: (identifier) @semantics.variable.name
                    value: (_)? @semantics.variable.value) @semantics.variable.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                "type": "variable"
            }
        },
        "type": {
            "pattern": """
            [
                (net_type_declaration
                    name: (identifier) @semantics.type.name
                    type: (_) @semantics.type.definition) @semantics.type.def,
                (enum_declaration
                    name: (identifier) @semantics.type.name
                    members: (_) @semantics.type.members) @semantics.type.def
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
                (include_compiler_directive
                    path: (string_literal) @structure.import.path) @structure.import.def,
                (package_import_declaration
                    package: (identifier) @structure.import.package) @structure.import.def
            ]
            """,
            "extract": lambda node: {
                "path": node["captures"].get("structure.import.path", {}).get("text", ""),
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