"""TypeScript-specific Tree-sitter patterns."""

from .js_base import JS_BASE_PATTERNS

TYPESCRIPT_PATTERNS = {
    **JS_BASE_PATTERNS,

    # Type definition patterns
    "type_definition": """
        [
          (type_alias_declaration
            name: (type_identifier) @type.alias.name
            value: (_) @type.alias.value) @type.alias,
          (interface_declaration
            name: (type_identifier) @interface.name
            body: (object_type) @interface.body) @interface,
          (enum_declaration
            name: (identifier) @enum.name
            body: (enum_body) @enum.body) @enum
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
              default: (_)? @generic.param.default)*) @generic.params,
          (type_arguments
            (_)* @generic.args) @generic
        ]
    """,

    # Decorator patterns
    "decorator": """
        [
          (decorator
            name: (_) @decorator.name
            arguments: (_)? @decorator.args) @decorator
        ]
    """
} 