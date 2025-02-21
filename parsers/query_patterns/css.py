"""Query patterns for CSS files."""

from .common import COMMON_PATTERNS

CSS_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "class": {
            "pattern": """
            (class_selector
                name: (class_name) @syntax.class.name) @syntax.class.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                "type": "class"
            }
        },
        "module": {
            "pattern": """
            (stylesheet
                (rule_set) @syntax.module.rules) @syntax.module.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            (declaration
                name: (property_name) @semantics.variable.name
                value: (property_value) @semantics.variable.value) @semantics.variable.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                "type": "variable"
            }
        },
        "type": {
            "pattern": """
            [
                (id_selector) @semantics.type.id,
                (type_selector) @semantics.type.element,
                (universal_selector) @semantics.type.universal
            ]
            """
        }
    },

    "structure": {
        "import": {
            "pattern": """
            [
                (import_statement
                    source: (string_value) @structure.import.path) @structure.import.def,
                (media_statement
                    query: (media_query) @structure.import.query) @structure.import.def
            ]
            """,
            "extract": lambda node: {
                "path": node["captures"].get("structure.import.path", {}).get("text", ""),
                "type": "import"
            }
        },
        "namespace": {
            "pattern": """
            (namespace_statement
                prefix: (namespace_name)? @structure.namespace.prefix
                uri: (string_value) @structure.namespace.uri) @structure.namespace.def
            """
        }
    },

    "documentation": {
        "comment": {
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