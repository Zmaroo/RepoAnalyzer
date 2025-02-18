"""Swift-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

SWIFT_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_declaration) @syntax.function,
          
          ; Rich function patterns
          (function_declaration
            attributes: (attribute)* @syntax.function.attributes
            modifiers: [(private) (public) (internal) (fileprivate) (static) (class) (final)]* @syntax.function.modifier
            name: (identifier) @syntax.function.name
            generic_parameter_clause: (generic_parameter_clause
              (generic_parameter
                name: (type_identifier) @syntax.function.type_param.name
                type_constraints: (type_constraints
                  (inheritance_constraint
                    type: (_) @syntax.function.type_param.constraint))*) @syntax.function.type_param)* @syntax.function.type_params
            parameter_clause: (parameter_clause
              (parameter
                attributes: (attribute)* @syntax.function.param.attributes
                modifiers: [(inout)]* @syntax.function.param.modifier
                name: (identifier) @syntax.function.param.name
                type: (_) @syntax.function.param.type
                default_value: (_)? @syntax.function.param.default)*) @syntax.function.params
            return_type: (type_annotation
              type: (_) @syntax.function.return_type)? @syntax.function.return
            generic_where_clause: (generic_where_clause)? @syntax.function.where
            body: (code_block) @syntax.function.body) @syntax.function.def,
            
          ; Method patterns
          (function_declaration
            modifiers: [(mutating) (override)]* @syntax.function.method.modifier) @syntax.function.method
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_declaration) @syntax.class,
          
          ; Rich class patterns
          (class_declaration
            attributes: (attribute)* @syntax.class.attributes
            modifiers: [(private) (public) (internal) (fileprivate) (final)]* @syntax.class.modifier
            name: (type_identifier) @syntax.class.name
            generic_parameter_clause: (generic_parameter_clause)? @syntax.class.type_params
            type_inheritance_clause: (type_inheritance_clause
              [(class_requirement) @syntax.class.superclass
               (type_identifier) @syntax.class.protocol]*) @syntax.class.inheritance
            generic_where_clause: (generic_where_clause)? @syntax.class.where
            members: (class_body
              [(property_declaration) @syntax.class.property
               (function_declaration) @syntax.class.method
               (initializer_declaration) @syntax.class.initializer
               (deinitializer_declaration) @syntax.class.deinitializer
               (subscript_declaration) @syntax.class.subscript
               (protocol_property_declaration) @syntax.class.protocol_property]*) @syntax.class.body) @syntax.class.def,
               
          ; Protocol patterns
          (protocol_declaration
            attributes: (attribute)* @syntax.protocol.attributes
            modifiers: [(private) (public) (internal) (fileprivate)]* @syntax.protocol.modifier
            name: (type_identifier) @syntax.protocol.name
            type_inheritance_clause: (type_inheritance_clause)? @syntax.protocol.inheritance
            members: (protocol_body) @syntax.protocol.body) @syntax.protocol.def
        ]
    """,
    
    # Structure category with rich patterns
    "module": """
        [
          (import_declaration
            path: (identifier)+ @structure.import.path
            attributes: (attribute)* @structure.import.attributes) @structure.import,
            
          (extension_declaration
            type: (type_identifier) @structure.extension.type
            type_inheritance_clause: (type_inheritance_clause)? @structure.extension.protocols
            generic_where_clause: (generic_where_clause)? @structure.extension.where
            members: (extension_body) @structure.extension.body) @structure.extension
        ]
    """,
    
    # Property patterns
    "property": """
        [
          (property_declaration
            attributes: (attribute)* @semantics.property.attributes
            modifiers: [(private) (public) (internal) (fileprivate) (static) (class)]* @semantics.property.modifier
            name: (identifier) @semantics.property.name
            type: (type_annotation
              type: (_) @semantics.property.type)? @semantics.property.type_annotation
            getter_setter_block: (getter_setter_block
              [(getter_clause) @semantics.property.getter
               (setter_clause) @semantics.property.setter])? @semantics.property.accessors) @semantics.property,
               
          (computed_property
            code_block: (code_block) @semantics.property.computed.body) @semantics.property.computed
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; Rich documentation patterns
          (documentation_comment
            text: /\\/\\/\\/.*/) @documentation.doc.line,
            
          (documentation_comment
            text: /\\/\\*\\*.*?\\*\\// @documentation.doc.block),
            
          ; Documentation keywords
          (documentation_comment
            text: /- [a-zA-Z]+:.*/) @documentation.doc.keyword
        ]
    """,
    
    # Error handling patterns
    "error": """
        [
          (do_statement
            code_block: (code_block) @semantics.error.do.block
            catch_clauses: (catch_clause
              pattern: (_) @semantics.error.catch.pattern
              where_clause: (where_clause)? @semantics.error.catch.where
              code_block: (code_block) @semantics.error.catch.block)*) @semantics.error.do,
              
          (throw_statement
            expression: (_) @semantics.error.throw.expr) @semantics.error.throw,
            
          (try_expression
            expression: (_) @semantics.error.try.expr) @semantics.error.try
        ]
    """,
    
    # Concurrency patterns
    "concurrency": """
        [
          (actor_declaration
            name: (type_identifier) @semantics.concurrency.actor.name
            members: (actor_body) @semantics.concurrency.actor.body) @semantics.concurrency.actor,
            
          (async_function
            modifiers: (async) @semantics.concurrency.async.modifier) @semantics.concurrency.async,
            
          (await_expression
            expression: (_) @semantics.concurrency.await.expr) @semantics.concurrency.await
        ]
    """
} 