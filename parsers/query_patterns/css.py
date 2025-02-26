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

# Repository learning patterns for CSS
CSS_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (class_selector
                name: (class_name) @naming.class.name) @naming.class,
                
            (id_selector
                name: (id_name) @naming.id.name) @naming.id,
                
            (keyframes_statement
                name: (id_name) @naming.keyframes.name) @naming.keyframes,
                
            (custom_property_name) @naming.custom_property
        ]
        """,
        "extract": lambda node: {
            "type": "naming_convention_pattern",
            "entity_type": ("class" if "naming.class.name" in node["captures"] else
                          "id" if "naming.id.name" in node["captures"] else
                          "keyframes" if "naming.keyframes.name" in node["captures"] else
                          "custom_property"),
            "name": (node["captures"].get("naming.class.name", {}).get("text", "") or
                   node["captures"].get("naming.id.name", {}).get("text", "") or
                   node["captures"].get("naming.keyframes.name", {}).get("text", "") or
                   node["captures"].get("naming.custom_property", {}).get("text", "")),
            "is_kebab_case": "-" in (node["captures"].get("naming.class.name", {}).get("text", "") or
                                  node["captures"].get("naming.id.name", {}).get("text", "") or
                                  node["captures"].get("naming.keyframes.name", {}).get("text", "")),
            "is_bem_style": "__" in (node["captures"].get("naming.class.name", {}).get("text", "") or "") or
                         "--" in (node["captures"].get("naming.class.name", {}).get("text", "") or ""),
            "is_camel_case": not "-" in (node["captures"].get("naming.class.name", {}).get("text", "") or
                                      node["captures"].get("naming.id.name", {}).get("text", "") or
                                      node["captures"].get("naming.keyframes.name", {}).get("text", "")) and
                           any(c.isupper() for c in (node["captures"].get("naming.class.name", {}).get("text", "") or
                                                 node["captures"].get("naming.id.name", {}).get("text", "") or
                                                 node["captures"].get("naming.keyframes.name", {}).get("text", "")))
        }
    },
    
    "selector_complexity": {
        "pattern": """
        [
            (descendant_selector) @complexity.descendant,
            
            (child_selector) @complexity.child,
            
            (adjacent_sibling_selector) @complexity.adjacent_sibling,
            
            (general_sibling_selector) @complexity.general_sibling,
            
            (attribute_selector) @complexity.attribute,
            
            (pseudo_class_selector) @complexity.pseudo_class,
            
            (pseudo_element_selector) @complexity.pseudo_element,
            
            (class_selector) @complexity.class,
            
            (id_selector) @complexity.id
        ]
        """,
        "extract": lambda node: {
            "type": "selector_complexity_pattern",
            "uses_descendant": "complexity.descendant" in node["captures"],
            "uses_child": "complexity.child" in node["captures"],
            "uses_adjacent_sibling": "complexity.adjacent_sibling" in node["captures"],
            "uses_general_sibling": "complexity.general_sibling" in node["captures"],
            "uses_attribute": "complexity.attribute" in node["captures"],
            "uses_pseudo_class": "complexity.pseudo_class" in node["captures"],
            "uses_pseudo_element": "complexity.pseudo_element" in node["captures"],
            "selector_type": ("id" if "complexity.id" in node["captures"] else
                             "class" if "complexity.class" in node["captures"] else
                             "complex")
        }
    },
    
    "media_queries": {
        "pattern": """
        [
            (media_statement
                query: (media_query
                    [(feature_name) (value) (plain_value) (feature)]+ @media.query.features) @media.query) @media.statement
        ]
        """,
        "extract": lambda node: {
            "type": "media_query_pattern",
            "query_text": node["captures"].get("media.query", {}).get("text", ""),
            "is_responsive": any(keyword in node["captures"].get("media.query.features", {}).get("text", "").lower() for keyword in ["max-width", "min-width", "width", "device-width"]),
            "is_print": "print" in node["captures"].get("media.query", {}).get("text", "").lower(),
            "is_feature_query": "supports" in node["captures"].get("media.query", {}).get("text", "").lower() or "@supports" in node["captures"].get("media.query", {}).get("text", "").lower()
        }
    },
    
    "property_usage": {
        "pattern": """
        [
            (declaration
                name: (property_name) @property.name
                value: (property_value) @property.value) @property.declaration
        ]
        """,
        "extract": lambda node: {
            "type": "property_usage_pattern",
            "property_name": node["captures"].get("property.name", {}).get("text", ""),
            "uses_flexbox": node["captures"].get("property.name", {}).get("text", "") in ["display"] and
                          "flex" in node["captures"].get("property.value", {}).get("text", ""),
            "uses_grid": node["captures"].get("property.name", {}).get("text", "") in ["display"] and
                       "grid" in node["captures"].get("property.value", {}).get("text", ""),
            "uses_var": "var(" in node["captures"].get("property.value", {}).get("text", ""),
            "uses_calc": "calc(" in node["captures"].get("property.value", {}).get("text", ""),
            "uses_custom_property": node["captures"].get("property.name", {}).get("text", "").startswith("--")
        }
    }
}

# Add the repository learning patterns to the main patterns
CSS_PATTERNS['REPOSITORY_LEARNING'] = CSS_PATTERNS_FOR_LEARNING 