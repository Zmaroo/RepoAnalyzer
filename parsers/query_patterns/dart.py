"""Dart-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

DART_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_declaration) @syntax.function,
          
          ; Rich function patterns
          (function_declaration
            metadata: (metadata)* @syntax.function.metadata
            return_type: (_)? @syntax.function.return_type
            name: (identifier) @syntax.function.name
            parameters: (formal_parameter_list
              [(normal_formal_parameter
                 metadata: (metadata)* @syntax.function.param.metadata
                 type: (_)? @syntax.function.param.type
                 name: (identifier) @syntax.function.param.name
                 default_value: (_)? @syntax.function.param.default)
               (optional_formal_parameters
                 parameters: (formal_parameter_list)? @syntax.function.param.optional)]*) @syntax.function.params
            body: [(block) (arrow_body)]? @syntax.function.body) @syntax.function.def,
            
          ; Method patterns
          (method_declaration
            metadata: (metadata)* @syntax.function.method.metadata
            modifiers: [(static) (abstract) (external)]* @syntax.function.method.modifier
            return_type: (_)? @syntax.function.method.return_type
            name: (identifier) @syntax.function.method.name
            parameters: (formal_parameter_list) @syntax.function.method.params
            body: [(block) (arrow_body)]? @syntax.function.method.body) @syntax.function.method
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_declaration) @syntax.class,
          
          ; Rich class patterns
          (class_declaration
            metadata: (metadata)* @syntax.class.metadata
            modifiers: [(abstract)]* @syntax.class.modifier
            name: (identifier) @syntax.class.name
            type_parameters: (type_parameters
              (type_parameter
                metadata: (metadata)* @syntax.class.type_param.metadata
                name: (identifier) @syntax.class.type_param.name
                extends: (_)? @syntax.class.type_param.bound)*) @syntax.class.type_params
            superclass: (superclass
              type: (_) @syntax.class.extends)? @syntax.class.superclass
            interfaces: (interfaces
              types: (_)+ @syntax.class.implements)? @syntax.class.interfaces
            mixins: (mixins
              types: (_)+ @syntax.class.with)? @syntax.class.mixins
            body: (class_body
              [(method_declaration) @syntax.class.method
               (variable_declaration) @syntax.class.field
               (constructor_declaration) @syntax.class.constructor]*) @syntax.class.body) @syntax.class.def,
               
          ; Mixin patterns
          (mixin_declaration
            metadata: (metadata)* @syntax.mixin.metadata
            name: (identifier) @syntax.mixin.name
            on: (on_clause)? @syntax.mixin.on
            interfaces: (interfaces)? @syntax.mixin.implements
            body: (class_body) @syntax.mixin.body) @syntax.mixin.def
        ]
    """,
    
    # Structure category with rich patterns
    "library": """
        [
          (library_declaration
            metadata: (metadata)* @structure.library.metadata
            name: (identifier) @structure.library.name) @structure.library,
            
          (import_statement
            metadata: (metadata)* @structure.import.metadata
            uri: (string_literal) @structure.import.uri
            configurations: (configuration_uri)* @structure.import.config
            combinators: [(show_combinator) (hide_combinator)]* @structure.import.combinator) @structure.import,
            
          (part_directive
            metadata: (metadata)* @structure.part.metadata
            uri: (string_literal) @structure.part.uri) @structure.part
        ]
    """,
    
    # Async patterns
    "async": """
        [
          (function_declaration
            body: (block
              (async_marker) @semantics.async.marker)) @semantics.async.function,
              
          (method_declaration
            body: (block
              (async_marker) @semantics.async.method.marker)) @semantics.async.method,
              
          (await_expression
            expression: (_) @semantics.async.await.expr) @semantics.async.await,
            
          (yield_statement
            expression: (_)? @semantics.async.yield.expr) @semantics.async.yield
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; Documentation comments
          (documentation_comment
            content: (_)* @documentation.doc.content) @documentation.doc,
            
          ; Documentation references
          (documentation_comment
            reference: (identifier) @documentation.doc.reference) @documentation.doc.ref
        ]
    """,
    
    # Flutter widget patterns
    "widget": """
        [
          (class_declaration
            metadata: (metadata
              (identifier) @semantics.widget.annotation
              (#match? @semantics.widget.annotation "^Widget$")) @semantics.widget.metadata
            name: (identifier) @semantics.widget.name) @semantics.widget.class,
            
          (method_declaration
            name: (identifier) @semantics.widget.build
            (#match? @semantics.widget.build "^build$")
            body: (block
              (return_statement
                expression: (_) @semantics.widget.build.return))) @semantics.widget.build_method,
                
          (constructor_invocation
            type: (identifier) @semantics.widget.constructor
            arguments: (arguments
              [(named_argument
                 name: (identifier) @semantics.widget.prop.name
                 expression: (_) @semantics.widget.prop.value)
               (positional_argument) @semantics.widget.prop.child]*)) @semantics.widget.instance
        ]
    """,
    
    # State management patterns
    "state": """
        [
          (class_declaration
            metadata: (metadata
              (identifier) @semantics.state.annotation
              (#match? @semantics.state.annotation "^(State|ChangeNotifier|Bloc)$")) @semantics.state.metadata) @semantics.state.class,
            
          (method_declaration
            name: (identifier) @semantics.state.method
            (#match? @semantics.state.method "^(setState|notifyListeners|emit)$")) @semantics.state.update
        ]
    """
} 