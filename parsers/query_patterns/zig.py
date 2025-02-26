"""Query patterns for Zig files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

ZIG_PATTERNS_FOR_LEARNING = {
    "memory_management": {
        "pattern": """
        [
            (call_expression
                function: (identifier) @mem.alloc.func {
                    match: "^(alloc|allocator|allocate|create)$"
                }
                arguments: (_) @mem.alloc.args) @mem.alloc,
                
            (call_expression
                function: (identifier) @mem.free.func {
                    match: "^(free|deallocate|destroy)$"
                }
                arguments: (_) @mem.free.args) @mem.free,
                
            (pointer_type
                [(asterisk) (asterisk_asterisk)] @mem.ptr.type
                child: (_) @mem.ptr.child) @mem.ptr,
                
            (array_type
                size: (_)? @mem.array.size
                element: (_) @mem.array.element) @mem.array,
                
            (slice_type
                element: (_) @mem.slice.element) @mem.slice
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "memory_management",
            "is_allocation": "mem.alloc" in node["captures"],
            "is_free": "mem.free" in node["captures"],
            "is_pointer": "mem.ptr" in node["captures"],
            "is_array": "mem.array" in node["captures"],
            "is_slice": "mem.slice" in node["captures"],
            "alloc_function": node["captures"].get("mem.alloc.func", {}).get("text", ""),
            "free_function": node["captures"].get("mem.free.func", {}).get("text", ""),
            "pointer_type": node["captures"].get("mem.ptr.type", {}).get("text", ""),
            "pointed_type": node["captures"].get("mem.ptr.child", {}).get("text", ""),
            "array_element_type": node["captures"].get("mem.array.element", {}).get("text", ""),
            "slice_element_type": node["captures"].get("mem.slice.element", {}).get("text", ""),
            "memory_pattern_type": (
                "allocation" if "mem.alloc" in node["captures"] else
                "deallocation" if "mem.free" in node["captures"] else
                "pointer" if "mem.ptr" in node["captures"] else
                "array" if "mem.array" in node["captures"] else
                "slice" if "mem.slice" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (error_type) @error.type,
            
            (error_set_declaration
                names: (error_set_decl
                    (identifier)+ @error.set.name) @error.set.names) @error.set,
                
            (if_statement
                condition: (if_error_capture
                    value: (_) @error.capture.value
                    error_binding: (identifier) @error.capture.binding) @error.capture
                then: (_) @error.capture.then
                else: (_)? @error.capture.else) @error.capture.if,
                
            (binary_expression
                left: (_) @error.union.left
                operator: (anon_three_dots) @error.union.op {
                    match: "^!$"
                }
                right: (_) @error.union.right) @error.union,
                
            (call_expression
                function: (field_access
                    field: (field_identifier) @error.handle.field {
                        match: "^(catch|try)$"
                    }) @error.handle.func
                arguments: (_) @error.handle.args) @error.handle
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "error_handling",
            "is_error_type": "error.type" in node["captures"],
            "is_error_set": "error.set" in node["captures"],
            "is_error_capture": "error.capture" in node["captures"],
            "is_error_union": "error.union" in node["captures"],
            "is_error_handle": "error.handle" in node["captures"],
            "error_set_names": [n.get("text", "") for n in node["captures"].get("error.set.name", [])],
            "error_binding": node["captures"].get("error.capture.binding", {}).get("text", ""),
            "error_union_right": node["captures"].get("error.union.right", {}).get("text", ""),
            "error_handle_method": node["captures"].get("error.handle.field", {}).get("text", ""),
            "error_pattern_type": (
                "error_type" if "error.type" in node["captures"] else
                "error_set" if "error.set" in node["captures"] else
                "error_capture" if "error.capture" in node["captures"] else
                "error_union" if "error.union" in node["captures"] else
                "error_handle" if "error.handle" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "comptime": {
        "pattern": """
        [
            (comptime
                expression: (_) @comptime.expr) @comptime.block,
                
            (comptime_type) @comptime.type,
            
            (if_statement
                condition: (comptime) @comptime.if.cond
                then: (_) @comptime.if.then
                else: (_)? @comptime.if.else) @comptime.if,
                
            (inline
                expression: (_) @comptime.inline.expr) @comptime.inline,
                
            (call_expression
                function: (identifier) @comptime.fn.name {
                    match: "^(@[a-zA-Z][a-zA-Z0-9_]*)$"
                }
                arguments: (_) @comptime.fn.args) @comptime.fn
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "comptime",
            "is_comptime_block": "comptime.block" in node["captures"],
            "is_comptime_type": "comptime.type" in node["captures"],
            "is_comptime_if": "comptime.if" in node["captures"],
            "is_inline": "comptime.inline" in node["captures"],
            "is_builtin_fn": "comptime.fn" in node["captures"],
            "comptime_expr": node["captures"].get("comptime.expr", {}).get("text", ""),
            "builtin_function": node["captures"].get("comptime.fn.name", {}).get("text", ""),
            "comptime_pattern_type": (
                "comptime_block" if "comptime.block" in node["captures"] else
                "comptime_type" if "comptime.type" in node["captures"] else
                "comptime_if" if "comptime.if" in node["captures"] else
                "inline" if "comptime.inline" in node["captures"] else
                "builtin_function" if "comptime.fn" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "async_concurrency": {
        "pattern": """
        [
            (function_signature
                async: (async) @async.func.modifier
                name: (_) @async.func.name
                parameters: (_) @async.func.params
                return_type: (_) @async.func.return) @async.func.sig,
                
            (async_expression
                expression: (_) @async.expr.value) @async.expr,
                
            (await_expression
                expression: (_) @async.await.expr) @async.await,
                
            (suspend
                body: (_)? @async.suspend.body) @async.suspend,
                
            (resume_expression
                expression: (_) @async.resume.expr) @async.resume,
                
            (call_expression
                function: (identifier) @async.frame.func {
                    match: "^(Frame)$"
                }
                arguments: (_) @async.frame.args) @async.frame.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "async_concurrency",
            "is_async_function": "async.func.sig" in node["captures"],
            "is_async_expression": "async.expr" in node["captures"],
            "is_await": "async.await" in node["captures"],
            "is_suspend": "async.suspend" in node["captures"],
            "is_resume": "async.resume" in node["captures"],
            "is_frame": "async.frame.call" in node["captures"],
            "function_name": node["captures"].get("async.func.name", {}).get("text", ""),
            "await_expr": node["captures"].get("async.await.expr", {}).get("text", ""),
            "has_suspend_body": "async.suspend.body" in node["captures"] and node["captures"].get("async.suspend.body", {}).get("text", "") != "",
            "resume_expr": node["captures"].get("async.resume.expr", {}).get("text", ""),
            "async_pattern_type": (
                "async_function" if "async.func.sig" in node["captures"] else
                "async_expression" if "async.expr" in node["captures"] else
                "await" if "async.await" in node["captures"] else
                "suspend" if "async.suspend" in node["captures"] else
                "resume" if "async.resume" in node["captures"] else
                "frame" if "async.frame.call" in node["captures"] else
                "unknown"
            )
        }
    }
}

ZIG_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (function_definition
                signature: (function_signature
                    pub: (pub)? @syntax.function.pub
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list
                        (parameter_declaration
                            name: (identifier) @syntax.function.param.name
                            type: (_) @syntax.function.param.type)* @syntax.function.params) @syntax.function.param_list
                    return_type: (_) @syntax.function.return_type) @syntax.function.sig
                body: (block) @syntax.function.body) @syntax.function
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "is_public": "syntax.function.pub" in node["captures"] and node["captures"].get("syntax.function.pub", {}).get("text", "") != "",
                "parameters": [p.get("text", "") for p in node["captures"].get("syntax.function.param.name", [])]
            }
        },
        
        "struct": {
            "pattern": """
            (container_declaration
                pub: (pub)? @syntax.struct.pub
                root_ptr: (asterisk)? @syntax.struct.ptr
                name: (identifier) @syntax.struct.name
                fields: (container_field_declaration
                    name: (identifier) @syntax.struct.field.name
                    type: (_) @syntax.struct.field.type)* @syntax.struct.fields) @syntax.struct {
                filter: { @syntax.struct.text =~ "\\bstruct\\b" }
            }
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.struct.name", {}).get("text", ""),
                "is_public": "syntax.struct.pub" in node["captures"] and node["captures"].get("syntax.struct.pub", {}).get("text", "") != "",
                "fields": [f.get("text", "") for f in node["captures"].get("syntax.struct.field.name", [])]
            }
        },
        "enum": {
            "pattern": """
            (ErrorSetDecl
                fields: (IDENTIFIER)* @syntax.enum.fields) @syntax.enum.def
            """
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_declaration
                    pub: (pub)? @semantics.variable.pub
                    const: (const)? @semantics.variable.const
                    name: (identifier) @semantics.variable.name
                    type: (_)? @semantics.variable.type
                    value: (_) @semantics.variable.value) @semantics.variable.declaration,
                
                (assignment_statement
                    left: (_) @semantics.variable.assign.target
                    right: (_) @semantics.variable.assign.value) @semantics.variable.assignment
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                "is_constant": "semantics.variable.const" in node["captures"] and node["captures"].get("semantics.variable.const", {}).get("text", "") != "",
                "type": node["captures"].get("semantics.variable.type", {}).get("text", ""),
                "kind": "declaration" if "semantics.variable.declaration" in node["captures"] else "assignment"
            }
        },
        "type": {
            "pattern": """
            [
                (ErrorUnionExpr
                    exception: (_)? @semantics.type.error
                    type: (_) @semantics.type.value) @semantics.type.def,
                (PrefixTypeOp
                    operator: (_) @semantics.type.operator
                    type: (_) @semantics.type.value) @semantics.type.def
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (BinaryExpr) @semantics.expression.binary,
                (UnaryExpr) @semantics.expression.unary,
                (GroupedExpr) @semantics.expression.grouped,
                (InitList) @semantics.expression.init
            ]
            """
        }
    },
    
    "structure": {
        "import": {
            "pattern": """
            (call_expression
                function: (identifier) @structure.import.func {
                    match: "^@import$"
                }
                arguments: (argument_list
                    (string_literal) @structure.import.path) @structure.import.args) @structure.import
            """,
            "extract": lambda node: {
                "path": node["captures"].get("structure.import.path", {}).get("text", "")
            }
        }
    },
    
    "documentation": {
        "comment": {
            "pattern": """
            [
                (line_comment) @documentation.line,
                (container_doc_comment) @documentation.container
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.line", {}).get("text", "") or
                       node["captures"].get("documentation.container", {}).get("text", "")
            }
        }
    },
    
    "REPOSITORY_LEARNING": ZIG_PATTERNS_FOR_LEARNING
} 