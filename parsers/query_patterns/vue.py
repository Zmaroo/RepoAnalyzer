"""Query patterns for Vue files."""

from .common import COMMON_PATTERNS

VUE_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "component": {
            "pattern": """
            (component
                (template_element
                    (start_tag)
                    (_)* @syntax.component.template
                    (end_tag))
                (script_element
                    (start_tag)
                    (_)? @syntax.component.script
                    (end_tag))
                (style_element
                    (start_tag)
                    (_)? @syntax.component.style
                    (end_tag))) @syntax.component.def
            """,
            "extract": lambda node: {
                "type": "component"
            }
        },
        "method": {
            "pattern": """
            (script_element
                (start_tag)
                (raw_text) @syntax.method.body
                (end_tag)) @syntax.method.def
            """
        }
    },
    
    "semantics": {
        "expression": {
            "pattern": """
            [
                (interpolation
                    (raw_text) @semantics.expression.value) @semantics.expression.def,
                (directive_attribute
                    name: (directive_name) @semantics.expression.name
                    value: (attribute_value) @semantics.expression.value) @semantics.expression.def
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("semantics.expression.value", {}).get("text", "")
            }
        },
        "variable": {
            "pattern": """
            (attribute
                name: (attribute_name) @semantics.variable.name
                value: (attribute_value) @semantics.variable.value) @semantics.variable.def
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            (template_element
                (start_tag)
                (_)* @structure.module.content
                (end_tag)) @structure.module.def
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    }
} 