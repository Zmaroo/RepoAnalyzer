"""JavaScript-specific Tree-sitter patterns."""

from .js_base import JS_BASE_PATTERNS
from .js_ts_shared import JS_TS_SHARED_PATTERNS

JAVASCRIPT_PATTERNS = {
    **JS_BASE_PATTERNS,
    
    # JSX patterns (specific to JavaScript with JSX)
    "jsx": JS_TS_SHARED_PATTERNS["jsx_element"],
    
    # Additional JavaScript-specific patterns
    "object": """
        [
          (object
            (pair
              key: (_) @object.key
              value: (_) @object.value)*) @object.def,
          (object_pattern
            (shorthand_property_identifier_pattern) @object.pattern.shorthand
            (pair_pattern
              key: (_) @object.pattern.key
              value: (_) @object.pattern.value)*) @object.pattern
        ]
    """
} 