"""TSX-specific Tree-sitter patterns."""

from .typescript import TYPESCRIPT_PATTERNS

TSX_PATTERNS = {
    **TYPESCRIPT_PATTERNS,  # Includes JS_BASE_PATTERNS and COMMON_PATTERNS

    # TSX-specific patterns
    "jsx_element": """
        [
          (jsx_element
            opening_element: (jsx_opening_element
              name: (_) @syntax.jsx.tag.name
              type_arguments: (_)? @syntax.jsx.type_args
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
            type_arguments: (_)? @syntax.jsx.self.type_args
            attributes: (jsx_attributes
              (jsx_attribute
                name: (jsx_attribute_name) @syntax.jsx.self.attr.name
                value: (_)? @syntax.jsx.self.attr.value)*)?
          ) @syntax.jsx.self
        ]
    """,

    "jsx_type": """
        [
          (jsx_opening_element
            type_arguments: (type_arguments
              (type_identifier) @semantics.jsx.type.name
              (union_type)? @semantics.jsx.type.union
              (intersection_type)? @semantics.jsx.type.intersection
            )) @semantics.jsx.type.args
        ]
    """
}