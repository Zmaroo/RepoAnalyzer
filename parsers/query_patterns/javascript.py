"""JavaScript-specific Tree-sitter patterns."""

from .js_ts_shared import JS_TS_SHARED_PATTERNS

JAVASCRIPT_PATTERNS = {
    **JS_TS_SHARED_PATTERNS,  # Include shared patterns
    
    "syntax": {
        **JS_TS_SHARED_PATTERNS["syntax"],  # Keep shared syntax patterns
        "jsx": {
            "pattern": """
            [
                (jsx_element
                    opening_element: (jsx_opening_element
                        name: (_) @syntax.jsx.tag.name
                        attributes: (jsx_attributes
                            (jsx_attribute
                                name: (jsx_attribute_name) @syntax.jsx.attr.name
                                value: (_)? @syntax.jsx.attr.value)*)?
                    ) @syntax.jsx.open
                    children: (_)* @syntax.jsx.children
                    closing_element: (jsx_closing_element)? @syntax.jsx.close
                ) @syntax.jsx.element,
                
                (jsx_self_closing_element
                    name: (_) @syntax.jsx.self.name
                    attributes: (jsx_attributes
                        (jsx_attribute
                            name: (jsx_attribute_name) @syntax.jsx.self.attr.name
                            value: (_)? @syntax.jsx.self.attr.value)*)?
                ) @syntax.jsx.self
            ]
            """,
            "extract": lambda node: {
                "tag": node["captures"].get("syntax.jsx.tag.name", {}).get("text", ""),
                "attributes": [a.text.decode('utf8') for a in node["captures"].get("syntax.jsx.attr.name", [])]
            }
        }
    }
} 

# Repository learning patterns for JavaScript
JAVASCRIPT_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (function_declaration
                name: (identifier) @naming.function.name) @naming.function,
                
            (variable_declarator
                name: (identifier) @naming.variable.name) @naming.variable,
                
            (class_declaration
                name: (identifier) @naming.class.name) @naming.class,
                
            (property_identifier) @naming.property
        ]
        """,
        "extract": lambda node: {
            "type": "naming_convention_pattern",
            "entity_type": ("function" if "naming.function" in node["captures"] else
                           "variable" if "naming.variable" in node["captures"] else
                           "class" if "naming.class" in node["captures"] else
                           "property"),
            "name": (node["captures"].get("naming.function.name", {}).get("text", "") or
                    node["captures"].get("naming.variable.name", {}).get("text", "") or
                    node["captures"].get("naming.class.name", {}).get("text", "") or
                    node["captures"].get("naming.property", {}).get("text", "")),
            "is_camel_case": not "_" in (node["captures"].get("naming.function.name", {}).get("text", "") or
                                        node["captures"].get("naming.variable.name", {}).get("text", "") or
                                        node["captures"].get("naming.property", {}).get("text", "")) and
                            any(c.isupper() for c in (node["captures"].get("naming.function.name", {}).get("text", "") or
                                                     node["captures"].get("naming.variable.name", {}).get("text", "") or
                                                     node["captures"].get("naming.property", {}).get("text", ""))) and
                            (node["captures"].get("naming.function.name", {}).get("text", "") or
                             node["captures"].get("naming.variable.name", {}).get("text", "") or
                             node["captures"].get("naming.property", {}).get("text", ""))[0].islower(),
            "is_pascal_case": (node["captures"].get("naming.class.name", {}).get("text", "")) and
                             not "_" in node["captures"].get("naming.class.name", {}).get("text", "") and
                             node["captures"].get("naming.class.name", {}).get("text", "")[0].isupper()
        }
    },
    
    "jsx_patterns": {
        "pattern": """
        [
            (jsx_element
                opening_element: (jsx_opening_element
                    name: (_) @jsx.element.name)) @jsx.element,
                    
            (jsx_self_closing_element
                name: (_) @jsx.self.name) @jsx.self,
                
            (jsx_attribute
                name: (jsx_attribute_name) @jsx.attr.name
                value: (_)? @jsx.attr.value) @jsx.attr
        ]
        """,
        "extract": lambda node: {
            "type": "jsx_pattern",
            "is_component": (node["captures"].get("jsx.element.name", {}).get("text", "") or
                           node["captures"].get("jsx.self.name", {}).get("text", "")).strip() and
                          (node["captures"].get("jsx.element.name", {}).get("text", "") or
                           node["captures"].get("jsx.self.name", {}).get("text", ""))[0].isupper() if 
                           node["captures"].get("jsx.element.name", {}).get("text", "") or
                           node["captures"].get("jsx.self.name", {}).get("text", "") else False,
            "is_html_element": (node["captures"].get("jsx.element.name", {}).get("text", "") or
                              node["captures"].get("jsx.self.name", {}).get("text", "")).strip() and
                             (node["captures"].get("jsx.element.name", {}).get("text", "") or
                              node["captures"].get("jsx.self.name", {}).get("text", ""))[0].islower() if 
                              node["captures"].get("jsx.element.name", {}).get("text", "") or
                              node["captures"].get("jsx.self.name", {}).get("text", "") else False,
            "prop_name": node["captures"].get("jsx.attr.name", {}).get("text", "")
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (try_statement
                body: (statement_block) @error.try.body
                [(catch_clause
                    parameter: (identifier)? @error.catch.param
                    body: (statement_block) @error.catch.body) @error.catch
                 (finally_clause
                    body: (statement_block) @error.finally.body) @error.finally]) @error.try,
                    
            (throw_statement
                value: (_) @error.throw.value) @error.throw
        ]
        """,
        "extract": lambda node: {
            "type": "error_handling_pattern",
            "has_catch": "error.catch" in node["captures"],
            "has_finally": "error.finally" in node["captures"],
            "is_throw": "error.throw" in node["captures"],
            "error_param": node["captures"].get("error.catch.param", {}).get("text", "")
        }
    }
}

# Add the repository learning patterns to the main patterns
JAVASCRIPT_PATTERNS['REPOSITORY_LEARNING'] = JAVASCRIPT_PATTERNS_FOR_LEARNING 