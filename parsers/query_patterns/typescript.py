"""TypeScript-specific Tree-sitter patterns."""

from .js_base import JS_BASE_PATTERNS
from .js_ts_shared import JS_TS_SHARED_PATTERNS

TYPESCRIPT_PATTERNS = {
    **JS_BASE_PATTERNS,

    # TypeScript-specific patterns
    "type": """
        [
          (type_alias_declaration
            name: (type_identifier) @type.name
            value: (_) @type.value) @type.def,
          (interface_declaration
            name: (type_identifier) @interface.name
            body: (object_type) @interface.body) @interface.def,
          (enum_declaration
            name: (identifier) @enum.name
            body: (enum_body) @enum.body) @enum.def
        ]
    """,

    # Type annotation patterns
    "type_annotation": """
        [
          (type_annotation
            type: (_) @type.annotation.value) @type.annotation,
          (index_signature
            type: (_) @type.index.value) @type.index,
          (property_signature
            name: (_) @type.property.name
            type: (_)? @type.property.value) @type.property
        ]
    """,

    # Generic patterns
    "generic": """
        [
          (type_parameters
            (type_parameter
              name: (type_identifier) @generic.param.name
              constraint: (_)? @generic.param.constraint
              default: (_)? @generic.param.default)*) @generic.params
        ]
    """,

    # Decorator patterns
    "decorator": """
        [
          (decorator
            name: (_) @decorator.name
            arguments: (arguments)? @decorator.args) @decorator.def
        ]
    """,

    # Include shared JSX patterns
    "jsx": JS_TS_SHARED_PATTERNS["jsx_element"]
} 