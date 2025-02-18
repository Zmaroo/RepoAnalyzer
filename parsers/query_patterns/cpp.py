"""C++-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

CPP_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_definition) @syntax.function,
          
          ; Rich function patterns
          (function_definition
            specifiers: [(virtual) (static) (inline) (explicit) (constexpr) (friend)]* @syntax.function.specifier
            type: (_) @syntax.function.return_type
            declarator: (function_declarator
              declarator: (identifier) @syntax.function.name
              parameters: (parameter_list
                [(parameter_declaration
                   type: (_) @syntax.function.param.type
                   declarator: (_) @syntax.function.param.name
                   default_value: (_)? @syntax.function.param.default)
                 (variadic_parameter_declaration) @syntax.function.param.variadic]*) @syntax.function.params
              trailing_return_type: (type_descriptor)? @syntax.function.trailing_return) @syntax.function.declarator
            requires: (requires_clause)? @syntax.function.requires
            body: (compound_statement) @syntax.function.body) @syntax.function.def,
            
          ; Method patterns
          (function_definition
            specifiers: [(virtual) (static) (const) (override) (final) (noexcept)]* @syntax.function.method.specifier
            declarator: (function_declarator
              declarator: (qualified_identifier) @syntax.function.method.name) @syntax.function.method.declarator) @syntax.function.method,
            
          ; Constructor patterns
          (constructor_or_destructor_definition
            specifiers: [(explicit) (constexpr)]* @syntax.function.constructor.specifier
            declarator: (function_declarator
              declarator: (qualified_identifier) @syntax.function.constructor.name
              parameters: (parameter_list) @syntax.function.constructor.params)
            initializer_list: (initializer_list)? @syntax.function.constructor.init
            body: (compound_statement) @syntax.function.constructor.body) @syntax.function.constructor
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_specifier) @syntax.class,
          
          ; Rich class patterns
          (class_specifier
            name: (type_identifier) @syntax.class.name
            virtual_specifier: (virtual_specifier)? @syntax.class.virtual
            base_classes: (base_class_clause
              [(access_specifier)? @syntax.class.base.access
               (type_identifier) @syntax.class.base.name]*) @syntax.class.bases
            body: (field_declaration_list
              [(access_specifier) @syntax.class.access
               (field_declaration) @syntax.class.field
               (function_definition) @syntax.class.method
               (constructor_or_destructor_definition) @syntax.class.constructor
               (friend_declaration) @syntax.class.friend
               (template_declaration) @syntax.class.template
               (using_declaration) @syntax.class.using]*) @syntax.class.body) @syntax.class.def,
               
          ; Struct patterns
          (struct_specifier
            name: (type_identifier) @syntax.struct.name
            body: (field_declaration_list) @syntax.struct.body) @syntax.struct.def
        ]
    """,
    
    # Template patterns
    "template": """
        [
          (template_declaration
            parameters: (template_parameter_list
              [(type_parameter_declaration
                 type: (type_identifier) @semantics.template.param.type
                 default: (_)? @semantics.template.param.default)
               (parameter_declaration
                 type: (_) @semantics.template.param.type
                 declarator: (_) @semantics.template.param.name)]*) @semantics.template.params
            declaration: (_) @semantics.template.declaration) @semantics.template.def,
            
          (template_instantiation
            name: (_) @semantics.template.inst.name
            arguments: (template_argument_list
              (_)* @semantics.template.inst.arg)) @semantics.template.inst
        ]
    """,
    
    # Structure category with rich patterns
    "namespace": """
        [
          (namespace_definition
            name: (identifier) @structure.namespace.name
            body: (declaration_list) @structure.namespace.body) @structure.namespace,
            
          (using_declaration
            name: (qualified_identifier) @structure.using.name) @structure.using,
            
          (using_directive
            namespace_name: (qualified_identifier) @structure.using.namespace) @structure.using.directive
        ]
    """,
    
    # Modern C++ features
    "modern": """
        [
          ; Lambda expressions
          (lambda_expression
            captures: (lambda_capture_specifier)? @semantics.lambda.captures
            parameters: (parameter_list)? @semantics.lambda.params
            body: (compound_statement) @semantics.lambda.body) @semantics.lambda,
            
          ; Concepts
          (concept_definition
            name: (identifier) @semantics.concept.name
            parameters: (template_parameter_list)? @semantics.concept.params
            constraint: (_) @semantics.concept.constraint) @semantics.concept,
            
          ; Ranges
          (range_based_for_statement
            declarator: (_) @semantics.range.var
            range: (_) @semantics.range.expr
            body: (_) @semantics.range.body) @semantics.range.for
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; Rich documentation patterns
          (comment) @documentation.comment,
          
          ; Doxygen patterns
          (comment
            text: /\\/\\*\\*.*?\\*\\// @documentation.doxygen.block) @documentation.doxygen,
          (comment
            text: /\\/\\/\\/.*/) @documentation.doxygen.line,
            
          ; Documentation commands
          (comment
            text: /@[a-zA-Z]+.*/) @documentation.command
        ]
    """
} 