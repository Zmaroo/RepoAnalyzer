"""MATLAB-specific Tree-sitter patterns."""

MATLAB_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_definition
            name: (identifier) @function.name
            parameters: (arguments)? @function.params
            return_values: (multioutput_variable)? @function.returns
            body: (_)* @function.body) @function.def,
          (function_call
            name: (_) @function.call.name
            arguments: (arguments)? @function.call.args) @function.call
        ]
    """,

    # Class patterns
    "class": """
        [
          (classdef_statement
            name: (identifier) @class.name
            superclasses: (_)? @class.super
            body: (_)* @class.body) @class.def,
          (properties_block
            attributes: (attributes)? @properties.attrs
            properties: (_)* @properties.list) @properties,
          (methods_block
            attributes: (attributes)? @methods.attrs
            methods: (_)* @methods.list) @methods
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (_) @if.condition
            body: (_)* @if.body
            alternatives: (_)* @if.alternatives) @if,
          (switch_statement
            expression: (_) @switch.expr
            cases: (_)* @switch.cases) @switch,
          (for_statement
            iterator: (_) @for.iterator
            body: (_)* @for.body) @for,
          (while_statement
            condition: (_) @while.condition
            body: (_)* @while.body) @while,
          (try_statement
            body: (_)* @try.body
            catch: (_)? @try.catch) @try,
          (break_statement) @break,
          (continue_statement) @continue,
          (return_statement) @return
        ]
    """,

    # Assignment patterns
    "assignment": """
        [
          (assignment
            left: (_) @assign.target
            right: (_) @assign.value) @assign
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (binary_operator
            left: (_) @expr.binary.left
            operator: (_) @expr.binary.op
            right: (_) @expr.binary.right) @expr.binary,
          (unary_operator
            operator: (_) @expr.unary.op
            operand: (_) @expr.unary.value) @expr.unary,
          (comparison_operator
            left: (_) @expr.comp.left
            operator: (_) @expr.comp.op
            right: (_) @expr.comp.right) @expr.comp
        ]
    """,

    # Matrix/Array patterns
    "matrix": """
        [
          (matrix
            rows: (_)* @matrix.rows) @matrix,
          (cell
            elements: (_)* @cell.elements) @cell,
          (range
            start: (_) @range.start
            step: (_)? @range.step
            end: (_) @range.end) @range
        ]
    """,

    # Field access patterns
    "field": """
        [
          (field_expression
            object: (_) @field.object
            field: (identifier) @field.name) @field
        ]
    """,

    # Lambda patterns
    "lambda": """
        [
          (lambda
            parameters: (_)? @lambda.params
            body: (_) @lambda.body) @lambda
        ]
    """,

    # Value patterns
    "value": """
        [
          (number) @value.number,
          (string) @value.string,
          (boolean) @value.boolean
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 