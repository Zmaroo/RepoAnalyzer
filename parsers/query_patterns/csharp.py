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
            modifiers: (_)* @syntax.function.modifier
            type: (_) @syntax.function.return_type
            name: (identifier) @syntax.function.name
            parameters: (parameter_list) @syntax.function.params
            body: [(block) (arrow_expression_clause)]? @syntax.function.body) @syntax.function.method,
            
          ; Constructor patterns
          (constructor_declaration
            attributes: (attribute_list)* @syntax.function.constructor.attributes
            modifiers: (_)* @syntax.function.constructor.modifier
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
            modifiers: (_)* @syntax.class.modifier
            name: (identifier) @syntax.class.name
            type_parameters: (type_parameter_list)? @syntax.class.type_params
            base_list: (base_list)? @syntax.class.bases
            body: (declaration_list) @syntax.class.body) @syntax.class.def,
               
          ; Interface patterns
          (interface_declaration
            attributes: (attribute_list)* @syntax.interface.attributes
            modifiers: (_)* @syntax.interface.modifier
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