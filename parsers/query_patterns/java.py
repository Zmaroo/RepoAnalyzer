"""Java-specific Tree-sitter patterns."""

JAVA_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (method_declaration)
          (constructor_declaration)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (method_declaration
            modifiers: (modifiers)? @function.modifiers
            type: (_) @function.return_type
            name: (identifier) @function.name
            parameters: (formal_parameters) @function.params
            throws: (throws)? @function.throws
            body: (block) @function.body
            [
              (comment)* @function.javadoc
            ]?) @function.def,
          (constructor_declaration
            modifiers: (modifiers)? @function.modifiers
            name: (identifier) @function.name
            parameters: (formal_parameters) @function.params
            throws: (throws)? @function.throws
            body: (block) @function.body) @function.def
        ]
    """,
    # Class patterns
    "class": """
        [
          (class_declaration)
          (interface_declaration)
          (enum_declaration)
        ] @class
    """,
    "class_details": """
        [
          (class_declaration
            modifiers: (modifiers)? @class.modifiers
            name: (identifier) @class.name
            type_parameters: (type_parameters)? @class.type_params
            superclass: (superclass)? @class.extends
            interfaces: (super_interfaces)? @class.implements
            body: (class_body
              [
                (field_declaration)* @class.fields
                (method_declaration)* @class.methods
                (constructor_declaration)* @class.constructors
                (class_declaration)* @class.inner_classes
              ]
              [
                (comment)* @class.javadoc
              ]?)) @class.def,
          (interface_declaration
            modifiers: (modifiers)? @interface.modifiers
            name: (identifier) @interface.name
            type_parameters: (type_parameters)? @interface.type_params
            interfaces: (extends_interfaces)? @interface.extends
            body: (interface_body
              [
                (constant_declaration)* @interface.constants
                (method_declaration)* @interface.methods
              ])) @interface.def,
          (enum_declaration
            modifiers: (modifiers)? @enum.modifiers
            name: (identifier) @enum.name
            interfaces: (super_interfaces)? @enum.implements
            body: (enum_body
              [
                (enum_constant)* @enum.constants
                (field_declaration)* @enum.fields
                (method_declaration)* @enum.methods
              ])) @enum.def
        ]
    """,
    # Package and module patterns
    "package": """
        [
          (package_declaration
            name: (identifier) @package.name) @package,
          (module_declaration
            name: (identifier) @module.name
            body: (module_body
              [
                (requires_module_directive)* @module.requires
                (exports_module_directive)* @module.exports
                (opens_module_directive)* @module.opens
              ])) @module
        ]
    """,
    # Type patterns
    "type": """
        [
          (type_identifier) @type.name,
          (generic_type
            type: (type_identifier) @type.generic.base
            type_arguments: (type_arguments
              (_)* @type.generic.args)) @type.generic,
          (wildcard
            bound: (type_bound)? @type.wildcard.bound) @type.wildcard
        ]
    """,
    # Documentation patterns
    "documentation": """
        [
          (comment) @comment
          (line_comment) @comment.line
          (block_comment) @comment.block
          (javadoc_comment) @comment.javadoc
        ]
    """,
    "import": """
        (import_declaration
          name: (qualified_identifier) @import.name) @import
    """,
    "variable": """
        (local_variable_declaration
           (variable_declarator
             name: (identifier) @variable.name)) @variable
    """,
    "conditional": """
        (if_statement
          condition: (parenthesized_expression)? @conditional.condition
          consequence: (block) @conditional.consequence
          (else_clause (block) @conditional.alternative)?) @conditional
    """,
    "loop": """
        [
          (for_statement
            (for_init)? @loop.init
            condition: (parenthesized_expression)? @loop.condition
            (for_update)? @loop.update
            body: (block) @loop.body),
          (while_statement
            condition: (parenthesized_expression)? @loop.condition
            body: (block) @loop.body)
        ] @loop
    """,
    "lambda": """
        (lambda_expression
            parameters: (inferred_parameters)? @lambda.params
            body: (_) @lambda.body) @lambda
    """,
    "spring_annotations": """
        [
            (annotation
                name: (identifier) @spring.annotation.name
                (#match? @spring.annotation.name "^(Controller|Service|Repository|Component|Autowired|RequestMapping|GetMapping|PostMapping)$")
                arguments: (annotation_argument_list)? @spring.annotation.args) @spring.annotation,
            (class_declaration
                (modifiers
                    (annotation
                        name: (identifier) @spring.class.annotation
                        (#match? @spring.class.annotation "^(Controller|Service|Repository|Component)$")
                        arguments: (annotation_argument_list)? @spring.class.args))) @spring.class
        ]
    """
} 