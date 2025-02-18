"""Query patterns for Erlang files."""

ERLANG_PATTERNS = {
    "syntax": {
        "function": [
            """
            (fun_decl
                clause: (_) @function.clause) @function.def
            """,
            """
            (fun_clause
                name: (_)? @function.name
                args: (expr_args) @function.params
                guard: (_)? @function.guard
                body: (clause_body) @function.body) @function.clause
            """
        ],
        "class": [
            """
            (module_attribute
                name: (_) @module.name) @class
            """
        ]
    },
    "structure": {
        "import": [
            """
            (import_attribute
                module: (_) @import.module
                functions: (_) @import.functions) @import
            """
        ],
        "namespace": [
            """
            (behaviour_attribute
                module: (_) @behaviour.module) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (variable_definition
                name: (_) @name
                value: (_) @value) @variable
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            (comment) @comment
            """
        ]
    },
    # Module patterns
    "module": """
        [
          (module_attribute
            name: (_) @module.name) @module,
          (behaviour_attribute
            module: (_) @behaviour.module) @behaviour
        ]
    """,

    # Export/Import patterns
    "export": """
        [
          (export_attribute
            functions: (_) @export.functions) @export,
          (export_type_attribute
            types: (_) @export.types) @export.type,
          (import_attribute
            module: (_) @import.module
            functions: (_) @import.functions) @import
        ]
    """,

    # Type patterns
    "type": """
        [
          (type_attribute
            name: (_) @type.name
            args: (_)? @type.args
            value: (_) @type.value) @type.def,
          (opaque
            name: (_) @type.opaque.name
            args: (_)? @type.opaque.args
            value: (_) @type.opaque.value) @type.opaque
        ]
    """,

    # Record patterns
    "record": """
        [
          (record_decl
            name: (_) @record.name
            fields: (record_field
              name: (_) @record.field.name
              ty: (_)? @record.field.type
              expr: (_)? @record.field.default)*) @record.def,
          (record_expr
            name: (_) @record.expr.name
            fields: (_)* @record.expr.fields) @record.expr
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (binary_op_expr
            lhs: (_) @expr.binary.left
            rhs: (_) @expr.binary.right) @expr.binary,
          (unary_op_expr
            operand: (_) @expr.unary.operand) @expr.unary,
          (call
            expr: (_) @expr.call.target
            args: (_) @expr.call.args) @expr.call
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (case_expr
            expr: (_) @case.expr
            clauses: (_)* @case.clauses) @case,
          (if_expr
            clauses: (_)* @if.clauses) @if,
          (receive_expr
            clauses: (_)* @receive.clauses
            after: (_)? @receive.after) @receive,
          (try_expr
            body: (_) @try.body
            clauses: (_)* @try.clauses
            after: (_)? @try.after) @try
        ]
    """,

    # List comprehension patterns
    "comprehension": """
        [
          (list_comprehension
            expr: (_) @comprehension.expr
            lc_exprs: (_) @comprehension.generators) @comprehension.list,
          (binary_comprehension
            expr: (_) @comprehension.expr
            lc_exprs: (_) @comprehension.generators) @comprehension.binary
        ]
    """,

    # Literal patterns
    "literal": """
        [
          (atom) @literal.atom,
          (char) @literal.char,
          (float) @literal.float,
          (integer) @literal.integer,
          (string) @literal.string,
          (var) @literal.variable
        ]
    """,

    # Macro patterns
    "macro": """
        [
          (macro_call_expr
            name: (_) @macro.name
            args: (_)? @macro.args) @macro.call,
          (pp_define
            name: (_) @macro.def.name
            args: (_)? @macro.def.args
            value: (_)? @macro.def.value) @macro.def
        ]
    """,

    # Attribute patterns
    "attribute": """
        [
          (feature_attribute
            feature: (_) @attr.feature.name
            flag: (_) @attr.feature.flag) @attr.feature,
          (file_attribute
            original_file: (_) @attr.file.name
            original_line: (_) @attr.file.line) @attr.file,
          (wild_attribute
            name: (_) @attr.name
            value: (_) @attr.value) @attr
        ]
    """
} 