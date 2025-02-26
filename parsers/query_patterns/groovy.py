"""Query patterns for Groovy files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

GROOVY_PATTERNS_FOR_LEARNING = {
    "build_system_patterns": {
        "pattern": """
        [
            (class_declaration
                body: (class_body 
                    (method_declaration 
                        name: (identifier) @build.gradle.task
                        (#match? @build.gradle.task "^task|apply|dependencies|repositories")))) @build.gradle.class,
            (method_call
                name: (identifier) @build.method
                (#match? @build.method "^apply|dependencies|repositories|plugins|task")) @build.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "build_system",
            "is_gradle_task": "build.gradle.task" in node["captures"],
            "is_gradle_method": "build.method" in node["captures"],
            "method_name": (
                node["captures"].get("build.gradle.task", {}).get("text", "") or
                node["captures"].get("build.method", {}).get("text", "")
            ),
            "is_build_related": True
        }
    },
    
    "method_chaining": {
        "pattern": """
        (method_invocation_chain
            receiver: (_) @chain.receiver
            chain: (_)+ @chain.methods) @chain.expression
        """,
        "extract": lambda node: {
            "pattern_type": "method_chaining",
            "chain_length": len(node["captures"].get("chain.methods", {}).get("text", "").split(".")),
            "uses_builder_pattern": any(
                builder in (node["captures"].get("chain.methods", {}).get("text", "") or "")
                for builder in ["build", "create", "with", "add"]
            ),
            "uses_stream_api": any(
                stream in (node["captures"].get("chain.methods", {}).get("text", "") or "")
                for stream in ["stream", "filter", "map", "collect", "forEach"]
            )
        }
    },
    
    "closure_patterns": {
        "pattern": """
        [
            (closure_expression
                parameters: (parameter_list)? @closure.params
                body: (block) @closure.body) @closure.def,
                
            (method_call
                name: (identifier) @closure.method
                arguments: (argument_list
                    (closure_expression) @closure.arg)) @closure.with_arg
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "closure",
            "has_parameters": "closure.params" in node["captures"] and node["captures"].get("closure.params", {}).get("text", ""),
            "is_passed_as_argument": "closure.with_arg" in node["captures"],
            "method_taking_closure": node["captures"].get("closure.method", {}).get("text", ""),
            "closure_complexity": len((node["captures"].get("closure.body", {}).get("text", "") or "").split("\n"))
        }
    },
    
    "dsl_usage": {
        "pattern": """
        [
            (method_call
                name: (identifier) @dsl.method) @dsl.call,
                
            (block 
                (expression_statement
                    (method_call
                        name: (identifier) @dsl.block.method
                        arguments: (argument_list)? @dsl.block.args)) @dsl.block.stmt) @dsl.block
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "dsl_usage",
            "is_likely_dsl": any(
                dsl in (
                    node["captures"].get("dsl.method", {}).get("text", "") or
                    node["captures"].get("dsl.block.method", {}).get("text", "") or ""
                )
                for dsl in ["pipeline", "stage", "node", "steps", "sh", "script", "gradle", "task", "depends"]
            ),
            "method_name": (
                node["captures"].get("dsl.method", {}).get("text", "") or
                node["captures"].get("dsl.block.method", {}).get("text", "")
            ),
            "is_jenkins_pipeline": any(
                jenkins in (
                    node["captures"].get("dsl.method", {}).get("text", "") or
                    node["captures"].get("dsl.block.method", {}).get("text", "") or ""
                )
                for jenkins in ["pipeline", "stage", "node", "steps", "sh", "script", "agent"]
            ),
            "is_gradle_script": any(
                gradle in (
                    node["captures"].get("dsl.method", {}).get("text", "") or
                    node["captures"].get("dsl.block.method", {}).get("text", "") or ""
                )
                for gradle in ["apply", "dependencies", "repositories", "plugins", "task"]
            )
        }
    }
}

GROOVY_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (method_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list)? @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def,
                (closure_expression
                    parameters: (parameter_list)? @syntax.function.closure.params
                    body: (block) @syntax.function.closure.body) @syntax.function.closure
            ]
            """
        },
        "class": {
            "pattern": """
            (class_declaration
                name: (identifier) @syntax.class.name
                body: (class_body) @syntax.class.body) @syntax.class.def
            """
        },
        "interface": {
            "pattern": """
            (interface_declaration
                name: (identifier) @syntax.interface.name
                body: (interface_body) @syntax.interface.body) @syntax.interface.def
            """
        },
        "enum": {
            "pattern": """
            (enum_declaration
                name: (identifier) @syntax.enum.name
                body: (enum_body) @syntax.enum.body) @syntax.enum.def
            """
        },
        "decorator": {
            "pattern": """
            (annotation
                name: (identifier) @syntax.decorator.name
                arguments: (annotation_argument_list)? @syntax.decorator.args) @syntax.decorator.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_declaration
                    name: (identifier) @semantics.variable.name
                    value: (_)? @semantics.variable.value) @semantics.variable.def,
                (field_declaration
                    name: (identifier) @semantics.variable.field.name
                    value: (_)? @semantics.variable.field.value) @semantics.variable.field
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (method_call
                    name: (identifier) @semantics.expression.name
                    arguments: (argument_list)? @semantics.expression.args) @semantics.expression.call,
                (property_expression
                    object: (_) @semantics.expression.property.object
                    property: (identifier) @semantics.expression.property.name) @semantics.expression.property
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (line_comment) @documentation.comment.line,
                (block_comment) @documentation.comment.block
            ]
            """
        }
    },

    "structure": {
        "package": {
            "pattern": """
            (package_declaration
                name: (_) @structure.package.name) @structure.package.def
            """
        },
        "import": {
            "pattern": """
            (import_declaration
                name: (_) @structure.import.name) @structure.import.def
            """
        }
    },
    
    "REPOSITORY_LEARNING": GROOVY_PATTERNS_FOR_LEARNING
} 