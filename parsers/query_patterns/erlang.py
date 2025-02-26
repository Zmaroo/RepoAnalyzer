"""Query patterns for Erlang files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

ERLANG_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (module_attribute
                name: (_) @naming.module.name) @naming.module,
                
            (fun_decl
                clause: (fun_clause
                    name: (_) @naming.function.name)) @naming.function,
                    
            (record_attribute
                name: (_) @naming.record.name) @naming.record,
                
            (var) @naming.variable
        ]
        """,
        "extract": lambda node: {
            "entity_type": ("module" if "naming.module.name" in node["captures"] else
                         "function" if "naming.function.name" in node["captures"] else
                         "record" if "naming.record.name" in node["captures"] else
                         "variable"),
            "name": (node["captures"].get("naming.module.name", {}).get("text", "") or
                   node["captures"].get("naming.function.name", {}).get("text", "") or
                   node["captures"].get("naming.record.name", {}).get("text", "") or
                   node["captures"].get("naming.variable", {}).get("text", "")),
            "uses_snake_case": "_" in (node["captures"].get("naming.function.name", {}).get("text", "") or ""),
            "uses_camel_case": any(
                name and not "_" in name and not name.isupper() and any(c.isupper() for c in name)
                for name in [
                    node["captures"].get("naming.function.name", {}).get("text", ""),
                    node["captures"].get("naming.record.name", {}).get("text", "")
                ] if name
            ),
            "is_all_caps": (node["captures"].get("naming.variable", {}).get("text", "") or "").isupper()
        }
    },
    
    "functional_patterns": {
        "pattern": """
        [
            (case_expr
                expr: (_) @fp.case.expr
                clauses: (_) @fp.case.clauses) @fp.case,
                
            (list_comp
                expr: (_) @fp.list_comp.expr
                qualifiers: (_) @fp.list_comp.qualifiers) @fp.list_comp,
                
            (fun_expr
                clauses: (_) @fp.lambda.clauses) @fp.lambda,
                
            (binary_op_expr
                operator: (bin_op) @fp.pipe.op
                (#match? @fp.pipe.op "\\|\\>")
                lhs: (_) @fp.pipe.left
                rhs: (_) @fp.pipe.right) @fp.pipe
        ]
        """,
        "extract": lambda node: {
            "uses_pattern_matching": "fp.case" in node["captures"],
            "uses_list_comprehension": "fp.list_comp" in node["captures"],
            "uses_lambda": "fp.lambda" in node["captures"],
            "uses_pipe": "fp.pipe" in node["captures"],
            "pattern_type": ("case" if "fp.case" in node["captures"] else
                          "list_comprehension" if "fp.list_comp" in node["captures"] else
                          "lambda" if "fp.lambda" in node["captures"] else
                          "pipe" if "fp.pipe" in node["captures"] else "other")
        }
    },
    
    "otp_patterns": {
        "pattern": """
        [
            (behaviour_attribute
                module: (_) @otp.behaviour.name) @otp.behaviour,
                
            (call
                expr: (atom) @otp.gen.call
                (#match? @otp.gen.call "^(gen_server|gen_fsm|gen_statem|gen_event|supervisor):[a-z_]+$")) @otp.gen,
                
            (call
                expr: (atom) @otp.proc.call
                (#match? @otp.proc.call "^(erlang|proc_lib):(spawn|spawn_link|spawn_monitor)")
                args: (_) @otp.proc.args) @otp.proc
        ]
        """,
        "extract": lambda node: {
            "uses_otp_behaviour": "otp.behaviour" in node["captures"],
            "uses_gen_module": "otp.gen" in node["captures"],
            "uses_process_primitives": "otp.proc" in node["captures"],
            "behaviour_name": node["captures"].get("otp.behaviour.name", {}).get("text", ""),
            "otp_pattern_type": ("behaviour" if "otp.behaviour" in node["captures"] else
                              "gen_module" if "otp.gen" in node["captures"] else
                              "process_primitive" if "otp.proc" in node["captures"] else "other")
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (try_expr
                body: (_) @error.try.body
                clauses: (_) @error.try.clauses
                catch_clauses: (_)? @error.try.catch
                after_clauses: (_)? @error.try.after) @error.try,
                
            (call
                expr: (atom) @error.raise.func
                (#match? @error.raise.func "^(throw|error|exit)$")
                args: (_) @error.raise.args) @error.raise
        ]
        """,
        "extract": lambda node: {
            "uses_try_catch": "error.try" in node["captures"],
            "has_after_clause": "error.try.after" in node["captures"] and node["captures"].get("error.try.after", {}).get("text", ""),
            "raises_exception": "error.raise" in node["captures"],
            "exception_type": node["captures"].get("error.raise.func", {}).get("text", ""),
            "error_handling_style": ("structured" if "error.try" in node["captures"] else
                                 "primitive" if "error.raise" in node["captures"] else "none")
        }
    }
}

ERLANG_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (fun_decl
                    clause: (_) @syntax.function.clause) @syntax.function.def,
                (fun_clause
                    name: (_)? @syntax.function.name
                    args: (expr_args) @syntax.function.params
                    guard: (_)? @syntax.function.guard
                    body: (clause_body) @syntax.function.body) @syntax.function.clause
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_attribute
                    name: (_) @syntax.type.name
                    args: (_)? @syntax.type.args
                    value: (_) @syntax.type.value) @syntax.type.def,
                (opaque
                    name: (_) @syntax.type.name
                    args: (_)? @syntax.type.args
                    value: (_) @syntax.type.value) @syntax.type.def
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (var) @semantics.variable,
                (record_field
                    name: (_) @semantics.variable.name
                    expr: (_)? @semantics.variable.value) @semantics.variable.def
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (binary_op_expr
                    lhs: (_) @semantics.expression.left
                    rhs: (_) @semantics.expression.right) @semantics.expression.binary,
                (call
                    expr: (_) @semantics.expression.target
                    args: (_) @semantics.expression.args) @semantics.expression.call
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": "(comment) @documentation.comment"
        },
        "docstring": {
            "pattern": """
            (comment 
                (#match? @documentation.comment "^%+\\s*@doc")) @documentation.docstring
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            (module_attribute
                name: (_) @structure.module.name) @structure.module.def
            """
        },
        "import": {
            "pattern": """
            [
                (import_attribute
                    module: (_) @structure.import.module
                    functions: (_) @structure.import.functions) @structure.import.def,
                (behaviour_attribute
                    module: (_) @structure.import.module) @structure.import.behaviour
            ]
            """
        }
    },
    
    "REPOSITORY_LEARNING": ERLANG_PATTERNS_FOR_LEARNING
} 