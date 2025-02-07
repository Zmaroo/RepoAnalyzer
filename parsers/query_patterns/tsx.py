"""TSX-specific Tree-sitter patterns."""

from .js_base import JS_BASE_PATTERNS

TSX_PATTERNS = {
    **JS_BASE_PATTERNS,

    # TSX-specific patterns
    "tsx": """
        [
          (jsx_element
            open_tag: (jsx_opening_element
              name: (_) @tsx.tag.name
              type_arguments: (_)? @tsx.tag.type_args
              attributes: (jsx_attribute)* @tsx.tag.attrs) @tsx.open
            children: (_)* @tsx.children
            close_tag: (jsx_closing_element) @tsx.close) @tsx,
          (jsx_self_closing_element
            name: (_) @tsx.self.name
            type_arguments: (_)? @tsx.self.type_args
            attributes: (jsx_attribute)* @tsx.self.attrs) @tsx.self
        ]
    """
} 