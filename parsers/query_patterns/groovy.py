"""Query patterns for Groovy files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

GROOVY_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (method_declaration
                        name: (identifier) @syntax.function.name
                        parameters: (parameter_list)? @syntax.function.params
                        body: (block) @syntax.function.body) @syntax.function.def,
                    (closure_expression
                        parameters: (parameter_list)? @syntax.function.closure.params
                        body: (block) @syntax.function.closure.body) @syntax.function.closure
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function",
                    "is_closure": "syntax.function.closure" in node["captures"]
                }
            ),
            "class": QueryPattern(
                pattern="""
                (class_declaration
                    name: (identifier) @syntax.class.name
                    body: (class_body) @syntax.class.body) @syntax.class.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                    "type": "class"
                }
            ),
            "interface": QueryPattern(
                pattern="""
                (interface_declaration
                    name: (identifier) @syntax.interface.name
                    body: (interface_body) @syntax.interface.body) @syntax.interface.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.interface.name", {}).get("text", ""),
                    "type": "interface"
                }
            ),
            "enum": QueryPattern(
                pattern="""
                (enum_declaration
                    name: (identifier) @syntax.enum.name
                    body: (enum_body) @syntax.enum.body) @syntax.enum.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.enum.name", {}).get("text", ""),
                    "type": "enum"
                }
            ),
            "decorator": QueryPattern(
                pattern="""
                (annotation
                    name: (identifier) @syntax.decorator.name
                    arguments: (annotation_argument_list)? @syntax.decorator.args) @syntax.decorator.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.decorator.name", {}).get("text", ""),
                    "type": "decorator"
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (variable_declaration
                        name: (identifier) @semantics.variable.name
                        value: (_)? @semantics.variable.value) @semantics.variable.def,
                    (field_declaration
                        name: (identifier) @semantics.variable.field.name
                        value: (_)? @semantics.variable.field.value) @semantics.variable.field
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("semantics.variable.name", {}).get("text", "") or
                        node["captures"].get("semantics.variable.field.name", {}).get("text", "")
                    ),
                    "type": "variable",
                    "is_field": "semantics.variable.field" in node["captures"]
                }
            ),
            "expression": QueryPattern(
                pattern="""
                [
                    (method_call
                        name: (identifier) @semantics.expression.name
                        arguments: (argument_list)? @semantics.expression.args) @semantics.expression.call,
                    (property_expression
                        object: (_) @semantics.expression.property.object
                        property: (identifier) @semantics.expression.property.name) @semantics.expression.property
                ]
                """,
                extract=lambda node: {
                    "type": "expression",
                    "expression_type": (
                        "method_call" if "semantics.expression.call" in node["captures"] else
                        "property_access" if "semantics.expression.property" in node["captures"] else
                        "other"
                    )
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (line_comment) @documentation.comment.line,
                    (block_comment) @documentation.comment.block
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment.line", {}).get("text", "") or
                        node["captures"].get("documentation.comment.block", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_block": "documentation.comment.block" in node["captures"]
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "package": QueryPattern(
                pattern="""
                (package_declaration
                    name: (_) @structure.package.name) @structure.package.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.package.name", {}).get("text", ""),
                    "type": "package"
                }
            ),
            "import": QueryPattern(
                pattern="""
                (import_declaration
                    name: (_) @structure.import.name) @structure.import.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.import.name", {}).get("text", ""),
                    "type": "import"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "build_system_patterns": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "pattern_type": "build_system",
                    "is_gradle_task": "build.gradle.task" in node["captures"],
                    "is_gradle_method": "build.method" in node["captures"],
                    "method_name": (
                        node["captures"].get("build.gradle.task", {}).get("text", "") or
                        node["captures"].get("build.method", {}).get("text", "")
                    ),
                    "is_build_related": True
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "method_chaining": QueryPattern(
                pattern="""
                (method_invocation_chain
                    receiver: (_) @chain.receiver
                    chain: (_)+ @chain.methods) @chain.expression
                """,
                extract=lambda node: {
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
            ),
            "closure_patterns": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "pattern_type": "closure",
                    "has_parameters": "closure.params" in node["captures"] and node["captures"].get("closure.params", {}).get("text", ""),
                    "is_passed_as_argument": "closure.with_arg" in node["captures"],
                    "method_taking_closure": node["captures"].get("closure.method", {}).get("text", ""),
                    "closure_complexity": len((node["captures"].get("closure.body", {}).get("text", "") or "").split("\n"))
                }
            )
        },
        PatternPurpose.DSL: {
            "dsl_usage": QueryPattern(
                pattern="""
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
                extract=lambda node: {
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
            )
        }
    }
} 