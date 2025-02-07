"""Nim-specific Tree-sitter patterns."""

NIM_PATTERNS = {
    # Function patterns
    "function": """
        [
          (proc_declaration
            name: (_) @function.name
            parameters: (parameter_declaration_list)? @function.params
            return_type: (type_expression)? @function.return_type
            pragmas: (pragma_list)? @function.pragmas
            body: (statement_list)? @function.body) @function.def,
          (func_expression
            parameters: (parameter_declaration_list)? @function.expr.params
            return_type: (type_expression)? @function.expr.return_type
            body: (statement_list)? @function.expr.body) @function.expr
        ]
    """,

    # Type patterns
    "type": """
        [
          (type_declaration
            name: (_) @type.name
            type: (_) @type.value) @type.def,
          (object_declaration
            name: (_) @type.object.name
            fields: (_)* @type.object.fields) @type.object,
          (enum_declaration
            name: (_) @type.enum.name
            values: (_)* @type.enum.values) @type.enum,
          (distinct_type
            name: (_) @type.distinct.name
            base: (_) @type.distinct.base) @type.distinct
        ]
    """,

    # Iterator patterns
    "iterator": """
        [
          (iterator_declaration
            name: (_) @iterator.name
            parameters: (parameter_declaration_list)? @iterator.params
            return_type: (type_expression)? @iterator.return_type
            pragmas: (pragma_list)? @iterator.pragmas
            body: (statement_list)? @iterator.body) @iterator.def,
          (iterator_expression
            parameters: (parameter_declaration_list)? @iterator.expr.params
            return_type: (type_expression)? @iterator.expr.return_type
            body: (statement_list)? @iterator.expr.body) @iterator.expr
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if
            condition: (_) @if.condition
            body: (_) @if.body
            alternative: (_)? @if.alternative) @if,
          (when
            condition: (_) @when.condition
            body: (_) @when.body) @when,
          (case
            value: (_) @case.value
            branches: (of_branch)* @case.branches) @case,
          (for
            variables: (_) @for.vars
            iterators: (_) @for.iterators
            body: (_) @for.body) @for,
          (while
            condition: (_) @while.condition
            body: (_) @while.body) @while,
          (try
            body: (_) @try.body
            except_branches: (except_branch)* @try.except
            finally_branch: (finally_branch)? @try.finally) @try
        ]
    """,

    # Variable patterns
    "variable": """
        [
          (var_section
            (variable_declaration
              name: (_) @var.name
              type: (_)? @var.type
              value: (_)? @var.value)*) @var.section,
          (let_section
            (variable_declaration
              name: (_) @let.name
              type: (_)? @let.type
              value: (_)? @let.value)*) @let.section,
          (const_section
            (variable_declaration
              name: (_) @const.name
              type: (_)? @const.type
              value: (_)? @const.value)*) @const.section
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (infix_expression
            left: (_) @expr.infix.left
            operator: (_) @expr.infix.op
            right: (_) @expr.infix.right) @expr.infix,
          (prefix_expression
            operator: (_) @expr.prefix.op
            operand: (_) @expr.prefix.operand) @expr.prefix,
          (dot_expression
            left: (_) @expr.dot.left
            right: (_) @expr.dot.right) @expr.dot
        ]
    """,

    # Template patterns
    "template": """
        [
          (template_declaration
            name: (_) @template.name
            parameters: (parameter_declaration_list)? @template.params
            pragmas: (pragma_list)? @template.pragmas
            body: (statement_list)? @template.body) @template.def
        ]
    """,

    # Macro patterns
    "macro": """
        [
          (macro_declaration
            name: (_) @macro.name
            parameters: (parameter_declaration_list)? @macro.params
            pragmas: (pragma_list)? @macro.pragmas
            body: (statement_list)? @macro.body) @macro.def
        ]
    """,

    # Pragma patterns
    "pragma": """
        [
          (pragma_list
            (_)* @pragma.items) @pragma,
          (pragma_expression
            name: (_) @pragma.expr.name
            arguments: (_)* @pragma.expr.args) @pragma.expr
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 