"""C#-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, 
    QueryPattern, PatternDefinition
)

CSHARP_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "modifiers": [m.text.decode('utf8') for m in node["captures"].get("syntax.function.modifier", [])],
                    "return_type": node["captures"].get("syntax.function.return_type", {}).get("text", ""),
                    "is_constructor": "syntax.function.constructor" in node["captures"]
                },
                description="Matches C# method and constructor declarations",
                examples=[
                    "public void Method() { }",
                    "public MyClass(int value) { }"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            
            "class": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", "") or
                           node["captures"].get("syntax.interface.name", {}).get("text", ""),
                    "type": "class" if "syntax.class.name" in node["captures"] else "interface",
                    "modifiers": [m.text.decode('utf8') for m in node["captures"].get("syntax.class.modifier", []) or
                                node["captures"].get("syntax.interface.modifier", [])]
                },
                description="Matches C# class and interface declarations",
                examples=[
                    "public class MyClass : BaseClass { }",
                    "public interface IService { }"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "namespace": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": node["captures"].get("structure.namespace.name", {}).get("text", ""),
                    "using": node["captures"].get("structure.using.name", {}).get("text", ""),
                    "is_static_using": "structure.using.static" in node["captures"]
                },
                description="Matches C# namespace and using declarations",
                examples=[
                    "namespace MyNamespace { }",
                    "using static System.Math;"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "linq": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "has_from": "semantics.linq.from.name" in node["captures"],
                    "has_where": "semantics.linq.where.condition" in node["captures"],
                    "has_orderby": "semantics.linq.orderby.expr" in node["captures"],
                    "has_group": "semantics.linq.group.expr" in node["captures"],
                    "has_join": "semantics.linq.join.name" in node["captures"]
                },
                description="Matches C# LINQ query expressions",
                examples=[
                    "from x in items select x",
                    "from x in items where x > 0 orderby x select x"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            
            "async": QueryPattern(
                pattern="""
                [
                    (method_declaration
                        modifiers: (async_keyword) @semantics.async.modifier) @semantics.async.method,
                        
                    (await_expression
                        expression: (_) @semantics.async.await.expr) @semantics.async.await,
                        
                    (anonymous_method_expression
                        modifiers: (async_keyword) @semantics.async.lambda.modifier) @semantics.async.lambda
                ]
                """,
                extract=lambda node: {
                    "is_async_method": "semantics.async.modifier" in node["captures"],
                    "has_await": "semantics.async.await" in node["captures"],
                    "is_async_lambda": "semantics.async.lambda" in node["captures"]
                },
                description="Matches C# async/await patterns",
                examples=[
                    "async Task<int> Method() { }",
                    "await Task.Delay(1000);"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
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
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "is_xml_doc": "documentation.xml" in node["captures"],
                    "xml_tags": [t.get("text", "") for t in node["captures"].get("documentation.xml.tag.name", [])]
                },
                description="Matches C# comments and XML documentation",
                examples=[
                    "// Line comment",
                    "/// <summary>Method description</summary>"
                ],
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    }
}

# Repository learning patterns for C#
CSHARP_PATTERNS_FOR_LEARNING = {
    PatternCategory.LEARNING: {
        PatternPurpose.LEARNING: {
            "naming_conventions": QueryPattern(
                pattern="""
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
                extract=lambda node: {
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
                },
                description="Matches C# naming conventions",
                examples=[
                    "public class MyClass { }",
                    "private string myField;",
                    "public interface IService { }"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "linq_usage": QueryPattern(
                pattern="""
                [
                    (query_expression
                        clauses: [(from_clause) (where_clause)? (select_clause)]+ @linq.basic.clauses) @linq.basic,
                        
                    (query_expression
                        clauses: [(group_clause) (join_clause) (orderby_clause)]+ @linq.advanced.clauses) @linq.advanced
                ]
                """,
                extract=lambda node: {
                    "type": "linq_usage_pattern",
                    "uses_basic_linq": "linq.basic" in node["captures"],
                    "uses_advanced_linq": "linq.advanced" in node["captures"],
                    "has_where": "where_clause" in node["captures"].get("linq.basic.clauses", {}).get("text", ""),
                    "has_group": "linq.advanced" in node["captures"] and "group_clause" in node["captures"].get("linq.advanced.clauses", {}).get("text", ""),
                    "has_join": "linq.advanced" in node["captures"] and "join_clause" in node["captures"].get("linq.advanced.clauses", {}).get("text", "")
                },
                description="Matches C# LINQ usage patterns",
                examples=[
                    "from x in items select x",
                    "from x in items join y in others on x.Id equals y.Id select x"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "async_await_patterns": QueryPattern(
                pattern="""
                [
                    (method_declaration
                        modifiers: (modifier_list
                            (async_keyword) @async.method.keyword) @async.method.modifiers
                        name: (identifier) @async.method.name) @async.method,
                        
                    (await_expression
                        expression: (_) @async.await.expression) @async.await
                ]
                """,
                extract=lambda node: {
                    "type": "async_await_pattern",
                    "is_async_method": "async.method" in node["captures"],
                    "uses_await": "async.await" in node["captures"],
                    "method_name": node["captures"].get("async.method.name", {}).get("text", ""),
                    "method_name_ends_with_async": node["captures"].get("async.method.name", {}).get("text", "").lower().endswith("async")
                },
                description="Matches C# async/await patterns",
                examples=[
                    "public async Task<int> GetValueAsync() { }",
                    "await client.GetAsync(url);"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "code_organization": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "type": "code_organization_pattern",
                    "uses_attributes": "organization.attribute" in node["captures"],
                    "uses_static_imports": "organization.using.static" in node["captures"],
                    "namespace_style": "dot_separated" if "." in node["captures"].get("organization.namespace.name", {}).get("text", "") else "single_level"
                },
                description="Matches C# code organization patterns",
                examples=[
                    "[Serializable] public class MyClass { }",
                    "using static System.Math;",
                    "namespace Company.Product.Feature { }"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            )
        }
    }
}

# Add the repository learning patterns to the main patterns
CSHARP_PATTERNS.update(CSHARP_PATTERNS_FOR_LEARNING) 