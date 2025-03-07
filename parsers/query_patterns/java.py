"""Java-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, 
    QueryPattern, PatternDefinition
)

JAVA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (method_declaration
                        modifiers: (_)* @syntax.function.modifier
                        type_parameters: (type_parameters)? @syntax.function.type_params
                        type: (_) @syntax.function.return_type
                        name: (identifier) @syntax.function.name
                        parameters: (formal_parameters) @syntax.function.params
                        dimensions: (dimensions)? @syntax.function.dimensions
                        throws: (throws)? @syntax.function.throws
                        body: (block)? @syntax.function.body) @syntax.function.method,
                    
                    (constructor_declaration
                        modifiers: (_)* @syntax.function.constructor.modifier
                        name: (identifier) @syntax.function.constructor.name
                        parameters: (formal_parameters) @syntax.function.constructor.params
                        throws: (throws)? @syntax.function.constructor.throws
                        body: (constructor_body) @syntax.function.constructor.body) @syntax.function.constructor
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "return_type": node["captures"].get("syntax.function.return_type", {}).get("text", ""),
                    "parameters": node["captures"].get("syntax.function.params", {}).get("text", ""),
                    "modifiers": [m.text.decode('utf8') for m in node["captures"].get("syntax.function.modifier", [])],
                    "type_params": node["captures"].get("syntax.function.type_params", {}).get("text", ""),
                    "throws": node["captures"].get("syntax.function.throws", {}).get("text", "")
                },
                description="Matches Java method and constructor declarations",
                examples=[
                    "public void method(String arg) { }",
                    "public MyClass(int value) { }"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "class": QueryPattern(
                pattern="""
                [
                    (class_declaration
                        modifiers: (_)* @syntax.class.modifier
                        name: (identifier) @syntax.class.name
                        type_parameters: (type_parameters)? @syntax.class.type_params
                        superclass: (superclass)? @syntax.class.superclass
                        interfaces: (super_interfaces)? @syntax.class.interfaces
                        permits: (permits)? @syntax.class.permits
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                    
                    (interface_declaration
                        modifiers: (_)* @syntax.interface.modifier
                        name: (identifier) @syntax.interface.name
                        type_parameters: (type_parameters)? @syntax.interface.type_params
                        interfaces: (extends_interfaces)? @syntax.interface.extends
                        permits: (permits)? @syntax.interface.permits
                        body: (interface_body) @syntax.interface.body) @syntax.interface.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", "") or 
                           node["captures"].get("syntax.interface.name", {}).get("text", ""),
                    "type": "class" if "syntax.class.name" in node["captures"] else "interface",
                    "modifiers": [m.text.decode('utf8') for m in node["captures"].get("syntax.class.modifier", []) or 
                                node["captures"].get("syntax.interface.modifier", [])],
                    "superclass": node["captures"].get("syntax.class.superclass", {}).get("text", ""),
                    "interfaces": node["captures"].get("syntax.class.interfaces", {}).get("text", "") or
                                node["captures"].get("syntax.interface.extends", {}).get("text", "")
                },
                description="Matches Java class and interface declarations",
                examples=[
                    "public class MyClass extends Parent implements Interface { }",
                    "public interface MyInterface extends Parent { }"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "package": QueryPattern(
                pattern="""
                [
                    (package_declaration
                        name: (_) @structure.package.name) @structure.package,
                    
                    (import_declaration
                        name: (_) @structure.import.name
                        static: (_)? @structure.import.static
                        asterisk: (_)? @structure.import.wildcard) @structure.import
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.package.name", {}).get("text", ""),
                    "imports": [i.text.decode('utf8') for i in node["captures"].get("structure.import.name", [])]
                },
                description="Matches Java package and import declarations",
                examples=[
                    "package com.example;",
                    "import java.util.List;"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (line_comment) @documentation.line,
                    (block_comment) @documentation.block
                ]
                """,
                extract=lambda node: {
                    "text": node["node"].text.decode('utf8'),
                    "type": "line" if node["node"].type == "line_comment" else "block",
                    "is_javadoc": node["node"].text.decode('utf8').startswith('/**')
                },
                description="Matches Java comments and Javadoc",
                examples=[
                    "// Line comment",
                    "/* Block comment */",
                    "/** Javadoc comment */"
                ],
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "annotation": QueryPattern(
                pattern="""
                [
                    (annotation
                        name: (identifier) @semantics.annotation.name
                        arguments: (annotation_argument_list)? @semantics.annotation.args) @semantics.annotation,
                    
                    (marker_annotation
                        name: (identifier) @semantics.annotation.marker.name) @semantics.annotation.marker
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.annotation.name", {}).get("text", "") or
                           node["captures"].get("semantics.annotation.marker.name", {}).get("text", ""),
                    "arguments": node["captures"].get("semantics.annotation.args", {}).get("text", ""),
                    "type": "marker" if "semantics.annotation.marker.name" in node["captures"] else "normal"
                },
                description="Matches Java annotations",
                examples=[
                    "@Override",
                    "@SuppressWarnings(\"unchecked\")"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.CODE_PATTERNS: {
        PatternPurpose.UNDERSTANDING: {
            "spring": QueryPattern(
                pattern="""
                [
                  (annotation
                    name: (identifier) @semantics.spring.annotation
                    (#match? @semantics.spring.annotation "^(Controller|Service|Repository|Component|Autowired|Configuration)$")
                    arguments: (annotation_argument_list)? @semantics.spring.args) @semantics.spring.component,
                    
                  (annotation
                    name: (identifier) @semantics.spring.mapping
                    (#match? @semantics.spring.mapping "^(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping)$")
                    arguments: (annotation_argument_list)? @semantics.spring.mapping.args) @semantics.spring.endpoint
                ]
                """,
                extract=lambda node: {
                    "type": "spring_annotation",
                    "name": node["captures"].get("semantics.spring.annotation", {}).get("text", "") or
                           node["captures"].get("semantics.spring.mapping", {}).get("text", ""),
                    "arguments": node["captures"].get("semantics.spring.args", {}).get("text", "") or
                               node["captures"].get("semantics.spring.mapping.args", {}).get("text", ""),
                    "is_endpoint": "semantics.spring.mapping" in node["captures"]
                },
                description="Matches Spring Framework annotations",
                examples=[
                    "@Controller",
                    "@GetMapping(\"/api/users\")"
                ],
                category=PatternCategory.CODE_PATTERNS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    }
}

# Repository learning patterns for Java
JAVA_PATTERNS_FOR_LEARNING = {
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
                        
                    (field_declaration
                        declarator: (variable_declarator
                            name: (identifier) @naming.field.name)) @naming.field
                ]
                """,
                extract=lambda node: {
                    "type": "naming_convention_pattern",
                    "entity_type": ("class" if "naming.class" in node["captures"] else
                                  "interface" if "naming.interface" in node["captures"] else
                                  "method" if "naming.method" in node["captures"] else
                                  "field"),
                    "name": (node["captures"].get("naming.class.name", {}).get("text", "") or
                            node["captures"].get("naming.interface.name", {}).get("text", "") or
                            node["captures"].get("naming.method.name", {}).get("text", "") or
                            node["captures"].get("naming.field.name", {}).get("text", "")),
                    "is_pascal_case": not "_" in (node["captures"].get("naming.class.name", {}).get("text", "") or
                                                node["captures"].get("naming.interface.name", {}).get("text", "")) and
                                    any(c.isupper() for c in (node["captures"].get("naming.class.name", {}).get("text", "") or
                                                            node["captures"].get("naming.interface.name", {}).get("text", ""))) and
                                    (node["captures"].get("naming.class.name", {}).get("text", "") or
                                     node["captures"].get("naming.interface.name", {}).get("text", "")).strip() and
                                    (node["captures"].get("naming.class.name", {}).get("text", "") or
                                     node["captures"].get("naming.interface.name", {}).get("text", ""))[0].isupper(),
                    "is_camel_case": not "_" in (node["captures"].get("naming.method.name", {}).get("text", "") or
                                               node["captures"].get("naming.field.name", {}).get("text", "")) and
                                   any(c.isupper() for c in (node["captures"].get("naming.method.name", {}).get("text", "") or
                                                           node["captures"].get("naming.field.name", {}).get("text", ""))) and
                                   (node["captures"].get("naming.method.name", {}).get("text", "") or 
                                    node["captures"].get("naming.field.name", {}).get("text", ""))[0].islower()
                },
                description="Matches Java naming conventions",
                examples=[
                    "public class MyClass { }",
                    "private String myField;"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "exception_handling": QueryPattern(
                pattern="""
                [
                    (try_statement
                        body: (block) @error.try.body
                        [(catch_clause
                            exception_type: (_) @error.catch.type
                            exception_name: (identifier) @error.catch.name
                            body: (block) @error.catch.body) @error.catch
                         (finally_clause
                            body: (block) @error.finally.body) @error.finally]) @error.try,
                            
                    (throw_statement
                        expression: (_) @error.throw.expr) @error.throw
                ]
                """,
                extract=lambda node: {
                    "type": "exception_handling_pattern",
                    "has_catch": "error.catch" in node["captures"],
                    "has_finally": "error.finally" in node["captures"],
                    "is_throw": "error.throw" in node["captures"],
                    "exception_type": node["captures"].get("error.catch.type", {}).get("text", ""),
                    "exception_name": node["captures"].get("error.catch.name", {}).get("text", "")
                },
                description="Matches Java exception handling patterns",
                examples=[
                    "try { ... } catch (Exception e) { ... }",
                    "throw new IllegalArgumentException();"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "api_design": QueryPattern(
                pattern="""
                [
                    (class_declaration
                        modifiers: [(public_modifier) @api.public
                                    (final_modifier) @api.final
                                    (abstract_modifier) @api.abstract]) @api.class,
                                    
                    (method_declaration
                        modifiers: [(public_modifier) @api.method.public
                                    (private_modifier) @api.method.private
                                    (protected_modifier) @api.method.protected
                                    (static_modifier) @api.method.static
                                    (final_modifier) @api.method.final
                                    (abstract_modifier) @api.method.abstract]) @api.method,
                                    
                    (annotation
                        name: (identifier) @api.annotation.name
                        (#match? @api.annotation.name "^(Override|Deprecated|SuppressWarnings|FunctionalInterface)$")) @api.annotation
                ]
                """,
                extract=lambda node: {
                    "type": "api_design_pattern",
                    "is_public_api": "api.public" in node["captures"] or "api.method.public" in node["captures"],
                    "is_private_impl": "api.method.private" in node["captures"],
                    "is_final": "api.final" in node["captures"] or "api.method.final" in node["captures"],
                    "is_abstract": "api.abstract" in node["captures"] or "api.method.abstract" in node["captures"],
                    "has_standard_annotation": "api.annotation" in node["captures"]
                },
                description="Matches Java API design patterns",
                examples=[
                    "public final class MyAPI { }",
                    "@Override public void method() { }"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            )
        }
    }
}

# Add the repository learning patterns to the main patterns
JAVA_PATTERNS.update(JAVA_PATTERNS_FOR_LEARNING) 