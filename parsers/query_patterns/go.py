"""Query patterns for Go files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

GO_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_declaration
                        name: (_) @syntax.function.name
                        parameters: (_) @syntax.function.params
                        result: (_)? @syntax.function.result
                        body: (_) @syntax.function.body) @syntax.function.def,
                    (method_declaration
                        name: (_) @syntax.function.name
                        receiver: (_) @syntax.function.receiver
                        parameters: (_) @syntax.function.params
                        result: (_)? @syntax.function.result
                        body: (_) @syntax.function.body) @syntax.function.method
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function",
                    "is_method": "syntax.function.method" in node["captures"]
                }
            ),
            "type": QueryPattern(
                pattern="""
                [
                    (type_declaration
                        name: (_) @syntax.type.name
                        type: (_) @syntax.type.def) @syntax.type.decl,
                    (struct_type
                        fields: (_) @syntax.type.struct.fields) @syntax.type.struct,
                    (interface_type
                        methods: (_) @syntax.type.interface.methods) @syntax.type.interface
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.type.name", {}).get("text", ""),
                    "type": (
                        "struct" if "syntax.type.struct" in node["captures"] else
                        "interface" if "syntax.type.interface" in node["captures"] else
                        "type"
                    )
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (var_declaration
                        name: (_) @semantics.variable.name
                        type: (_)? @semantics.variable.type
                        value: (_)? @semantics.variable.value) @semantics.variable.def,
                    (const_declaration
                        name: (_) @semantics.variable.const.name
                        type: (_)? @semantics.variable.const.type
                        value: (_)? @semantics.variable.const.value) @semantics.variable.const,
                    (short_var_declaration
                        left: (_) @semantics.variable.short.name
                        right: (_) @semantics.variable.short.value) @semantics.variable.short
                ]
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("semantics.variable.name", {}).get("text", "") or
                        node["captures"].get("semantics.variable.const.name", {}).get("text", "") or
                        node["captures"].get("semantics.variable.short.name", {}).get("text", "")
                    ),
                    "type": "variable",
                    "is_const": "semantics.variable.const" in node["captures"],
                    "is_short_decl": "semantics.variable.short" in node["captures"]
                }
            ),
            "expression": QueryPattern(
                pattern="""
                [
                    (binary_expression
                        left: (_) @semantics.expression.binary.left
                        operator: (_) @semantics.expression.binary.op
                        right: (_) @semantics.expression.binary.right) @semantics.expression.binary,
                    (call_expression
                        function: (_) @semantics.expression.call.func
                        arguments: (_) @semantics.expression.call.args) @semantics.expression.call
                ]
                """,
                extract=lambda node: {
                    "type": "expression",
                    "expression_type": (
                        "binary" if "semantics.expression.binary" in node["captures"] else
                        "call" if "semantics.expression.call" in node["captures"] else
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
                    (comment) @documentation.comment,
                    (interpreted_string_literal) @documentation.string
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "type": "comment"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "package": QueryPattern(
                pattern="""
                (package_clause
                    name: (_) @structure.package.name) @structure.package.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.package.name", {}).get("text", ""),
                    "type": "package"
                }
            ),
            "import": QueryPattern(
                pattern="""
                [
                    (import_declaration
                        import_spec: (_) @structure.import.spec) @structure.import.def,
                    (import_spec
                        name: (_)? @structure.import.name
                        path: (_) @structure.import.path) @structure.import.spec
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.import.name", {}).get("text", ""),
                    "path": node["captures"].get("structure.import.path", {}).get("text", ""),
                    "type": "import"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.CONCURRENCY: {
            "concurrency_patterns": QueryPattern(
                pattern="""
                [
                    (go_statement
                        expression: (_) @concur.go.expr) @concur.go,
                        
                    (channel_type
                        element: (_) @concur.chan.type
                        direction: (_)? @concur.chan.dir) @concur.chan.def,
                        
                    (receive_statement
                        left: (_)? @concur.rcv.left
                        right: (_) @concur.rcv.right) @concur.rcv,
                        
                    (send_statement
                        channel: (_) @concur.send.chan
                        value: (_) @concur.send.val) @concur.send,
                        
                    (select_statement
                        communication: (_) @concur.select.comm) @concur.select,
                        
                    (communication_case
                        communication: (_) @concur.case.comm
                        block: (_) @concur.case.block) @concur.case
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "goroutine" if "concur.go" in node["captures"] else
                        "channel_definition" if "concur.chan.def" in node["captures"] else
                        "receive_operation" if "concur.rcv" in node["captures"] else
                        "send_operation" if "concur.send" in node["captures"] else
                        "select_statement" if "concur.select" in node["captures"] else
                        "communication_case" if "concur.case" in node["captures"] else
                        "other"
                    ),
                    "uses_goroutine": "concur.go" in node["captures"],
                    "uses_channel": any(chan_op in node["captures"] for chan_op in ["concur.chan.def", "concur.rcv", "concur.send"]),
                    "uses_select": "concur.select" in node["captures"],
                    "channel_direction": node["captures"].get("concur.chan.dir", {}).get("text", "bidirectional"),
                    "is_buffered_channel": "make" in (node["captures"].get("concur.chan.def", {}).get("text", "") or "") and "," in (node["captures"].get("concur.chan.def", {}).get("text", "") or "")
                }
            )
        },
        PatternPurpose.ERROR_HANDLING: {
            "error_handling": QueryPattern(
                pattern="""
                [
                    (if_statement
                        condition: (binary_expression
                            left: (_) @error.if.var
                            right: (identifier) @error.if.err
                            (#eq? @error.if.err "err"))
                        consequence: (_) @error.if.body) @error.if,
                        
                    (assignment_statement
                        left: (_) @error.assign.left
                        right: (_) @error.assign.right
                        (#match? @error.assign.left ".*err.*|.*Err.*")) @error.assign,
                        
                    (return_statement
                        expression: (_) @error.return.expr
                        (#match? @error.return.expr ".*err.*|.*Err.*|.*error.*|.*nil.*")) @error.return,
                        
                    (function_declaration
                        name: (_) @error.func.name
                        parameters: (_) @error.func.params
                        result: (_) @error.func.result
                        (#match? @error.func.result ".*error.*")) @error.func,
                        
                    (defer_statement
                        expression: (_) @error.defer.expr) @error.defer
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "error_check_if" if "error.if" in node["captures"] else
                        "error_assignment" if "error.assign" in node["captures"] else
                        "error_return" if "error.return" in node["captures"] else
                        "error_function" if "error.func" in node["captures"] else
                        "defer_statement" if "error.defer" in node["captures"] else
                        "other"
                    ),
                    "uses_error_check": "error.if" in node["captures"],
                    "returns_error": "error.return" in node["captures"] or "error.func" in node["captures"],
                    "uses_defer": "error.defer" in node["captures"],
                    "error_variable_name": (
                        node["captures"].get("error.if.err", {}).get("text", "") or
                        (node["captures"].get("error.assign.left", {}).get("text", "") if "error.assign" in node["captures"] else "")
                    ),
                    "error_handling_style": (
                        "if_err_not_nil" if "error.if" in node["captures"] and "!= nil" in (node["captures"].get("error.if.var", {}).get("text", "") or "") else
                        "if_err_comparison" if "error.if" in node["captures"] else
                        "return_error" if "error.return" in node["captures"] else
                        "other"
                    )
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "package_organization": QueryPattern(
                pattern="""
                [
                    (package_clause
                        name: (_) @pkg.name) @pkg,
                        
                    (import_declaration
                        import_spec: (_) @pkg.import.spec) @pkg.import,
                        
                    (import_spec
                        name: (_)? @pkg.spec.name
                        path: (_) @pkg.spec.path) @pkg.spec,
                        
                    (function_declaration
                        name: (_) @pkg.func.name
                        parameters: (_) @pkg.func.params
                        result: (_)? @pkg.func.result
                        body: (_) @pkg.func.body) @pkg.func,
                        
                    (method_declaration
                        name: (_) @pkg.method.name
                        receiver: (_) @pkg.method.recv
                        parameters: (_) @pkg.method.params
                        result: (_)? @pkg.method.result
                        body: (_) @pkg.method.body) @pkg.method
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "package_declaration" if "pkg" in node["captures"] else
                        "import_declaration" if "pkg.import" in node["captures"] else
                        "import_spec" if "pkg.spec" in node["captures"] else
                        "function_declaration" if "pkg.func" in node["captures"] else
                        "method_declaration" if "pkg.method" in node["captures"] else
                        "other"
                    ),
                    "package_name": node["captures"].get("pkg.name", {}).get("text", ""),
                    "import_path": node["captures"].get("pkg.spec.path", {}).get("text", "").strip('"'),
                    "uses_named_import": "pkg.spec.name" in node["captures"] and node["captures"].get("pkg.spec.name", {}).get("text", ""),
                    "is_exported_symbol": (
                        node["captures"].get("pkg.func.name", {}).get("text", "")[0:1].isupper() if "pkg.func.name" in node["captures"] else
                        node["captures"].get("pkg.method.name", {}).get("text", "")[0:1].isupper() if "pkg.method.name" in node["captures"] else
                        False
                    ),
                    "is_interface_implementation": "pkg.method" in node["captures"]
                }
            )
        },
        PatternPurpose.BEST_PRACTICES: {
            "idiomatic_go": QueryPattern(
                pattern="""
                [
                    (short_var_declaration
                        left: (_) @idiom.short.left
                        right: (_) @idiom.short.right) @idiom.short,
                        
                    (range_clause
                        left: (_)? @idiom.range.left
                        right: (_) @idiom.range.right) @idiom.range,
                        
                    (for_statement
                        initializer: (_)? @idiom.for.init
                        condition: (_)? @idiom.for.cond
                        update: (_)? @idiom.for.update
                        body: (_) @idiom.for.body) @idiom.for,
                        
                    (type_assertion_expression
                        operand: (_) @idiom.assert.expr
                        type: (_) @idiom.assert.type) @idiom.assert,
                        
                    (interface_type
                        methods: (_)? @idiom.iface.methods) @idiom.iface,
                        
                    (struct_type
                        fields: (_) @idiom.struct.fields) @idiom.struct
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "short_var_declaration" if "idiom.short" in node["captures"] else
                        "range_loop" if "idiom.range" in node["captures"] else
                        "for_loop" if "idiom.for" in node["captures"] else
                        "type_assertion" if "idiom.assert" in node["captures"] else
                        "interface_definition" if "idiom.iface" in node["captures"] else
                        "struct_definition" if "idiom.struct" in node["captures"] else
                        "other"
                    ),
                    "uses_short_declaration": "idiom.short" in node["captures"],
                    "uses_range_loop": "idiom.range" in node["captures"],
                    "uses_blank_identifier": (
                        "_" in (node["captures"].get("idiom.range.left", {}).get("text", "") or "") or
                        "_" in (node["captures"].get("idiom.short.left", {}).get("text", "") or "")
                    ),
                    "is_empty_interface": "idiom.iface" in node["captures"] and not node["captures"].get("idiom.iface.methods", {}).get("text", ""),
                    "has_comments": any(comment in node_text for comment in ["//", "/*"]
                                    for node_text in [
                                        node["captures"].get("idiom.struct.fields", {}).get("text", ""),
                                        node["captures"].get("idiom.iface.methods", {}).get("text", "")
                                    ])
                }
            )
        }
    }
} 