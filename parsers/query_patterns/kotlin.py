"""Kotlin-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

KOTLIN_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_declaration) @syntax.function,
          
          ; Rich function patterns
          (function_declaration
            modifiers: [(public) (private) (protected) (internal) (override) (suspend) (inline) (tailrec)]* @syntax.function.modifier
            name: (simple_identifier) @syntax.function.name
            type_parameters: (type_parameters
              (type_parameter
                modifiers: [(reified)]* @syntax.function.type_param.modifier
                name: (type_identifier) @syntax.function.type_param.name
                type_constraints: (type_constraints
                  (type_constraint
                    type: (_) @syntax.function.type_param.constraint))*) @syntax.function.type_param)* @syntax.function.type_params
            value_parameters: (value_parameters
              (parameter
                modifiers: [(vararg) (noinline) (crossinline)]* @syntax.function.param.modifier
                name: (simple_identifier) @syntax.function.param.name
                type: (_) @syntax.function.param.type
                default_value: (_)? @syntax.function.param.default)*) @syntax.function.params
            type: (type_reference)? @syntax.function.return_type
            body: [(block) (expression)]? @syntax.function.body) @syntax.function.def,
            
          ; Property accessor methods
          (getter
            modifiers: [(public) (private) (protected) (internal)]* @syntax.function.getter.modifier
            body: [(block) (expression)]? @syntax.function.getter.body) @syntax.function.getter,
            
          (setter
            modifiers: [(public) (private) (protected) (internal)]* @syntax.function.setter.modifier
            parameter: (parameter)? @syntax.function.setter.param
            body: [(block) (expression)]? @syntax.function.setter.body) @syntax.function.setter
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_declaration) @syntax.class,
          
          ; Rich class patterns
          (class_declaration
            modifiers: [(public) (private) (protected) (internal) (abstract) (final) (sealed) (inner) (data)]* @syntax.class.modifier
            name: (type_identifier) @syntax.class.name
            type_parameters: (type_parameters)? @syntax.class.type_params
            primary_constructor: (class_parameters
              (class_parameter
                modifiers: [(public) (private) (protected) (internal) (override) (val) (var)]* @syntax.class.constructor.param.modifier
                name: (simple_identifier) @syntax.class.constructor.param.name
                type: (_) @syntax.class.constructor.param.type
                default_value: (_)? @syntax.class.constructor.param.default)*) @syntax.class.constructor
            delegation_specifiers: (delegation_specifiers
              [(constructor_invocation) @syntax.class.super.constructor
               (user_type) @syntax.class.implements]*) @syntax.class.delegation
            body: (class_body
              [(property_declaration) @syntax.class.property
               (function_declaration) @syntax.class.method
               (class_declaration) @syntax.class.nested
               (object_declaration) @syntax.class.companion]*) @syntax.class.body) @syntax.class.def,
               
          ; Interface patterns
          (interface_declaration
            modifiers: [(public) (private) (protected) (internal)]* @syntax.interface.modifier
            name: (type_identifier) @syntax.interface.name
            type_parameters: (type_parameters)? @syntax.interface.type_params
            delegation_specifiers: (delegation_specifiers)? @syntax.interface.extends
            body: (class_body) @syntax.interface.body) @syntax.interface.def
        ]
    """,
    
    # Structure category with rich patterns
    "package": """
        [
          (package_header
            identifier: (identifier) @structure.package.name) @structure.package,
            
          (import_header
            identifier: (identifier) @structure.import.path
            alias: (import_alias)? @structure.import.alias) @structure.import
        ]
    """,
    
    # Property patterns
    "property": """
        [
          (property_declaration
            modifiers: [(public) (private) (protected) (internal) (override) (lateinit) (const)]* @semantics.property.modifier
            var_or_val: [(var) (val)] @semantics.property.kind
            name: (simple_identifier) @semantics.property.name
            type: (type_reference)? @semantics.property.type
            initializer: (property_initializer)? @semantics.property.initializer
            delegate: (property_delegate)? @semantics.property.delegate
            accessors: [(getter) (setter)]* @semantics.property.accessors) @semantics.property
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; KDoc patterns
          (comment) @documentation.kdoc {
            match: "^/\\*\\*"
          },
          
          ; KDoc tags
          (comment) @documentation.kdoc.tag {
            match: "@[a-zA-Z]+"
          }
        ]
    """,
    
    # Coroutine patterns
    "coroutine": """
        [
          (function_declaration
            modifiers: (suspend) @semantics.coroutine.suspend) @semantics.coroutine.function,
            
          (call_expression
            function: [(simple_identifier) (navigation_expression)]
            lambda_literal: (lambda_literal
              statements: (statements) @semantics.coroutine.launch.body)
            (#match? @function "^(launch|async)$")) @semantics.coroutine.launch,
            
          (navigation_expression
            target: (simple_identifier) @semantics.coroutine.scope
            (#match? @semantics.coroutine.scope "^(coroutineScope|supervisorScope)$")) @semantics.coroutine.scope_call
        ]
    """,
    
    # DSL support patterns
    "dsl": """
        [
          (annotation
            use_site_target: (use_site_target) @semantics.dsl.annotation.target
            name: (constructor_invocation
              user_type: (user_type) @semantics.dsl.annotation.name)
            (#match? @semantics.dsl.annotation.name "^DslMarker$")) @semantics.dsl.marker,
            
          (function_declaration
            modifiers: (annotation
              name: (constructor_invocation
                user_type: (user_type) @semantics.dsl.function.annotation)
              (#match? @semantics.dsl.function.annotation "^(HtmlTagMarker|Composable)$"))) @semantics.dsl.function
        ]
    """
} 