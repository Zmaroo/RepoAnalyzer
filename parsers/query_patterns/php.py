"""PHP-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

PHP_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_definition) @syntax.function,
          
          ; Rich function patterns
          (function_definition
            attributes: (attribute_list)* @syntax.function.attributes
            modifiers: [(public) (private) (protected) (static) (final) (abstract)]* @syntax.function.modifier
            name: (name) @syntax.function.name
            parameters: (formal_parameters
              [(simple_parameter
                 type: (_)? @syntax.function.param.type
                 name: (variable_name) @syntax.function.param.name
                 default_value: (_)? @syntax.function.param.default)
               (variadic_parameter
                 type: (_)? @syntax.function.param.type
                 name: (variable_name) @syntax.function.param.name)]*) @syntax.function.params
            return_type: (type)? @syntax.function.return_type
            body: (compound_statement) @syntax.function.body) @syntax.function.def,
            
          ; Method patterns
          (method_declaration
            attributes: (attribute_list)* @syntax.function.method.attributes
            modifiers: [(public) (private) (protected) (static) (final) (abstract)]* @syntax.function.method.modifier
            name: (name) @syntax.function.method.name
            parameters: (formal_parameters) @syntax.function.method.params
            return_type: (type)? @syntax.function.method.return_type
            body: (compound_statement)? @syntax.function.method.body) @syntax.function.method
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_declaration) @syntax.class,
          
          ; Rich class patterns
          (class_declaration
            attributes: (attribute_list)* @syntax.class.attributes
            modifiers: [(abstract) (final)]* @syntax.class.modifier
            name: (name) @syntax.class.name
            base_clause: (base_clause
              name: (name) @syntax.class.extends)? @syntax.class.extends
            interfaces: (class_interface_clause
              names: (name)+ @syntax.class.implements)? @syntax.class.implements
            body: (declaration_list
              [(property_declaration
                 attributes: (attribute_list)* @syntax.class.property.attributes
                 modifiers: [(public) (private) (protected) (static)]* @syntax.class.property.modifier
                 type: (type)? @syntax.class.property.type
                 declarator: (property_declarator
                   name: (variable_name) @syntax.class.property.name
                   value: (_)? @syntax.class.property.value)) @syntax.class.property
               (method_declaration) @syntax.class.method
               (trait_use_clause) @syntax.class.trait]*) @syntax.class.body) @syntax.class.def,
               
          ; Interface patterns
          (interface_declaration
            attributes: (attribute_list)* @syntax.interface.attributes
            name: (name) @syntax.interface.name
            interfaces: (interface_base_clause)? @syntax.interface.extends
            body: (declaration_list) @syntax.interface.body) @syntax.interface.def,
            
          ; Trait patterns
          (trait_declaration
            attributes: (attribute_list)* @syntax.trait.attributes
            name: (name) @syntax.trait.name
            body: (declaration_list) @syntax.trait.body) @syntax.trait.def
        ]
    """,
    
    # Structure category with rich patterns
    "namespace": """
        [
          (namespace_definition
            name: (namespace_name)? @structure.namespace.name
            body: (compound_statement) @structure.namespace.body) @structure.namespace,
            
          (namespace_use_declaration
            kind: [(function) (const)]? @structure.use.kind
            clauses: (namespace_use_clause
              name: (qualified_name) @structure.use.name
              alias: (namespace_aliasing_clause)? @structure.use.alias)*) @structure.use,
              
          (namespace_group_use_declaration
            prefix: (qualified_name) @structure.use.group.prefix
            clauses: (namespace_group_use_clause)*) @structure.use.group
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; PHPDoc patterns
          (comment) @documentation.phpdoc {
            match: "^/\\*\\*"
          },
          
          ; PHPDoc tags
          (comment) @documentation.phpdoc.tag {
            match: "@[a-zA-Z]+"
          }
        ]
    """,
    
    # Attribute patterns
    "attribute": """
        [
          (attribute
            name: (qualified_name) @semantics.attribute.name
            arguments: (arguments
              (argument
                name: (name)? @semantics.attribute.arg.name
                value: (_) @semantics.attribute.arg.value)*) @semantics.attribute.args) @semantics.attribute
        ]
    """,
    
    # Laravel patterns
    "laravel": """
        [
          ; Eloquent model relationships
          (method_declaration
            name: (name) @semantics.laravel.relation
            (#match? @semantics.laravel.relation "^(hasOne|hasMany|belongsTo|belongsToMany|morphTo|morphOne|morphMany)$")
            body: (compound_statement
              (return_statement
                (method_call_expression
                  name: (name) @semantics.laravel.relation.type)))) @semantics.laravel.relation.def,
                  
          ; Route definitions
          (expression_statement
            (method_call_expression
              object: (name) @semantics.laravel.route
              (#match? @semantics.laravel.route "^Route$")
              name: (name) @semantics.laravel.route.method
              arguments: (arguments
                (string) @semantics.laravel.route.path))) @semantics.laravel.route.def
        ]
    """
} 