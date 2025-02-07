"""Vue-specific Tree-sitter patterns."""

VUE_PATTERNS = {
    # Component patterns
    "component": """
        [
          (component
            (template_element)? @component.template
            (script_element)? @component.script
            (style_element)? @component.style) @component
        ]
    """,

    # Template patterns
    "template": """
        [
          (template_element
            (start_tag) @template.open
            (_)* @template.content
            (end_tag) @template.close) @template
        ]
    """,

    # Element patterns
    "element": """
        [
          (element
            (start_tag
              (tag_name) @element.name
              (attribute)* @element.attrs
              (directive_attribute)* @element.directives) @element.open
            (_)* @element.content
            (end_tag)? @element.close) @element,
          (self_closing_tag
            (tag_name) @element.name
            (attribute)* @element.attrs
            (directive_attribute)* @element.directives) @element.self_close
        ]
    """,

    # Directive patterns
    "directive": """
        [
          (directive_attribute
            name: (directive_name) @directive.name
            argument: (directive_argument)? @directive.arg
            modifiers: (directive_modifiers)? @directive.modifiers
            value: (_)? @directive.value) @directive
        ]
    """,

    # Attribute patterns
    "attribute": """
        [
          (attribute
            name: (attribute_name) @attr.name
            value: (_)? @attr.value) @attr
        ]
    """,

    # Interpolation patterns
    "interpolation": """
        [
          (interpolation
            (raw_text)? @interpolation.expr) @interpolation
        ]
    """,

    # Script patterns
    "script": """
        [
          (script_element
            (start_tag) @script.open
            (raw_text)? @script.content
            (end_tag) @script.close) @script
        ]
    """,

    # Style patterns
    "style": """
        [
          (style_element
            (start_tag) @style.open
            (raw_text)? @style.content
            (end_tag) @style.close) @style
        ]
    """
} 