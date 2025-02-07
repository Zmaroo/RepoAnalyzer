"""HCL-specific Tree-sitter patterns."""

HCL_PATTERNS = {
    # Block patterns
    "block": """
        [
          (block
            (identifier) @block.type
            (string_lit)* @block.labels
            (body) @block.body) @block,
          (body
            (attribute)* @body.attrs
            (block)* @body.blocks) @body
        ]
    """,

    # Attribute patterns
    "attribute": """
        [
          (attribute
            name: (identifier) @attr.name
            value: (expression) @attr.value) @attr
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (binary_operation
            left: (_) @expr.binary.left
            right: (_) @expr.binary.right) @expr.binary,
          (unary_operation
            operand: (_) @expr.unary.operand) @expr.unary,
          (conditional
            condition: (_) @expr.cond.test
            consequent: (_) @expr.cond.true
            alternative: (_) @expr.cond.false) @expr.cond
        ]
    """,

    # Function patterns
    "function": """
        [
          (function_call
            name: (identifier) @function.name
            arguments: (_)* @function.args) @function.call
        ]
    """,

    # Collection patterns
    "collection": """
        [
          (tuple
            (_)* @collection.tuple.items) @collection.tuple,
          (object
            (_)* @collection.object.items) @collection.object
        ]
    """,

    # For expression patterns
    "for": """
        [
          (for_expr
            (for_intro
              variables: (identifier)* @for.vars
              collection: (_) @for.collection)
            (for_cond)? @for.condition
            body: (_) @for.body) @for
        ]
    """,

    # Template patterns
    "template": """
        [
          (template_expr
            (template_interpolation
              (expression) @template.expr)* @template.interpolation
            (template_directive
              (expression) @template.directive.expr)* @template.directive
            (template_if
              condition: (_) @template.if.condition
              consequence: (_) @template.if.body
              alternative: (_)? @template.if.else)* @template.if
            (template_for
              intro: (_) @template.for.intro
              body: (_) @template.for.body)* @template.for) @template,
          (template_literal) @template.literal
        ]
    """,

    # Variable patterns
    "variable": """
        [
          (variable_expr
            name: (identifier) @var.name) @var
        ]
    """,

    # Splat patterns
    "splat": """
        [
          (splat
            (attr_splat)* @splat.attrs
            (full_splat)* @splat.full) @splat
        ]
    """,

    # Value patterns
    "value": """
        [
          (bool_lit) @value.bool,
          (null_lit) @value.null,
          (string_lit) @value.string,
          (identifier) @value.identifier
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 