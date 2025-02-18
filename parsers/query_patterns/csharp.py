"""C#-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

CSHARP_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic method (from common)
          (method_declaration) @syntax.method,
          
          ; Rich method patterns
          (method_declaration
            attributes: (attribute_list)* @syntax.function.attributes
            modifiers: [(public) (private) (protected) (internal) (static) (virtual) (override) (abstract) (async)]* @syntax.function.modifier
            type_parameter_list: (type_parameter_list
              (type_parameter
                attributes: (attribute_list)* @syntax.function.type_param.attributes
                variance_annotation: [(in) (out)]? @syntax.function.type_param.variance
                name: (identifier) @syntax.function.type_param.name
                constraints: (type_parameter_constraints_clause)? @syntax.function.type_param.constraints)*) @syntax.function.type_params
            return_type: (_) @syntax.function.return_type
            name: (identifier) @syntax.function.name
            parameter_list: (parameter_list
              (parameter
                attributes: (attribute_list)* @syntax.function.param.attributes
                modifiers: [(ref) (out) (params)]* @syntax.function.param.modifier
                type: (_) @syntax.function.param.type
                name: (identifier) @syntax.function.param.name
                default_value: (_)? @syntax.function.param.default)*) @syntax.function.params
            constraints: (type_parameter_constraints_clause)* @syntax.function.constraints
            body: [(block) (arrow_expression_clause)]? @syntax.function.body) @syntax.function.def,
            
          ; Constructor patterns
          (constructor_declaration
            attributes: (attribute_list)* @syntax.function.constructor.attributes
            modifiers: [(public) (private) (protected) (internal)]* @syntax.function.constructor.modifier
            name: (identifier) @syntax.function.constructor.name
            parameter_list: (parameter_list) @syntax.function.constructor.params
            initializer: (constructor_initializer)? @syntax.function.constructor.init
            body: (block) @syntax.function.constructor.body) @syntax.function.constructor
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_declaration) @syntax.class,
          
          ; Rich class patterns
          (class_declaration
            attributes: (attribute_list)* @syntax.class.attributes
            modifiers: [(public) (private) (protected) (internal) (static) (abstract) (sealed) (partial)]* @syntax.class.modifier
            name: (identifier) @syntax.class.name
            type_parameter_list: (type_parameter_list)? @syntax.class.type_params
            base_list: (base_list
              [(primary_constructor_base_type) @syntax.class.extends.primary
               (base_type) @syntax.class.implements]*) @syntax.class.bases
            constraints: (type_parameter_constraints_clause)* @syntax.class.constraints
            body: (declaration_list
              [(field_declaration) @syntax.class.field
               (property_declaration) @syntax.class.property
               (method_declaration) @syntax.class.method
               (constructor_declaration) @syntax.class.constructor
               (delegate_declaration) @syntax.class.delegate
               (event_declaration) @syntax.class.event
               (indexer_declaration) @syntax.class.indexer]*) @syntax.class.body) @syntax.class.def,
               
          ; Interface patterns
          (interface_declaration
            attributes: (attribute_list)* @syntax.interface.attributes
            modifiers: [(public) (private) (protected) (internal)]* @syntax.interface.modifier
            name: (identifier) @syntax.interface.name
            type_parameter_list: (type_parameter_list)? @syntax.interface.type_params
            base_list: (base_list)? @syntax.interface.extends
            body: (declaration_list) @syntax.interface.body) @syntax.interface.def
        ]
    """,
    
    # Structure category with rich patterns
    "namespace": """
        [
          (namespace_declaration
            name: (qualified_name) @structure.namespace.name
            body: (declaration_list) @structure.namespace.body) @structure.namespace,
            
          (using_directive
            static_keyword: (static_keyword)? @structure.using.static
            name: (qualified_name) @structure.using.name
            alias: (identifier)? @structure.using.alias) @structure.using
        ]
    """,
    
    # LINQ patterns
    "linq": """
        [
          (query_expression
            clauses: [(from_clause
                       type: (_)? @semantics.linq.from.type
                       name: (identifier) @semantics.linq.from.name
                       in: (_) @semantics.linq.from.source)
                     (where_clause
                       condition: (_) @semantics.linq.where.condition)
                     (orderby_clause
                       orderings: (ordering
                         expression: (_) @semantics.linq.orderby.expr
                         direction: [(ascending_keyword) (descending_keyword)]? @semantics.linq.orderby.dir)*)
                     (select_clause
                       expression: (_) @semantics.linq.select.expr)
                     (group_clause
                       expression: (_) @semantics.linq.group.expr
                       by: (_) @semantics.linq.group.by)
                     (join_clause
                       name: (identifier) @semantics.linq.join.name
                       in: (_) @semantics.linq.join.source
                       on: (_) @semantics.linq.join.on
                       equals: (_) @semantics.linq.join.equals)]*) @semantics.linq.query
        ]
    """,
    
    # Async/await patterns
    "async": """
        [
          (method_declaration
            modifiers: (async_keyword) @semantics.async.modifier) @semantics.async.method,
            
          (await_expression
            expression: (_) @semantics.async.await.expr) @semantics.async.await,
            
          (anonymous_method_expression
            modifiers: (async_keyword) @semantics.async.lambda.modifier) @semantics.async.lambda
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; XML documentation comments
          (documentation_comment
            tags: [(element
                    name: (_) @documentation.xml.tag.name
                    attributes: (attribute
                      name: (_) @documentation.xml.attr.name
                      value: (_) @documentation.xml.attr.value)*
                    content: (_)* @documentation.xml.content)]*) @documentation.xml
        ]
    """
} 