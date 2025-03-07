"""Query patterns for C++ files using native tree-sitter syntax."""

from parsers.models import FileType, FileClassification
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, 
    QueryPattern, PatternDefinition
)

CPP_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                (function_definition
                    type: (_) @function.return_type
                    declarator: (function_declarator
                        declarator: (_) @function.name
                        parameters: (parameter_list) @function.params)
                    body: (compound_statement) @function.body) @function
                """,
                extract=lambda node: {
                    "name": node["captures"].get("function.name", {}).get("text", ""),
                    "return_type": node["captures"].get("function.return_type", {}).get("text", ""),
                    "parameters": node["captures"].get("function.params", {}).get("text", "")
                },
                description="Matches C++ function definitions",
                examples=[
                    "void func(int x) { }",
                    "auto calculate() -> int { }"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "class": QueryPattern(
                pattern="""
                (class_specifier
                    name: (type_identifier) @class.name
                    base_class_clause: (base_class_clause)? @class.bases
                    body: (field_declaration_list) @class.body) @class
                """,
                extract=lambda node: {
                    "name": node["captures"].get("class.name", {}).get("text", ""),
                    "bases": node["captures"].get("class.bases", {}).get("text", "")
                },
                description="Matches C++ class definitions",
                examples=[
                    "class MyClass { };",
                    "class Derived : public Base { }"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "template": QueryPattern(
                pattern="""
                (template_declaration
                    parameters: (template_parameter_list) @syntax.template.params
                    declaration: (_) @syntax.template.declaration) @syntax.template
                """,
                extract=lambda node: {
                    "parameters": [p.get("text", "") for p in node.get("params", [])],
                    "declaration": node.get("declaration", {}).get("text", "")
                },
                description="Matches C++ template declarations",
                examples=[
                    "template<typename T> class Container { };",
                    "template<class T, class U> void func() { }"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable_usage": QueryPattern(
                pattern="""
                (declaration
                    type: (_) @semantics.variable.type
                    declarator: (identifier) @semantics.variable.name
                    default_value: (_)? @semantics.variable.value) @semantics.variable
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                    "type": node["captures"].get("semantics.variable.type", {}).get("text", ""),
                    "has_default": "semantics.variable.value" in node["captures"]
                },
                description="Matches C++ variable declarations and usage",
                examples=[
                    "int x = 42;",
                    "std::string name;"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "type_relationships": QueryPattern(
                pattern="""
                (template_declaration
                    parameters: (template_parameter_list) @semantics.template.params
                    declaration: (_) @semantics.template.declaration) @semantics.template
                """,
                extract=lambda node: {
                    "params": node["captures"].get("semantics.template.params", {}).get("text", ""),
                    "declaration": node["captures"].get("semantics.template.declaration", {}).get("text", "")
                },
                description="Matches C++ template type relationships",
                examples=[
                    "template<typename T> using Ptr = std::shared_ptr<T>;",
                    "template<class Base> class Derived : public Base { }"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "namespace": QueryPattern(
                pattern="""
                (namespace_definition
                    name: (identifier) @structure.namespace.name
                    body: (declaration_list) @structure.namespace.body) @structure.namespace
                """,
                extract=lambda node: {
                    "name": node["captures"].get("namespace.name", {}).get("text", ""),
                    "body": node["captures"].get("namespace.body", {}).get("text", "")
                },
                description="Matches C++ namespace definitions",
                examples=[
                    "namespace myns { }",
                    "namespace detail::impl { }"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "include": QueryPattern(
                pattern="""
                (preproc_include 
                    path: (string_literal) @structure.include.path) @structure.include
                """,
                extract=lambda node: {
                    "path": node.get("path", {}).get("text", "").strip('"<>')
                },
                description="Matches C++ include directives",
                examples=[
                    "#include <vector>",
                    "#include \"myheader.h\""
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "preprocessor": QueryPattern(
                pattern="""[
                    (preproc_ifdef
                        name: (identifier) @preproc.ifdef.name) @preproc.ifdef
                    (preproc_def
                        name: (identifier) @preproc.def.name
                        value: (_)? @preproc.def.value) @preproc.def
                ]""",
                extract=lambda node: {
                    "type": node["node"].type,
                    "name": node["captures"].get("preproc.ifdef.name", {}).get("text", "") or 
                           node["captures"].get("preproc.def.name", {}).get("text", ""),
                    "value": node["captures"].get("preproc.def.value", {}).get("text", "")
                },
                description="Matches C++ preprocessor directives",
                examples=[
                    "#ifdef DEBUG",
                    "#define MAX_SIZE 100"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.CODE_PATTERNS: {
        PatternPurpose.UNDERSTANDING: {
            "memory_management": QueryPattern(
                pattern="""[
                    (call_expression
                        function: (identifier) @pattern.allocator
                        (#match? @pattern.allocator "^(new|malloc|calloc|realloc)$")
                        arguments: (_)? @pattern.alloc.args) @pattern.allocation,
                    (call_expression
                        function: (identifier) @pattern.deallocator
                        (#match? @pattern.deallocator "^(delete|free)$")
                        arguments: (_)? @pattern.dealloc.args) @pattern.deallocation
                ]""",
                extract=lambda node: {
                    "is_allocation": "pattern.allocation" in node["captures"],
                    "is_deallocation": "pattern.deallocation" in node["captures"],
                    "function": node["captures"].get("pattern.allocator", {}).get("text", "") or
                              node["captures"].get("pattern.deallocator", {}).get("text", "")
                },
                description="Matches C++ memory management patterns",
                examples=[
                    "int* p = new int(42);",
                    "delete ptr;"
                ],
                category=PatternCategory.CODE_PATTERNS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.DEPENDENCIES: {
        PatternPurpose.UNDERSTANDING: {
            "external_dependencies": QueryPattern(
                pattern="""
                (preproc_include
                    path: (string_literal) @dependencies.path
                    (#match? @dependencies.path "<.*>")) @dependencies.external
                """,
                extract=lambda node: {
                    "path": node["captures"].get("dependencies.path", {}).get("text", "").strip("<>")
                },
                description="Matches C++ external library includes",
                examples=[
                    "#include <vector>",
                    "#include <boost/shared_ptr.hpp>"
                ],
                category=PatternCategory.DEPENDENCIES,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "internal_dependencies": QueryPattern(
                pattern="""
                (preproc_include
                    path: (string_literal) @dependencies.path
                    (#match? @dependencies.path "\".*\"")) @dependencies.internal
                """,
                extract=lambda node: {
                    "path": node["captures"].get("dependencies.path", {}).get("text", "").strip("\"")
                },
                description="Matches C++ internal project includes",
                examples=[
                    "#include \"myheader.h\"",
                    "#include \"../include/utils.h\""
                ],
                category=PatternCategory.DEPENDENCIES,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.BEST_PRACTICES: {
        PatternPurpose.UNDERSTANDING: {
            "smart_pointers": QueryPattern(
                pattern="""
                (declaration
                    type: (template_type 
                        name: (type_identifier) @best_practices.smart_ptr
                        (#match? @best_practices.smart_ptr "^(unique_ptr|shared_ptr|weak_ptr)$")))
                """,
                extract=lambda node: {
                    "type": node["captures"].get("best_practices.smart_ptr", {}).get("text", "")
                },
                description="Matches C++ smart pointer usage",
                examples=[
                    "std::unique_ptr<T> ptr;",
                    "auto sp = std::make_shared<MyClass>();"
                ],
                category=PatternCategory.BEST_PRACTICES,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "raii_pattern": QueryPattern(
                pattern="""
                (class_specifier
                    body: (field_declaration_list
                        (field_declaration
                            type: (type_identifier) @best_practices.resource_type)))
                """,
                extract=lambda node: {
                    "resource_type": node["captures"].get("best_practices.resource_type", {}).get("text", "")
                },
                description="Matches C++ RAII pattern usage",
                examples=[
                    "class File { std::fstream file; };",
                    "class Lock { std::mutex mtx; };"
                ],
                category=PatternCategory.BEST_PRACTICES,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.COMMON_ISSUES: {
        PatternPurpose.UNDERSTANDING: {
            "memory_leaks": QueryPattern(
                pattern="""[
                    (call_expression
                        function: (identifier) @issues.alloc
                        (#match? @issues.alloc "^(new|malloc|calloc)$"))
                        ; Missing corresponding delete/free
                ]""",
                extract=lambda node: {
                    "allocator": node["captures"].get("issues.alloc", {}).get("text", "")
                },
                description="Matches potential C++ memory leak patterns",
                examples=[
                    "new int[10]; // No delete[]",
                    "malloc(size); // No free"
                ],
                category=PatternCategory.COMMON_ISSUES,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            "null_pointer_issues": QueryPattern(
                pattern="""
                (binary_expression
                    left: (pointer_expression) @issues.pointer
                    operator: "->") @issues.null_check_missing
                """,
                extract=lambda node: {
                    "pointer": node["captures"].get("issues.pointer", {}).get("text", "")
                },
                description="Matches potential C++ null pointer dereference patterns",
                examples=[
                    "ptr->method(); // No null check",
                    "obj->field; // Missing null check"
                ],
                category=PatternCategory.COMMON_ISSUES,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.USER_PATTERNS: {
        PatternPurpose.UNDERSTANDING: {
            "naming_conventions": QueryPattern(
                pattern="""[
                    (function_definition
                        declarator: (function_declarator
                            declarator: (_) @user.function.name)),
                    (class_specifier
                        name: (type_identifier) @user.class.name)
                ]""",
                extract=lambda node: {
                    "name": node["captures"].get("user.function.name", {}).get("text", "") or
                           node["captures"].get("user.class.name", {}).get("text", ""),
                    "style": "snake_case" if "_" in node["text"] else "camelCase"
                },
                description="Matches C++ naming convention patterns",
                examples=[
                    "void my_function();",
                    "class MyClass { };"
                ],
                category=PatternCategory.USER_PATTERNS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    }
}

# Repository learning patterns for C++
CPP_PATTERNS_FOR_LEARNING = {
    PatternCategory.LEARNING: {
        PatternPurpose.LEARNING: {
            "naming_conventions": QueryPattern(
                pattern="""
                [
                    (function_definition
                        declarator: (function_declarator
                            declarator: (_) @naming.function.name)) @naming.function,
                            
                    (class_specifier
                        name: (type_identifier) @naming.class.name) @naming.class,
                        
                    (namespace_definition
                        name: (identifier) @naming.namespace.name) @naming.namespace,
                        
                    (declaration
                        type: (_) @naming.variable.type
                        declarator: (identifier) @naming.variable.name) @naming.variable
                ]
                """,
                extract=lambda node: {
                    "type": "naming_convention_pattern",
                    "entity_type": ("function" if "naming.function.name" in node["captures"] else
                                   "class" if "naming.class.name" in node["captures"] else
                                   "namespace" if "naming.namespace.name" in node["captures"] else
                                   "variable"),
                    "name": (node["captures"].get("naming.function.name", {}).get("text", "") or
                            node["captures"].get("naming.class.name", {}).get("text", "") or
                            node["captures"].get("naming.namespace.name", {}).get("text", "") or
                            node["captures"].get("naming.variable.name", {}).get("text", "")),
                    "is_snake_case": "_" in (node["captures"].get("naming.function.name", {}).get("text", "") or 
                                           node["captures"].get("naming.variable.name", {}).get("text", "")),
                    "is_camel_case": not "_" in (node["captures"].get("naming.function.name", {}).get("text", "") or 
                                               node["captures"].get("naming.variable.name", {}).get("text", ""))
                },
                description="Matches C++ naming conventions",
                examples=[
                    "void my_function();",
                    "class MyClass { };"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "template_usage": QueryPattern(
                pattern="""
                [
                    (template_declaration
                        parameters: (template_parameter_list) @template.params
                        declaration: (_) @template.declaration) @template.def
                ]
                """,
                extract=lambda node: {
                    "type": "template_usage_pattern",
                    "parameter_count": len(node["captures"].get("template.params", {}).get("text", "").split(",")),
                    "is_class_template": "class" in node["captures"].get("template.declaration", {}).get("text", ""),
                    "is_function_template": "(" in node["captures"].get("template.declaration", {}).get("text", "")
                },
                description="Matches C++ template usage patterns",
                examples=[
                    "template<typename T> class Container { };",
                    "template<class T> void func(T arg) { }"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "error_handling": QueryPattern(
                pattern="""
                [
                    (try_statement
                        body: (compound_statement) @error.try.body
                        [(catch_clause
                            type: (_) @error.catch.type
                            name: (identifier)? @error.catch.name
                            body: (compound_statement) @error.catch.body) @error.catch]) @error.try,
                            
                    (throw_expression
                        value: (_)? @error.throw.value) @error.throw
                ]
                """,
                extract=lambda node: {
                    "type": "error_handling_pattern",
                    "has_try_catch": "error.try" in node["captures"],
                    "has_catch": "error.catch" in node["captures"],
                    "is_throw": "error.throw" in node["captures"],
                    "exception_type": node["captures"].get("error.catch.type", {}).get("text", "")
                },
                description="Matches C++ error handling patterns",
                examples=[
                    "try { } catch (std::exception& e) { }",
                    "throw MyException();"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "memory_management": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (identifier) @memory.allocator
                        (#match? @memory.allocator "^(new|malloc|calloc|realloc)$")
                        arguments: (_)? @memory.alloc.args) @memory.allocation,
                        
                    (call_expression
                        function: (identifier) @memory.deallocator
                        (#match? @memory.deallocator "^(delete|free)$")
                        arguments: (_)? @memory.dealloc.args) @memory.deallocation,
                        
                    (destructor_name) @memory.destructor
                ]
                """,
                extract=lambda node: {
                    "type": "memory_management_pattern",
                    "is_allocation": "memory.allocation" in node["captures"],
                    "is_deallocation": "memory.deallocation" in node["captures"],
                    "has_destructor": "memory.destructor" in node["captures"],
                    "allocator": node["captures"].get("memory.allocator", {}).get("text", ""),
                    "deallocator": node["captures"].get("memory.deallocator", {}).get("text", "")
                },
                description="Matches C++ memory management patterns",
                examples=[
                    "int* p = new int(42);",
                    "delete ptr;",
                    "~MyClass() { }"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            )
        }
    }
}

# Add the repository learning patterns to the main patterns
CPP_PATTERNS.update(CPP_PATTERNS_FOR_LEARNING) 