"""Starlark-specific Tree-sitter patterns."""

STARLARK_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_definition
            name: (identifier) @function.name
            parameters: (parameters) @function.params
            body: (block) @function.body
            return_type: (type)? @function.return_type) @function.def,
          (lambda
            parameters: (lambda_parameters)? @lambda.params
            body: (expression) @lambda.body) @lambda.def
        ]
    """,

    # Statement patterns
    "statement": """
        [
          (if_statement
            condition: (expression) @if.condition
            consequence: (block) @if.consequence
            alternative: [
              (elif_clause) @if.elif
              (else_clause) @if.else
            ]?) @if.def,
          (for_statement
            left: (_) @for.target
            right: (expression) @for.iter
            body: (block) @for.body
            alternative: (else_clause)? @for.else) @for.def,
          (while_statement
            condition: (expression) @while.condition
            body: (block) @while.body
            alternative: (else_clause)? @while.else) @while.def
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (call
            function: (_) @call.function
            arguments: [
              (argument_list) @call.args
              (keyword_argument) @call.kwargs
            ]?) @call.def,
          (list_comprehension
            body: (_) @list_comp.body
            clauses: [
              (for_in_clause) @list_comp.for
              (if_clause) @list_comp.if
            ]*) @list_comp.def,
          (conditional_expression
            consequence: (_) @cond.then
            condition: (_) @cond.if
            alternative: (_) @cond.else) @cond.def
        ]
    """,

    # Assignment patterns
    "assignment": """
        [
          (assignment
            left: (_) @assign.target
            right: (_) @assign.value) @assign.def,
          (augmented_assignment
            left: (_) @assign.aug.target
            right: (_) @assign.aug.value) @assign.def
        ]
    """,

    # Data structure patterns
    "data_structure": """
        [
          (list
            (_)* @list.items) @list.def,
          (dictionary
            (_)* @dict.items) @dict.def,
          (tuple
            (_)* @tuple.items) @tuple.def,
          (set
            (_)* @set.items) @set.def
        ]
    """,

    # Comment patterns
    "comment": """
        [
          (comment) @comment
        ]
    """,

    # String patterns
    "string": """
        [
          (string) @string.single,
          (concatenated_string) @string.concat,
          (string_content) @string.content
        ]
    """,

    # Import patterns
    "import": """
        [
          (import_statement
            name: (dotted_name) @import.module) @import.def,
          (import_from_statement
            module_name: (dotted_name) @import.from.module
            name: (dotted_name) @import.from.name) @import.from.def
        ]
    """
} 