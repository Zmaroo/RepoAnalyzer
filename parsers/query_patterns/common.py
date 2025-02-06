"""Common Tree-sitter patterns shared between languages."""

# JavaScript/TypeScript shared patterns
JS_TS_SHARED_PATTERNS = {
    "function": """
        [
          ; Regular function declaration
          (function_declaration
            [
              (comment)* @function.jsdoc
            ]?
            name: (identifier) @function.name
            parameters: (formal_parameters) @function.params
            body: (statement_block) @function.body) @function.def
            
          ; Arrow function
          (arrow_function
            [
              (comment)* @function.jsdoc
            ]?
            parameters: (formal_parameters) @function.params
            body: [
              (statement_block) @function.body
              (expression) @function.body
            ]) @function.def
            
          ; Method definition
          (method_definition
            [
              (comment)* @function.jsdoc
            ]?
            name: (property_identifier) @function.name
            parameters: (formal_parameters) @function.params
            body: (statement_block) @function.body) @function.def
            
          ; Function expression
          (function_expression
            [
              (comment)* @function.jsdoc
            ]?
            name: (identifier)? @function.name
            parameters: (formal_parameters) @function.params
            body: (statement_block) @function.body) @function.def
            
          ; Object method
          (method_definition
            [
              (comment)* @function.jsdoc
            ]?
            name: (property_identifier) @function.name
            parameters: (formal_parameters) @function.params
            body: (statement_block) @function.body) @function.def

          ; Arrow function in variable declaration
          (variable_declarator
            name: (identifier) @function.name
            value: [
              (arrow_function
                [
                  (comment)* @function.jsdoc
                ]?
                parameters: (formal_parameters) @function.params
                body: [
                  (statement_block) @function.body
                  (expression) @function.body
                ]) @function.def
              (function_expression
                [
                  (comment)* @function.jsdoc
                ]?
                parameters: (formal_parameters) @function.params
                body: (statement_block) @function.body) @function.def
            ])
        ]
    """,
    "class": """
        (class_declaration
          [
            (comment)* @class.jsdoc
          ]?
          name: (identifier) @class.name
          body: (class_body [
            (method_definition
              [
                (comment)* @class.method.jsdoc
              ]?
              name: (property_identifier) @class.method.name
              parameters: (formal_parameters) @class.method.params
              body: (statement_block) @class.method.body)
            (public_field_definition
              [
                (comment)* @class.field.jsdoc
              ]?
              name: (property_identifier) @class.field.name
              value: (_)? @class.field.value)
          ]*) @class.body
          extends: (extends_clause
            value: [
              (identifier) @class.extends
              (member_expression) @class.extends
            ])?) @class.def
    """,
    "import": """
        [
          ; ES6 imports
          (import_statement
            source: (string) @import.source
            clause: [
              ; Default import
              (import_clause
                (identifier) @import.default)
              ; Named imports
              (named_imports
                (import_specifier
                  name: (identifier) @import.name
                  alias: (identifier)? @import.alias)) 
            ]) @import
            
          ; Require
          (call_expression
            function: (identifier) @import.require
            (#eq? @import.require "require")
            arguments: (arguments (string) @import.source)) @import.require
            
          ; Dynamic import
          (call_expression
            function: (import) @import.dynamic
            arguments: (arguments (string) @import.source)) @import.dynamic
        ]
    """,
    "jsx_element": """
        [
          ; JSX/TSX Element
          (jsx_element
            opening_element: (jsx_opening_element
              name: (_) @jsx.tag.name
              attributes: (jsx_attributes
                (jsx_attribute
                  name: (jsx_attribute_name) @jsx.attr.name
                  value: (_)? @jsx.attr.value)*)?
            ) @jsx.open
            children: (_)* @jsx.children
            closing_element: (jsx_closing_element)? @jsx.close
          ) @jsx.element
          
          ; JSX/TSX Fragment
          (jsx_fragment
            children: (_)* @jsx.fragment.children
          ) @jsx.fragment
          
          ; JSX/TSX Expression
          (jsx_expression
            expression: (_) @jsx.expression.value
          ) @jsx.expression
        ]
    """
} 