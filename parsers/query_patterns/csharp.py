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

# Repository learning patterns for C#
CSHARP_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (class_declaration
                name: (identifier) @naming.class.name) @naming.class,
                
            (interface_declaration
                name: (identifier) @naming.interface.name) @naming.interface,
                
            (method_declaration
                name: (identifier) @naming.method.name) @naming.method,
                
            (variable_declaration
                (variable_declarator
                    name: (identifier) @naming.variable.name)) @naming.variable,
                    
            (property_declaration
                name: (identifier) @naming.property.name) @naming.property
        ]
        """,
        "extract": lambda node: {
            "type": "naming_convention_pattern",
            "entity_type": ("class" if "naming.class.name" in node["captures"] else
                          "interface" if "naming.interface.name" in node["captures"] else
                          "method" if "naming.method.name" in node["captures"] else
                          "property" if "naming.property.name" in node["captures"] else
                          "variable"),
            "name": (node["captures"].get("naming.class.name", {}).get("text", "") or 
                   node["captures"].get("naming.interface.name", {}).get("text", "") or
                   node["captures"].get("naming.method.name", {}).get("text", "") or
                   node["captures"].get("naming.property.name", {}).get("text", "") or
                   node["captures"].get("naming.variable.name", {}).get("text", "")),
            "is_pascal_case": not "_" in (node["captures"].get("naming.class.name", {}).get("text", "") or
                                        node["captures"].get("naming.interface.name", {}).get("text", "") or
                                        node["captures"].get("naming.property.name", {}).get("text", "") or
                                        node["captures"].get("naming.method.name", {}).get("text", "")) and
                             (node["captures"].get("naming.class.name", {}).get("text", "") or
                              node["captures"].get("naming.interface.name", {}).get("text", "") or
                              node["captures"].get("naming.property.name", {}).get("text", "") or
                              node["captures"].get("naming.method.name", {}).get("text", ""))[0:1].isupper(),
            "is_camel_case": not "_" in (node["captures"].get("naming.variable.name", {}).get("text", "")) and
                           (node["captures"].get("naming.variable.name", {}).get("text", "")).strip() and
                           (node["captures"].get("naming.variable.name", {}).get("text", ""))[0:1].islower(),
            "interface_starts_with_i": node["captures"].get("naming.interface.name", {}).get("text", "").startswith("I") and
                                     len(node["captures"].get("naming.interface.name", {}).get("text", "")) > 1 and
                                     node["captures"].get("naming.interface.name", {}).get("text", "")[1].isupper()
        }
    },
    
    "linq_usage": {
        "pattern": """
        [
            (query_expression
                clauses: [(from_clause) (where_clause)? (select_clause)]+ @linq.basic.clauses) @linq.basic,
                
            (query_expression
                clauses: [(group_clause) (join_clause) (orderby_clause)]+ @linq.advanced.clauses) @linq.advanced
        ]
        """,
        "extract": lambda node: {
            "type": "linq_usage_pattern",
            "uses_basic_linq": "linq.basic" in node["captures"],
            "uses_advanced_linq": "linq.advanced" in node["captures"],
            "has_where": "where_clause" in node["captures"].get("linq.basic.clauses", {}).get("text", ""),
            "has_group": "linq.advanced" in node["captures"] and "group_clause" in node["captures"].get("linq.advanced.clauses", {}).get("text", ""),
            "has_join": "linq.advanced" in node["captures"] and "join_clause" in node["captures"].get("linq.advanced.clauses", {}).get("text", "")
        }
    },
    
    "async_await_patterns": {
        "pattern": """
        [
            (method_declaration
                modifiers: (modifier_list
                    (async_keyword) @async.method.keyword) @async.method.modifiers
                name: (identifier) @async.method.name) @async.method,
                
            (await_expression
                expression: (_) @async.await.expression) @async.await
        ]
        """,
        "extract": lambda node: {
            "type": "async_await_pattern",
            "is_async_method": "async.method" in node["captures"],
            "uses_await": "async.await" in node["captures"],
            "method_name": node["captures"].get("async.method.name", {}).get("text", ""),
            "method_name_ends_with_async": node["captures"].get("async.method.name", {}).get("text", "").lower().endswith("async")
        }
    },
    
    "code_organization": {
        "pattern": """
        [
            (attribute_list
                (attribute
                    name: (identifier) @organization.attribute.name)) @organization.attribute,
                    
            (using_directive
                static_keyword: (static_keyword)? @organization.using.static
                name: (qualified_name) @organization.using.name) @organization.using,
                
            (namespace_declaration
                name: (qualified_name) @organization.namespace.name) @organization.namespace
        ]
        """,
        "extract": lambda node: {
            "type": "code_organization_pattern",
            "uses_attributes": "organization.attribute" in node["captures"],
            "uses_static_imports": "organization.using.static" in node["captures"],
            "namespace_style": "dot_separated" if "." in node["captures"].get("organization.namespace.name", {}).get("text", "") else "single_level"
        }
    }
}

# Add the repository learning patterns to the main patterns
CSHARP_PATTERNS['REPOSITORY_LEARNING'] = CSHARP_PATTERNS_FOR_LEARNING 