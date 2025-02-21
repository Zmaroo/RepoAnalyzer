"""TSX-specific Tree-sitter patterns."""

from .js_ts_shared import JS_TS_SHARED_PATTERNS
from .typescript import TYPESCRIPT_PATTERNS

TSX_PATTERNS = {
    **JS_TS_SHARED_PATTERNS,  # Include shared JS/TS patterns
    **TYPESCRIPT_PATTERNS,  # Include TypeScript patterns
    
    "syntax": {
        **JS_TS_SHARED_PATTERNS.get("syntax", {}),  # Keep shared JS/TS syntax patterns
        **TYPESCRIPT_PATTERNS.get("syntax", {}),  # Keep TypeScript syntax patterns
        "jsx": {
            "pattern": """
            [
                (jsx_element
                    opening_element: (jsx_opening_element
                        name: (_) @syntax.jsx.tag.name
                        type_arguments: (type_arguments)? @syntax.jsx.type_args
                        attributes: (jsx_attributes
                            [(jsx_attribute
                                name: (jsx_attribute_name) @syntax.jsx.attr.name
                                value: (_)? @syntax.jsx.attr.value)
                             (jsx_expression) @syntax.jsx.attr.expression]*)?
                    ) @syntax.jsx.open
                    children: [
                        (jsx_text) @syntax.jsx.text
                        (jsx_expression) @syntax.jsx.expression
                        (jsx_element) @syntax.jsx.child
                        (jsx_self_closing_element) @syntax.jsx.child.self_closing
                    ]* @syntax.jsx.children
                    closing_element: (jsx_closing_element)? @syntax.jsx.close
                ) @syntax.jsx.element,
                
                (jsx_self_closing_element
                    name: (_) @syntax.jsx.self.name
                    type_arguments: (type_arguments)? @syntax.jsx.self.type_args
                    attributes: (jsx_attributes
                        [(jsx_attribute
                            name: (jsx_attribute_name) @syntax.jsx.self.attr.name
                            value: (_)? @syntax.jsx.self.attr.value)
                         (jsx_expression) @syntax.jsx.self.attr.expression]*)?
                ) @syntax.jsx.self
            ]
            """,
            "extract": lambda node: {
                "tag": node["captures"].get("syntax.jsx.tag.name", {}).get("text", "") or
                       node["captures"].get("syntax.jsx.self.name", {}).get("text", ""),
                "attributes": [
                    {
                        "name": attr.get("text", ""),
                        "value": val.get("text", "") if val else None
                    }
                    for attr, val in zip(
                        node["captures"].get("syntax.jsx.attr.name", []) +
                        node["captures"].get("syntax.jsx.self.attr.name", []),
                        node["captures"].get("syntax.jsx.attr.value", []) +
                        node["captures"].get("syntax.jsx.self.attr.value", [])
                    )
                ]
            }
        }
    },
    
    "semantics": {
        **JS_TS_SHARED_PATTERNS.get("semantics", {}),  # Keep shared JS/TS semantic patterns
        **TYPESCRIPT_PATTERNS.get("semantics", {}),  # Keep TypeScript semantic patterns
        "jsx_type": {
            "pattern": """
            [
                (jsx_opening_element
                    type_arguments: (type_arguments
                        [(type_identifier) @semantics.jsx.type.name
                         (union_type) @semantics.jsx.type.union
                         (intersection_type) @semantics.jsx.type.intersection
                         (generic_type) @semantics.jsx.type.generic]*
                    )) @semantics.jsx.type.args,
                    
                (jsx_self_closing_element
                    type_arguments: (type_arguments
                        [(type_identifier) @semantics.jsx.type.self.name
                         (union_type) @semantics.jsx.type.self.union
                         (intersection_type) @semantics.jsx.type.self.intersection
                         (generic_type) @semantics.jsx.type.self.generic]*
                    )) @semantics.jsx.type.self.args
            ]
            """,
            "extract": lambda node: {
                "type": node["captures"].get("semantics.jsx.type.name", {}).get("text", "") or
                       node["captures"].get("semantics.jsx.type.self.name", {}).get("text", ""),
                "kind": ("union" if "semantics.jsx.type.union" in node["captures"] or
                                  "semantics.jsx.type.self.union" in node["captures"] else
                        "intersection" if "semantics.jsx.type.intersection" in node["captures"] or
                                        "semantics.jsx.type.self.intersection" in node["captures"] else
                        "generic" if "semantics.jsx.type.generic" in node["captures"] or
                                   "semantics.jsx.type.self.generic" in node["captures"] else
                        "basic")
            }
        }
    }
}