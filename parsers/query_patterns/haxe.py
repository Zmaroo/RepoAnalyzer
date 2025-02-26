"""Query patterns for Haxe files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

HAXE_PATTERNS_FOR_LEARNING = {
    "macro_patterns": {
        "pattern": """
        [
            (function_declaration
                metadata: (metadata
                    (metadata_item
                        name: (identifier) @macro.func.meta
                        (#eq? @macro.func.meta "macro"))
                    ) 
                name: (identifier) @macro.func.name) @macro.func,
                
            (call_expression
                function: (identifier) @macro.call.name
                (#match? @macro.call.name "^macro\\.|\\$")) @macro.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "macro",
            "is_macro_function": "macro.func" in node["captures"],
            "is_macro_call": "macro.call" in node["captures"],
            "macro_name": (
                node["captures"].get("macro.func.name", {}).get("text", "") or
                node["captures"].get("macro.call.name", {}).get("text", "")
            ),
            "uses_compile_time_metaprogramming": True
        }
    },
    
    "conditional_compilation": {
        "pattern": """
        [
            (preprocessor
                condition: (_) @cond.expr) @cond.directive,
                
            (metadata
                (metadata_item
                    name: (identifier) @cond.meta.name
                    (#match? @cond.meta.name "if|elseif|else|end"))) @cond.meta
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "conditional_compilation",
            "uses_preprocessor": "cond.directive" in node["captures"],
            "uses_metadata": "cond.meta" in node["captures"],
            "condition_expression": node["captures"].get("cond.expr", {}).get("text", ""),
            "metadata_directive": node["captures"].get("cond.meta.name", {}).get("text", ""),
            "is_platform_check": any(
                platform in (node["captures"].get("cond.expr", {}).get("text", "") or "")
                for platform in ["js", "cpp", "java", "cs", "python", "php", "neko", "flash"]
            )
        }
    },
    
    "type_definitions": {
        "pattern": """
        [
            (typedef_declaration
                name: (identifier) @type.alias.name
                type: (_) @type.alias.type) @type.alias,
                
            (abstract_type_declaration
                name: (identifier) @type.abstract.name
                underlying_type: (_)? @type.abstract.underlying
                body: (_) @type.abstract.body) @type.abstract,
                
            (enum_declaration
                name: (identifier) @type.enum.name
                constructors: (_)* @type.enum.constructors) @type.enum
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "type_definition",
            "is_type_alias": "type.alias" in node["captures"],
            "is_abstract_type": "type.abstract" in node["captures"],
            "is_enum_type": "type.enum" in node["captures"],
            "type_name": (
                node["captures"].get("type.alias.name", {}).get("text", "") or
                node["captures"].get("type.abstract.name", {}).get("text", "") or
                node["captures"].get("type.enum.name", {}).get("text", "")
            ),
            "is_abstract_over_primitive": any(
                primitive in (node["captures"].get("type.abstract.underlying", {}).get("text", "") or "")
                for primitive in ["Int", "Float", "String", "Bool"]
            ),
            "has_enum_constructors": "type.enum.constructors" in node["captures"] and node["captures"].get("type.enum.constructors", {}).get("text", "")
        }
    },
    
    "target_specific": {
        "pattern": """
        [
            (preprocessor
                condition: (_) @target.condition
                (#match? @target.condition "(js|cpp|java|cs|python|php|neko|flash)")) @target.directive,
                
            (metadata
                (metadata_item
                    name: (identifier) @target.meta.name
                    (#match? @target.meta.name "js|cpp|java|cs|python|php|neko|flash"))) @target.meta
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "target_specific",
            "uses_target_directive": "target.directive" in node["captures"],
            "uses_target_metadata": "target.meta" in node["captures"],
            "target_platform": (
                node["captures"].get("target.condition", {}).get("text", "") or
                node["captures"].get("target.meta.name", {}).get("text", "")
            ),
            "is_cross_platform_code": True
        }
    }
}

HAXE_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (function_declaration
                name: (identifier) @syntax.function.name
                parameters: (parameter_list)? @syntax.function.params
                body: (block)? @syntax.function.body) @syntax.function.def
            """
        },
        "class": {
            "pattern": """
            (class_declaration
                name: (identifier) @syntax.class.name
                body: (class_body)? @syntax.class.body) @syntax.class.def
            """
        },
        "interface": {
            "pattern": """
            (interface_declaration
                name: (identifier) @syntax.interface.name
                body: (interface_body)? @syntax.interface.body) @syntax.interface.def
            """
        },
        "typedef": {
            "pattern": """
            (typedef_declaration
                name: (identifier) @syntax.typedef.name
                type: (type)? @syntax.typedef.type) @syntax.typedef.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            (variable_declaration
                name: (identifier) @semantics.variable.name
                initializer: (expression)? @semantics.variable.value) @semantics.variable.def
            """
        },
        "type": {
            "pattern": """
            (type
                name: (identifier) @semantics.type.name) @semantics.type.def
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    },

    "structure": {
        "import": {
            "pattern": """
            (import_statement
                package: (package_name)? @structure.import.package
                type: (type_name)? @structure.import.type) @structure.import.def
            """
        },
        "package": {
            "pattern": """
            (package_statement
                name: (package_name) @structure.package.name) @structure.package.def
            """
        }
    },
    
    "REPOSITORY_LEARNING": HAXE_PATTERNS_FOR_LEARNING
} 