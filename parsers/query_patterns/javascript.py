"""JavaScript-specific Tree-sitter patterns."""

from .js_base import JS_BASE_PATTERNS

JAVASCRIPT_PATTERNS = {
    **JS_BASE_PATTERNS,
    
    # JSX patterns (specific to JavaScript with JSX)
    "jsx": """
        [
          (jsx_element
            open_tag: (jsx_opening_element
              name: (_) @jsx.tag.name
              attributes: (jsx_attribute)* @jsx.tag.attrs) @jsx.open
            children: (_)* @jsx.children
            close_tag: (jsx_closing_element) @jsx.close) @jsx,
          (jsx_self_closing_element
            name: (_) @jsx.self.name
            attributes: (jsx_attribute)* @jsx.self.attrs) @jsx.self
        ]
    """
} 