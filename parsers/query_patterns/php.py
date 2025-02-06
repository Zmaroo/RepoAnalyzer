"""PHP-specific Tree-sitter patterns."""

PHP_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_definition)
          (method_declaration)
          (arrow_function)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
        (function_definition
            name: (name) @function.name
            parameters: (formal_parameters
              (parameter_declaration
                type: (_)? @function.param.type
                name: (variable_name) @function.param.name
                default_value: (_)? @function.param.default)*) @function.params
            return_type: (_)? @function.return_type
            body: (compound_statement) @function.body
            [
              (text) @function.doc
            ]?) @function.def,
          (method_declaration
            modifiers: (member_modifier)* @function.modifiers
            name: (name) @function.name
            parameters: (formal_parameters
              (parameter_declaration
                type: (_)? @function.param.type
                name: (variable_name) @function.param.name
                default_value: (_)? @function.param.default)*) @function.params
            return_type: (_)? @function.return_type
            body: (compound_statement) @function.body
            [
              (text) @function.doc
            ]?) @function.def,
          (arrow_function
            parameters: (formal_parameters
              (parameter_declaration
                type: (_)? @function.param.type
                name: (variable_name) @function.param.name)*) @function.params
            return_type: (_)? @function.return_type
            body: (_) @function.body) @function.arrow
        ]
    """,
    # Class patterns
    "class": """
        [
          (class_declaration
            modifiers: (member_modifier)* @class.modifiers
            name: (name) @class.name
            extends: (base_clause
              (name) @class.extends)?
            implements: (class_interface_clause
              (name)* @class.implements)?
            body: (declaration_list
              [
                (field_declaration)* @class.fields
                (property_declaration)* @class.properties
                (method_declaration)* @class.methods
                (constructor_declaration)* @class.constructors
              ]
              [
                (text) @class.doc
              ]?)) @class.def
        ]
    """,
    # Interface patterns
    "interface": """
        (interface_declaration
          name: (name) @interface.name
          extends: (base_clause
            (name)* @interface.extends)?
          body: (declaration_list
            [
              (property_declaration)* @interface.properties
              (method_declaration)* @interface.methods
            ]
            [
              (text) @interface.doc
            ]?)) @interface.def
    """,
    # Trait patterns
    "trait": """
        (trait_declaration
          name: (name) @trait.name
          body: (declaration_list
            [
              (method_declaration)* @trait.methods
              (property_declaration)* @trait.properties
            ]
            [
              (text) @trait.doc
            ]?)) @trait.def
    """,
    # Namespace patterns
    "namespace": """
        [
          (namespace_definition
            name: (identifier) @namespace.name
            body: (compound_statement)? @namespace.body) @namespace.def,
          (using_declaration
            name: (qualified_name) @use.name) @use
        ]
    """,
    # Type patterns
    "type": """
        [
          (primitive_type) @type.primitive,
          (cast_type) @type.cast,
          (named_type) @type.named,
          (nullable_type) @type.nullable,
          (union_type) @type.union,
          (intersection_type) @type.intersection
        ]
    """,
    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (parenthesized_expression) @if.condition
            body: (_) @if.body
            else: (_)? @if.else) @if,
          (foreach_statement
            collection: (_) @foreach.collection
            value: (_) @foreach.value
            key: (_)? @foreach.key
            body: (_) @foreach.body) @foreach,
          (while_statement
            condition: (parenthesized_expression) @while.condition
            body: (_) @while.body) @while,
          (do_statement
            body: (_) @do.body
            condition: (parenthesized_expression) @do.condition) @do,
          (for_statement
            initializations: (_)? @for.init
            condition: (_)? @for.condition
            increments: (_)? @for.increment
            body: (_) @for.body) @for,
          (switch_statement
            condition: (parenthesized_expression) @switch.condition
            body: (switch_block
              (case_statement
                value: (_) @case.value
                body: (_)? @case.body)*
              (default_statement
                body: (_)? @default.body)?)) @switch
        ]
    """,
    # Exception handling patterns
    "exception": """
        [
          (try_statement
            body: (compound_statement) @try.body
            (catch_clause
              type: (qualified_name) @catch.type
              name: (variable_name) @catch.name
              body: (compound_statement) @catch.body)*
            (finally_clause
              body: (compound_statement))? @finally.body) @try,
          (throw_expression
            value: (_) @throw.value) @throw
        ]
    """,
    # Variable patterns
    "variable": """
        [
          (variable_name) @variable.name,
          (property_element
            name: (variable_name) @property.name) @property,
          (array_creation_expression
            elements: (array_element_initializer
              key: (_)? @array.key
              value: (_) @array.value)*) @array
        ]
    """,
    # String patterns
    "string": """
        [
          (string) @string,
          (encapsed_string
            (string_value) @string.content
            (variable_name)* @string.var) @string.complex,
          (heredoc
            (string_value) @heredoc.content) @heredoc
        ]
    """,
    "attributes": """
        [
            (attribute_list
                (attribute
                    name: (name) @attribute.name
                    arguments: (arguments)? @attribute.args)) @attribute,
            (attribute_group
                (attribute
                    name: (name) @attribute.group.name
                    arguments: (arguments)? @attribute.group.args)) @attribute.group
        ]
    """,
    "framework_patterns": """
        [
            (attribute_list
                (attribute
                    name: (name) @framework.attribute
                    (#match? @framework.attribute "^(Route|Controller|Entity|Column)$")
                    arguments: (arguments)? @framework.args)) @framework,
            (class_declaration
                (name) @controller.name
                (base_clause
                    (name) @controller.base
                    (#match? @controller.base "^.*Controller$"))) @controller
        ]
    """
} 