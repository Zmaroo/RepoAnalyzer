"""Gleam-specific Tree-sitter patterns."""

GLEAM_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_definition
            name: (identifier) @function.name
            parameters: (function_parameters) @function.params
            return_type: (_)? @function.return_type
            body: (function_body) @function.body) @function.def,
          (anonymous_function
            parameters: (function_parameters) @function.anon.params
            return_type: (_)? @function.anon.return_type
            body: (function_body) @function.anon.body) @function.anon
        ]
    """,

    # Type patterns
    "type": """
        [
          (type_definition
            name: (type_name) @type.name
            constructors: (data_constructors
              (data_constructor
                name: (constructor_name) @type.constructor.name
                arguments: (data_constructor_arguments)? @type.constructor.args)*) @type.constructors) @type.def,
          (type_alias
            name: (type_name) @type.alias.name
            value: (_) @type.alias.value) @type.alias
        ]
    """,

    # Module patterns
    "module": """
        [
          (module
            name: (_) @module.name) @module,
          (import
            module: (module) @import.module
            alias: (_)? @import.alias
            imports: (unqualified_imports)? @import.unqualified) @import
        ]
    """,

    # Record patterns
    "record": """
        [
          (record
            name: (_) @record.name
            arguments: (arguments)? @record.args) @record,
          (record_update
            constructor: (_) @record.update.constructor
            spread: (_) @record.update.spread
            arguments: (record_update_arguments) @record.update.args) @record.update
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (case
            subjects: (case_subjects) @case.subjects
            clauses: (case_clauses
              (case_clause
                patterns: (case_clause_patterns) @case.clause.patterns
                guard: (case_clause_guard)? @case.clause.guard
                value: (_) @case.clause.value)*) @case.clauses) @case
        ]
    """,

    # Variable patterns
    "variable": """
        [
          (let
            pattern: (_) @let.pattern
            type: (_)? @let.type
            value: (_) @let.value) @let,
          (let_assert
            pattern: (_) @let_assert.pattern
            type: (_)? @let_assert.type
            value: (_) @let_assert.value
            message: (_)? @let_assert.message) @let_assert
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (binary_expression
            left: (_) @expr.binary.left
            operator: (_) @expr.binary.operator
            right: (_) @expr.binary.right) @expr.binary,
          (boolean_negation
            (_) @expr.bool_neg.value) @expr.bool_neg,
          (integer_negation
            (_) @expr.int_neg.value) @expr.int_neg,
          (field_access
            record: (_) @expr.field.record
            field: (label) @expr.field.name) @expr.field
        ]
    """,

    # List patterns
    "list": """
        [
          (list
            spread: (_)? @list.spread) @list,
          (list_pattern
            assign: (_)? @list.pattern.assign) @list.pattern
        ]
    """,

    # Constant patterns
    "constant": """
        [
          (constant
            name: (identifier) @const.name
            type: (_)? @const.type
            value: (_) @const.value) @const
        ]
    """,

    # External function patterns
    "external": """
        [
          (external_function
            name: (identifier) @external.name
            parameters: (function_parameters) @external.params
            return_type: (_) @external.return_type
            body: (external_function_body) @external.body) @external.def,
          (external_type
            name: (type_name) @external.type.name) @external.type
        ]
    """
} 