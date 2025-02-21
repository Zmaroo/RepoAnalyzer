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