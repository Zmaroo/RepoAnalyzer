"""
Query patterns for Pascal files.
"""

from .common import COMMON_PATTERNS

PASCAL_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (formal_parameter_list)? @syntax.function.params
                    return_type: (type_identifier)? @syntax.function.return
                    body: (block) @syntax.function.body) @syntax.function.def,
                (procedure_declaration
                    name: (identifier) @syntax.procedure.name
                    parameters: (formal_parameter_list)? @syntax.procedure.params
                    body: (block) @syntax.procedure.body) @syntax.procedure.def
            ]
            """
        },
        "class": {
            "pattern": """
            [
                (class_type
                    name: (identifier) @syntax.class.name
                    heritage: (heritage_list)? @syntax.class.heritage
                    members: (class_member_list)? @syntax.class.members) @syntax.class.def,
                (object_type
                    members: (object_member_list)? @syntax.object.members) @syntax.object.def
            ]
            """
        },
        "conditional": {
            "pattern": """
            [
                (if_statement
                    condition: (_) @syntax.conditional.if.condition
                    consequence: (_) @syntax.conditional.if.body
                    alternative: (_)? @syntax.conditional.if.else) @syntax.conditional.if,
                (case_statement
                    expression: (_) @syntax.conditional.case.expr
                    cases: (case_selector_list) @syntax.conditional.case.selectors) @syntax.conditional.case
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (variable_declaration
                    names: (identifier_list) @semantics.variable.names
                    type: (_) @semantics.variable.type) @semantics.variable.def,
                (const_declaration
                    name: (identifier) @semantics.constant.name
                    value: (_) @semantics.constant.value) @semantics.constant.def
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_declaration
                    name: (identifier) @semantics.type.name
                    type: (_) @semantics.type.def) @semantics.type.decl,
                (record_type
                    fields: (field_list) @semantics.type.record.fields) @semantics.type.record
            ]
            """
        }
    },

    "structure": {
        "namespace": {
            "pattern": """
            [
                (program
                    name: (identifier) @structure.program.name
                    block: (block) @structure.program.body) @structure.program,
                (unit
                    name: (identifier) @structure.unit.name
                    interface: (interface_section) @structure.unit.interface
                    implementation: (implementation_section) @structure.unit.implementation) @structure.unit
            ]
            """
        },
        "import": {
            "pattern": """
            (uses_clause
                units: (identifier_list) @structure.import.units) @structure.import
            """
        },
        "exception": {
            "pattern": """
            (try_statement
                body: (_) @structure.exception.try
                handlers: (except_handler_list)? @structure.exception.handlers
                finally: (finally_clause)? @structure.exception.finally) @structure.exception.try
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (directive) @documentation.directive
            ]
            """
        }
    }
} 