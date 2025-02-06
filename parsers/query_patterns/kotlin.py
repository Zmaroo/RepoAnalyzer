"""Kotlin-specific Tree-sitter patterns."""

KOTLIN_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_declaration)
          (lambda_literal)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
        (function_declaration
           name: (simple_identifier) @function.name
            parameters: (parameter_list) @function.params
            body: (function_body) @function.body) @function.def,
          (lambda_literal
            parameters: (parameter_list)? @function.params
            body: (statements) @function.body) @function.def
        ]
    """,
    # Class patterns
    "class": """
        [
          (class_declaration
            modifiers: (modifiers)? @class.modifiers
            name: (simple_identifier) @class.name
            type_parameters: (type_parameters)? @class.type_params
            primary_constructor: (primary_constructor)? @class.constructor
            delegation_specifiers: (delegation_specifiers)? @class.delegation
            class_body: (class_body)? @class.body) @class.def
        ]
    """,
    # Interface patterns
    "interface": """
        [
          (interface_declaration
            modifiers: (modifiers)? @interface.modifiers
            name: (simple_identifier) @interface.name
            type_parameters: (type_parameters)? @interface.type_params
            delegation_specifiers: (delegation_specifiers)? @interface.delegation
            class_body: (class_body)? @interface.body) @interface.def
        ]
    """,
    # Property patterns
    "property": """
        [
          (property_declaration
            modifiers: (modifiers)? @property.modifiers
            var_or_val: (_) @property.kind
            name: (simple_identifier) @property.name
            type: (type)? @property.type
            expression: (_)? @property.initializer
            property_delegate: (property_delegate)? @property.delegate) @property.def
        ]
    """,
    # Constructor patterns
    "constructor": """
        [
          (primary_constructor
            modifiers: (modifiers)? @constructor.modifiers
            class_parameters: (class_parameters)? @constructor.params) @constructor.primary,
          (secondary_constructor
            modifiers: (modifiers)? @constructor.secondary.modifiers
            parameters: (parameter_list) @constructor.secondary.params
            delegation_call: (constructor_delegation_call)? @constructor.secondary.delegation
            body: (statements)? @constructor.secondary.body) @constructor.secondary
        ]
    """,
    # Coroutine patterns
    "coroutines": """
        [
            (function_declaration
                modifiers: (modifiers
                    (annotation
                        (#match? @annotation.name "^Suspend$"))) @coroutine.modifiers
                name: (simple_identifier) @coroutine.name
                body: (function_body) @coroutine.body) @coroutine,
            (call_expression
                function: [
                    (simple_identifier) @coroutine.launch
                    (#match? @coroutine.launch "^(launch|async|withContext)$")
                ]
                lambda: (lambda_literal) @coroutine.block) @coroutine.call
        ]
    """,
    # DSL patterns
    "dsl": """
        [
            (class_declaration
                modifiers: (modifiers
                    (annotation
                        (#match? @annotation.name "^DslMarker$"))) @dsl.marker
                name: (simple_identifier) @dsl.name
                body: (class_body) @dsl.body) @dsl.class,
            (function_declaration
                modifiers: (modifiers
                    (annotation
                        (#match? @annotation.name "^BuilderDsl$"))) @dsl.builder.modifiers
                name: (simple_identifier) @dsl.builder.name
                body: (function_body) @dsl.builder.body) @dsl.builder
        ]
    """,
    # Spring patterns
    "spring": """
        [
            (class_declaration
                modifiers: (modifiers
                    (annotation
                        (#match? @annotation.name "^(Controller|Service|Repository|Component)$"))) @spring.component.type
                name: (simple_identifier) @spring.component.name) @spring.component,
            (function_declaration
                modifiers: (modifiers
                    (annotation
                        (#match? @annotation.name "^(GetMapping|PostMapping|PutMapping|DeleteMapping)$"))) @spring.endpoint.type
                name: (simple_identifier) @spring.endpoint.name) @spring.endpoint
        ]
    """,
    # Control flow patterns
    "control_flow": """
        [
          (if_expression
            condition: (_) @if.condition
            body: (_) @if.body
            else: (_)? @if.else) @if,
          (when_expression
            subject: (_)? @when.subject
            entries: (when_entry
              conditions: (_)* @when.condition
              body: (_) @when.body)*) @when,
          (for_statement
            variables: (_) @for.vars
            range: (_) @for.range
            body: (_) @for.body) @for,
          (while_statement
            condition: (_) @while.condition
            body: (_) @while.body) @while
        ]
    """,
    # Type patterns
    "type": """
        [
          (type_alias
            modifiers: (modifiers)? @type.alias.modifiers
            name: (simple_identifier) @type.alias.name
            type_parameters: (type_parameters)? @type.alias.type_params
            type: (type) @type.alias.type) @type.alias,
          (object_declaration
            modifiers: (modifiers)? @type.object.modifiers
            name: (simple_identifier) @type.object.name
            delegation_specifiers: (delegation_specifiers)? @type.object.delegation
            class_body: (class_body)? @type.object.body) @type.object
        ]
    """,
    # Extension patterns
    "extension": """
        [
          (function_declaration
            modifiers: (modifiers)? @extension.modifiers
            receiver_type: (type) @extension.receiver
            name: (simple_identifier) @extension.name
            parameters: (parameter_list) @extension.params
            body: (function_body) @extension.body) @extension.function
        ]
    """
} 