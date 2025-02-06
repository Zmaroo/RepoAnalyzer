"""C++-specific Tree-sitter patterns."""

CPP_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_definition)
          (method_definition)
          (lambda_expression)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
        (function_definition
            type: (primitive_type)? @function.return_type
           declarator: (function_declarator
              declarator: (identifier) @function.name
              parameters: (parameter_list
                (parameter_declaration
                  type: (_) @function.param.type
                  declarator: (identifier) @function.param.name)*) @function.params)
            body: (compound_statement) @function.body) @function.def,
          (method_definition
            type: (_)? @function.return_type
            declarator: (function_declarator
              declarator: (identifier) @function.name
              parameters: (parameter_list
                (parameter_declaration
                  type: (_) @function.param.type
                  declarator: (identifier) @function.param.name)*) @function.params)
            body: (compound_statement) @function.body) @function.def,
          (lambda_expression
            captures: (lambda_capture_specifier)? @function.captures
            parameters: (parameter_list)? @function.params
            body: [
              (compound_statement) @function.body
              (expression_statement) @function.body
            ]) @function.lambda
        ]
    """,
    # Class patterns
    "class": """
        [
          (class_specifier
            name: (type_identifier) @class.name
            bases: (base_class_clause
              (base_class
                name: (type_identifier) @class.base
                access_specifier: (_)? @class.base.access)*)?
            body: (field_declaration_list
              [
                (access_specifier) @class.access
                (field_declaration
                  type: (_) @class.field.type
                  declarator: (field_identifier) @class.field.name)*
                (function_definition)* @class.methods
              ])) @class.def,
          (struct_specifier
            name: (type_identifier) @struct.name
            body: (field_declaration_list)) @struct.def
        ]
    """,
    # Template patterns
    "template": """
        [
          (template_declaration
            parameters: (template_parameter_list
              [
                (type_parameter_declaration
                  name: (type_identifier) @template.param.name)
                (parameter_declaration
                  type: (_) @template.param.type
                  declarator: (identifier) @template.param.name)
                )
              ]*) @template.params
            declaration: (_) @template.body) @template.def,
          (template_instantiation
            name: (identifier) @template.inst.name
            arguments: (template_argument_list
              (_)* @template.inst.args)) @template.inst
        ]
    """,
    # Namespace patterns
    "namespace": """
        [
          (namespace_definition
            name: (identifier) @namespace.name
            body: (declaration_list) @namespace.body) @namespace.def,
          (using_declaration
            name: (qualified_identifier) @using.name) @using,
          (using_directive
            name: (qualified_identifier) @using.namespace) @using.directive
        ]
    """,
    # Type patterns
    "type": """
        [
          (type_identifier) @type.name,
          (primitive_type) @type.primitive,
          (sized_type_specifier) @type.sized,
          (type_qualifier) @type.qualifier,
          (enum_specifier
            name: (type_identifier) @enum.name
            body: (enumerator_list
              (enumerator
                name: (identifier) @enum.value.name
                value: (_)? @enum.value.init)*)) @enum.def
        ]
    """,
    # Operator patterns
    "operator": """
        [
          (operator_name) @operator.name,
          (operator_cast
            type: (_) @operator.cast.type) @operator.cast,
          (operator_assignment) @operator.assignment,
          (operator_binary) @operator.binary,
          (operator_unary) @operator.unary
        ]
    """,
    # Exception handling patterns
    "exception": """
        [
          (try_statement
            body: (compound_statement) @try.body
            (catch_clause
              parameters: (parameter_list) @catch.params
              body: (compound_statement) @catch.body)*
            (finally_clause
              body: (compound_statement))? @finally.body) @try,
          (throw_statement
            value: (_) @throw.value) @throw
        ]
    """,
    # Memory management patterns
    "memory": """
        [
          (new_expression
            type: (_) @new.type
            arguments: (argument_list)? @new.args) @new,
          (delete_expression
            value: (_) @delete.value) @delete,
          (pointer_expression
            operator: (_) @pointer.op
            argument: (_) @pointer.arg) @pointer
        ]
    """,
    # Preprocessor patterns
    "preprocessor": """
        [
          (preproc_include
            path: (_) @include.path) @include,
          (preproc_def
            name: (identifier) @define.name
            value: (_)? @define.value) @define,
          (preproc_ifdef
            name: (identifier) @ifdef.name) @ifdef,
          (preproc_function_def
            name: (identifier) @macro.name
            parameters: (preproc_params)? @macro.params) @macro
        ]
    """,
    "modern_features": """
        [
            (concept_definition
                name: (identifier) @concept.name
                parameters: (template_parameter_list)? @concept.params
                body: (_) @concept.body) @concept,
            (requires_clause
                requirements: (_) @requires.constraints) @requires,
            (range_based_for_statement
                declarator: (_) @range.var
                range: (_) @range.expr
                body: (_) @range.body) @range,
            (fold_expression
                pack: (_) @fold.pack
                operator: (_) @fold.op) @fold,
            (structured_binding_declaration
                bindings: (identifier)* @binding.names
                value: (_) @binding.value) @binding
        ]
    """
} 