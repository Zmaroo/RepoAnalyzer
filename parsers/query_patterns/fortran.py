"""Query patterns for Fortran files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

FORTRAN_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_stmt
                        name: (_) @syntax.function.name
                        argument_list: (_)? @syntax.function.params
                        result: (_)? @syntax.function.result) @syntax.function.def,
                    (subroutine_stmt
                        name: (_) @syntax.function.name
                        argument_list: (_)? @syntax.function.params) @syntax.function.def,
                    (end_subroutine_stmt
                        name: (_)? @syntax.function.end_name) @syntax.function.end,
                    (end_function_stmt
                        name: (_)? @syntax.function.end_name) @syntax.function.end
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function"
                }
            ),
            "type": QueryPattern(
                pattern="""
                [
                    (specification_stmt
                        type: (_) @syntax.type.name
                        list: (_) @syntax.type.variables) @syntax.type.def,
                    (derived_type_stmt
                        name: (_) @syntax.type.name) @syntax.type.derived_def,
                    (end_type_stmt
                        name: (_)? @syntax.type.end_name) @syntax.type.end
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.type.name", {}).get("text", ""),
                    "type": "type"
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (specification_stmt
                        type: (_) @semantics.variable.type
                        attribute: (_)* @semantics.variable.attr
                        list: (_) @semantics.variable.names) @semantics.variable.def,
                    (entity_decl
                        name: (_) @semantics.variable.name
                        array_spec: (_)? @semantics.variable.array_spec
                        initialization: (_)? @semantics.variable.init) @semantics.variable.entity
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                    "type": "variable"
                }
            ),
            "expression": QueryPattern(
                pattern="""
                [
                    (binary_op
                        (_) @semantics.expression.left
                        _ @semantics.expression.op
                        (_) @semantics.expression.right) @semantics.expression.binary,
                    (parenthesized_expr
                        (_) @semantics.expression.inner) @semantics.expression.paren,
                    (array_ref
                        base: (_) @semantics.expression.array
                        section_subscript_list: (_) @semantics.expression.indices) @semantics.expression.array_access
                ]
                """,
                extract=lambda node: {
                    "type": "expression",
                    "expression_type": "binary_op" if "semantics.expression.binary" in node["captures"] else "array_access"
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="(comment) @documentation.comment",
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "type": "comment"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "module": QueryPattern(
                pattern="""
                [
                    (module_stmt
                        name: (_) @structure.module.name) @structure.module.def,
                    (end_module_stmt
                        name: (_)? @structure.module.end_name) @structure.module.end
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.module.name", {}).get("text", ""),
                    "type": "module"
                }
            ),
            "import": QueryPattern(
                pattern="""
                [
                    (use_stmt
                        module: (_) @structure.import.module
                        only: (_)? @structure.import.only) @structure.import.use,
                    (include_stmt
                        path: (_) @structure.import.path) @structure.import.include
                ]
                """,
                extract=lambda node: {
                    "module": node["captures"].get("structure.import.module", {}).get("text", ""),
                    "type": "import"
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "numerical_computing": QueryPattern(
                pattern="""
                [
                    (specification_stmt
                        type: (_) @num.type.name
                        list: (_) @num.type.vars) @num.type,
                        
                    (binary_op
                        (_) @num.op.left
                        _
                        (_) @num.op.right) @num.op,
                        
                    (call_stmt
                        procedure: (_) @num.call.name
                        argument_list: (_) @num.call.args) @num.call,
                        
                    (do_stmt
                        loop_control: (_) @num.loop.control) @num.loop,
                        
                    (if_stmt
                        condition: (_) @num.if.condition) @num.if
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "type_declaration" if "num.type" in node["captures"] else
                        "operation" if "num.op" in node["captures"] else
                        "function_call" if "num.call" in node["captures"] else
                        "loop" if "num.loop" in node["captures"] else
                        "conditional" if "num.if" in node["captures"] else
                        "other"
                    ),
                    "data_type": node["captures"].get("num.type.name", {}).get("text", "").lower(),
                    "is_numerical_type": any(
                        num_type in (node["captures"].get("num.type.name", {}).get("text", "") or "").lower()
                        for num_type in ["real", "integer", "complex", "double precision"]
                    ),
                    "uses_numerical_function": any(
                        num_func.lower() in (node["captures"].get("num.call.name", {}).get("text", "") or "").lower()
                        for num_func in ["sin", "cos", "tan", "exp", "log", "sqrt", "abs", "max", "min"]
                    ),
                    "has_loop": "num.loop" in node["captures"],
                    "has_conditional": "num.if" in node["captures"]
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "array_operations": QueryPattern(
                pattern="""
                [
                    (specification_stmt
                        type: (_) @array.type
                        list: (_) @array.vars
                        (#match? @array.vars "\\(.*:.*\\)")) @array.decl,
                        
                    (array_ref
                        base: (_) @array.name
                        section_subscript_list: (_) @array.indices) @array.ref,
                        
                    (binary_op
                        (array_ref) @array.op.arr
                        _ @array.op.operator
                        (_) @array.op.other) @array.op,
                        
                    (call_stmt
                        procedure: (_) @array.call.name
                        argument_list: (_) @array.call.args
                        (#match? @array.call.args ".*reshape.*|.*transpose.*|.*matmul.*")) @array.call
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "array_declaration" if "array.decl" in node["captures"] else
                        "array_reference" if "array.ref" in node["captures"] else
                        "array_operation" if "array.op" in node["captures"] else
                        "array_function" if "array.call" in node["captures"] else
                        "other"
                    ),
                    "uses_slicing": ":" in (node["captures"].get("array.indices", {}).get("text", "") or ""),
                    "uses_array_intrinsic": any(
                        arr_func.lower() in (node["captures"].get("array.call.name", {}).get("text", "") or "").lower()
                        for arr_func in ["reshape", "transpose", "matmul", "pack", "unpack", "cshift", "eoshift"]
                    ),
                    "uses_array_operation": "array.op" in node["captures"],
                    "array_name": node["captures"].get("array.name", {}).get("text", "")
                }
            )
        },
        PatternPurpose.ERROR_HANDLING: {
            "io_operations": QueryPattern(
                pattern="""
                [
                    (io_stmt
                        io_control: (_) @io.control) @io,
                        
                    (open_stmt
                        io_control: (_) @io.open.control) @io.open,
                        
                    (close_stmt
                        io_control: (_) @io.close.control) @io.close,
                        
                    (read_stmt
                        io_control: (_) @io.read.control
                        items: (_)? @io.read.items) @io.read,
                        
                    (write_stmt
                        io_control: (_) @io.write.control
                        items: (_)? @io.write.items) @io.write,
                        
                    (print_stmt
                        format: (_) @io.print.format
                        items: (_)? @io.print.items) @io.print
                ]
                """,
                extract=lambda node: {
                    "io_operation": (
                        "open" if "io.open" in node["captures"] else
                        "close" if "io.close" in node["captures"] else
                        "read" if "io.read" in node["captures"] else
                        "write" if "io.write" in node["captures"] else
                        "print" if "io.print" in node["captures"] else
                        "other"
                    ),
                    "uses_file_io": any(
                        io_op in node["captures"]
                        for io_op in ["io.open", "io.close", "io.read", "io.write"]
                    ),
                    "uses_formatted_io": (
                        "*" not in (node["captures"].get("io.read.control", {}).get("text", "") or "") and
                        "*" not in (node["captures"].get("io.write.control", {}).get("text", "") or "")
                    ),
                    "uses_print": "io.print" in node["captures"]
                }
            )
        }
    }
} 