"""Query patterns for PHP files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

PHP_PATTERNS_FOR_LEARNING = {
    "oop_concepts": {
        "pattern": """
        [
            (class_declaration
                modifiers: [(abstract) (final)]* @oop.class.modifier
                name: (name) @oop.class.name
                base_clause: (base_clause)? @oop.class.extends
                interfaces: (class_interface_clause)? @oop.class.implements) @oop.class,
                
            (trait_declaration
                name: (name) @oop.trait.name
                body: (declaration_list) @oop.trait.body) @oop.trait,
                
            (interface_declaration
                name: (name) @oop.interface.name
                interfaces: (interface_base_clause)? @oop.interface.extends) @oop.interface,
                
            (method_declaration
                modifiers: [(public) (private) (protected) (static) (final) (abstract)]* @oop.method.modifier
                name: (name) @oop.method.name) @oop.method
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "oop_concepts",
            "is_class": "oop.class" in node["captures"],
            "is_trait": "oop.trait" in node["captures"],
            "is_interface": "oop.interface" in node["captures"],
            "is_method": "oop.method" in node["captures"],
            "class_name": node["captures"].get("oop.class.name", {}).get("text", ""),
            "trait_name": node["captures"].get("oop.trait.name", {}).get("text", ""),
            "interface_name": node["captures"].get("oop.interface.name", {}).get("text", ""),
            "method_name": node["captures"].get("oop.method.name", {}).get("text", ""),
            "has_inheritance": "oop.class.extends" in node["captures"] and node["captures"].get("oop.class.extends", {}).get("text", ""),
            "implements_interfaces": "oop.class.implements" in node["captures"] and node["captures"].get("oop.class.implements", {}).get("text", ""),
            "is_abstract": "oop.class.modifier" in node["captures"] and "abstract" in (node["captures"].get("oop.class.modifier", {}).get("text", "") or "")
                or "oop.method.modifier" in node["captures"] and "abstract" in (node["captures"].get("oop.method.modifier", {}).get("text", "") or ""),
            "uses_access_modifier": "oop.method.modifier" in node["captures"] and any(
                modifier in (node["captures"].get("oop.method.modifier", {}).get("text", "") or "")
                for modifier in ["public", "private", "protected"]
            )
        }
    },
    
    "functional_patterns": {
        "pattern": """
        [
            (arrow_function 
                parameters: (formal_parameters) @func.arrow.params
                body: (_) @func.arrow.body) @func.arrow,
                
            (anonymous_function_creation_expression
                parameters: (formal_parameters) @func.anon.params
                body: (compound_statement) @func.anon.body) @func.anon,
                
            (function_call_expression
                function: (name) @func.call.name
                (#match? @func.call.name "^(array_map|array_filter|array_reduce|array_walk|array_map_recursive)$")
                arguments: (arguments) @func.call.args) @func.call,
                
            (array_creation_expression) @func.array
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional_patterns",
            "is_arrow_function": "func.arrow" in node["captures"],
            "is_anonymous_function": "func.anon" in node["captures"],
            "is_functional_call": "func.call" in node["captures"],
            "is_array_creation": "func.array" in node["captures"],
            "function_name": node["captures"].get("func.call.name", {}).get("text", ""),
            "arrow_param_count": len((node["captures"].get("func.arrow.params", {}).get("text", "") or "").split(",")),
            "anon_param_count": len((node["captures"].get("func.anon.params", {}).get("text", "") or "").split(",")),
            "uses_array_functions": "func.call" in node["captures"] and node["captures"].get("func.call.name", {}).get("text", "") in ["array_map", "array_filter", "array_reduce"],
            "functional_style": (
                "arrow_function" if "func.arrow" in node["captures"] else
                "anonymous_function" if "func.anon" in node["captures"] else
                "array_manipulation" if "func.call" in node["captures"] else
                "array_literal" if "func.array" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "framework_patterns": {
        "pattern": """
        [
            (namespace_definition
                name: (namespace_name) @framework.ns.name
                (#match? @framework.ns.name "^(App|Laravel|Symfony|Illuminate|Doctrine|Zend|CodeIgniter|CakePHP|Yii|Phalcon)")) @framework.ns,
                
            (class_declaration
                base_clause: (base_clause
                    (name) @framework.extends.name
                    (#match? @framework.extends.name ".*Controller$|.*Model$|.*Repository$|.*Service$"))) @framework.extends,
                    
            (attribute
                name: (qualified_name) @framework.attr.name
                arguments: (arguments)? @framework.attr.args) @framework.attr,
                
            (namespace_use_declaration
                clauses: (namespace_use_clause
                    name: (qualified_name) @framework.use.name
                    (#match? @framework.use.name "^(Laravel|Symfony|Illuminate|Doctrine|Zend|CodeIgniter|CakePHP|Yii|Phalcon)"))) @framework.use
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "framework_usage",
            "is_framework_namespace": "framework.ns" in node["captures"],
            "extends_framework_class": "framework.extends" in node["captures"],
            "uses_framework_attribute": "framework.attr" in node["captures"],
            "imports_framework": "framework.use" in node["captures"],
            "namespace_name": node["captures"].get("framework.ns.name", {}).get("text", ""),
            "base_class_name": node["captures"].get("framework.extends.name", {}).get("text", ""),
            "attribute_name": node["captures"].get("framework.attr.name", {}).get("text", ""),
            "imported_framework": node["captures"].get("framework.use.name", {}).get("text", ""),
            "framework_type": (
                "laravel" if any(
                    "Laravel" in name or "Illuminate" in name
                    for name in [
                        node["captures"].get("framework.ns.name", {}).get("text", ""),
                        node["captures"].get("framework.use.name", {}).get("text", "")
                    ]
                ) else
                "symfony" if any(
                    "Symfony" in name or "Doctrine" in name
                    for name in [
                        node["captures"].get("framework.ns.name", {}).get("text", ""),
                        node["captures"].get("framework.use.name", {}).get("text", "")
                    ]
                ) else
                "other_framework" if (
                    "framework.ns" in node["captures"] or
                    "framework.use" in node["captures"]
                ) else
                "unknown"
            )
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (try_statement
                body: (compound_statement) @error.try.body
                catch: (catch_clause
                    type: (name) @error.catch.type
                    name: (variable) @error.catch.var
                    body: (compound_statement) @error.catch.body)* @error.catch
                finally: (finally_clause)? @error.finally) @error.try,
                
            (throw_statement
                expression: (_) @error.throw.expr) @error.throw,
                
            (function_call_expression
                function: (name) @error.func.name
                (#match? @error.func.name "^(error_log|trigger_error)$")
                arguments: (arguments) @error.func.args) @error.func
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "error_handling",
            "is_try_catch": "error.try" in node["captures"],
            "is_throw": "error.throw" in node["captures"],
            "is_error_function": "error.func" in node["captures"],
            "exception_type": node["captures"].get("error.catch.type", {}).get("text", ""),
            "exception_variable": node["captures"].get("error.catch.var", {}).get("text", ""),
            "thrown_expression": node["captures"].get("error.throw.expr", {}).get("text", ""),
            "error_function": node["captures"].get("error.func.name", {}).get("text", ""),
            "has_finally_block": "error.finally" in node["captures"],
            "error_handling_style": (
                "try_catch" if "error.try" in node["captures"] else
                "throw" if "error.throw" in node["captures"] else
                "function" if "error.func" in node["captures"] else
                "unknown"
            )
        }
    }
}

PHP_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (name) @syntax.function.name
                    parameters: (formal_parameters) @syntax.function.params
                    body: (compound_statement) @syntax.function.body) @syntax.function.def,
                (method_declaration
                    modifiers: [(public) (private) (protected) (static) (final) (abstract)]* @syntax.method.modifier
                    name: (name) @syntax.method.name
                    parameters: (formal_parameters) @syntax.method.params
                    body: (compound_statement)? @syntax.method.body) @syntax.method.def,
                (arrow_function 
                    parameters: (formal_parameters) @syntax.function.arrow.params
                    body: (_) @syntax.function.arrow.body) @syntax.function.arrow
            ]
            """
        },
        "class": {
            "pattern": """
            [
                (class_declaration
                    modifiers: [(abstract) (final)]* @syntax.class.modifier
                    name: (name) @syntax.class.name
                    base_clause: (base_clause)? @syntax.class.extends
                    interfaces: (class_interface_clause)? @syntax.class.implements
                    body: (declaration_list) @syntax.class.body) @syntax.class.def,
                (interface_declaration
                    name: (name) @syntax.interface.name
                    interfaces: (interface_base_clause)? @syntax.interface.extends
                    body: (declaration_list) @syntax.interface.body) @syntax.interface.def,
                (trait_declaration
                    name: (name) @syntax.trait.name
                    body: (declaration_list) @syntax.trait.body) @syntax.trait.def
            ]
            """
        },
        "attribute": {
            "pattern": """
            [
                (attribute
                    name: (qualified_name) @syntax.attribute.name
                    arguments: (arguments)? @syntax.attribute.args) @syntax.attribute
            ]
            """
        }
    },

    "structure": {
        "namespace": {
            "pattern": """
            [
                (namespace_definition
                    name: (namespace_name)? @structure.namespace.name
                    body: (compound_statement) @structure.namespace.body) @structure.namespace,
                (namespace_use_declaration
                    clauses: (namespace_use_clause
                        name: (qualified_name) @structure.use.name
                        alias: (namespace_aliasing_clause)? @structure.use.alias)*) @structure.use
            ]
            """
        },
        "import": {
            "pattern": """
            [
                (namespace_use_declaration
                    kind: [(function) (const)]? @structure.import.kind
                    clauses: (namespace_use_clause
                        name: (qualified_name) @structure.import.name
                        alias: (namespace_aliasing_clause)? @structure.import.alias)*) @structure.import
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (comment) @documentation.phpdoc {
                    match: "^/\\*\\*"
                }
            ]
            """
        }
    },
    
    "REPOSITORY_LEARNING": PHP_PATTERNS_FOR_LEARNING
} 