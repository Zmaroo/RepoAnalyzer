"""C#-specific Tree-sitter patterns."""

CSHARP_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (method_declaration)
          (constructor_declaration)
          (local_function_statement)
          (anonymous_method_expression)
          (lambda_expression)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (method_declaration
            modifiers: (modifier_list)? @function.modifiers
            type: (_) @function.return_type
            name: (identifier) @function.name
            parameters: (parameter_list
              (parameter
                type: (_) @function.param.type
                name: (identifier) @function.param.name
                default_value: (_)? @function.param.default)*) @function.params
            constraints: (type_parameter_constraints_clause)? @function.constraints
            body: (block) @function.body
            [
              (documentation_comment)* @function.doc
            ]?) @function.def,
          (constructor_declaration
            modifiers: (modifier_list)? @function.modifiers
            name: (identifier) @function.name
            parameters: (parameter_list) @function.params
            initializer: (constructor_initializer)? @function.initializer
            body: (block) @function.body) @function.def,
          (local_function_statement
            modifiers: (modifier_list)? @function.modifiers
            type: (_) @function.return_type
            name: (identifier) @function.name
            parameters: (parameter_list) @function.params
            body: (block) @function.body) @function.def
        ]
    """,
    # Class patterns
    "class": """
        [
          (class_declaration)
          (interface_declaration)
          (struct_declaration)
          (record_declaration)
        ] @class
    """,
    "class_details": """
        [
          (class_declaration
            modifiers: (modifier_list)? @class.modifiers
            name: (identifier) @class.name
            type_parameters: (type_parameter_list)? @class.type_params
            base_list: (base_list
              (base_type
                type: (identifier) @class.base)*)?
            constraints: (type_parameter_constraints_clause)? @class.constraints
            body: (declaration_list
              [
                (field_declaration)* @class.fields
                (property_declaration)* @class.properties
                (method_declaration)* @class.methods
                (constructor_declaration)* @class.constructors
              ]
              [
                (comment)* @class.doc
              ]?)) @class.def,
          (interface_declaration
            modifiers: (modifier_list)? @interface.modifiers
            name: (identifier) @interface.name
            type_parameters: (type_parameter_list)? @interface.type_params
            base_list: (base_list)? @interface.base_list
            body: (declaration_list
              [
                (property_declaration)* @interface.properties
                (method_declaration)* @interface.methods
              ])) @interface.def,
          (record_declaration
            modifiers: (modifier_list)? @record.modifiers
            name: (identifier) @record.name
            parameters: (parameter_list)? @record.params
            base_list: (base_list)? @record.base_list
            body: (declaration_list)? @record.body) @record.def
        ]
    """,
    # Namespace patterns
    "namespace": """
        [
          (namespace_declaration
            name: (qualified_name) @namespace.name
            body: (declaration_list) @namespace.body) @namespace.def,
          (using_declaration
            name: (qualified_name) @using.name
            alias: (identifier)? @using.alias) @using
        ]
    """,
    # Type patterns
    "type": """
        [
          (predefined_type) @type.predefined,
          (nullable_type
            type: (_) @type.inner) @type.nullable,
          (array_type
            type: (_) @type.element
            rank: (array_rank_specifier) @type.rank) @type.array,
          (generic_name
            type: (identifier) @type.generic.base
            arguments: (type_argument_list
              (_)* @type.generic.args)) @type.generic
        ]
    """,
    # LINQ patterns
    "linq": """
        [
          (query_expression
            (from_clause
              type: (_)? @linq.from.type
              name: (identifier) @linq.from.name
              source: (_) @linq.from.source) @linq.from
            body: (query_body
              clauses: [
                (where_clause
                  condition: (_) @linq.where.condition)? @linq.where
                (orderby_clause
                  orderings: (ordering
                    expression: (_) @linq.orderby.expr
                    direction: (_)? @linq.orderby.dir)*) @linq.orderby
                (select_clause
                  expression: (_) @linq.select.expr) @linq.select
              ]) @linq.body) @linq
        ]
    """,
    # Async/await patterns
    "async": """
        [
          (method_declaration
            modifiers: (modifier_list
              (modifier) @async.modifier
              (#eq? @async.modifier "async")) @async.modifiers) @async.method,
          (await_expression
            expression: (_) @async.awaited) @async
        ]
    """,
    # Attribute patterns
    "attribute": """
        [
          (attribute_list
            (attribute
              name: (identifier) @attribute.name
              arguments: (attribute_argument_list
                (attribute_argument
                  name: (identifier)? @attribute.arg.name
                  expression: (_) @attribute.arg.value)*) @attribute.args)) @attribute,
          (global_attribute_list
            (global_attribute
              target: (identifier) @attribute.global.target
              attribute: (attribute) @attribute.global.attr)) @attribute.global
        ]
    """,
    # Event patterns
    "event": """
        [
          (event_declaration
            modifiers: (modifier_list)? @event.modifiers
            type: (_) @event.type
            name: (identifier) @event.name
            accessors: (accessor_list)? @event.accessors) @event,
          (event_field_declaration
            modifiers: (modifier_list)? @event.field.modifiers
            type: (_) @event.field.type
            declarators: (variable_declarator
              name: (identifier) @event.field.name)*) @event.field
        ]
    """,
    # Property patterns
    "property": """
        [
          (property_declaration
            modifiers: (modifier_list)? @property.modifiers
            type: (_) @property.type
            name: (identifier) @property.name
            accessors: (accessor_list
              [
                (get_accessor_declaration)? @property.get
                (set_accessor_declaration)? @property.set
              ]) @property.accessors) @property,
          (auto_property_declaration
            modifiers: (modifier_list)? @property.auto.modifiers
            type: (_) @property.auto.type
            name: (identifier) @property.auto.name
            value: (_)? @property.auto.value) @property.auto
        ]
    """,
    # Documentation patterns
    "documentation": """
        [
          (documentation_comment) @doc.xml,
          (single_line_comment) @doc.line,
          (multiline_comment) @doc.block
        ]
    """
} 