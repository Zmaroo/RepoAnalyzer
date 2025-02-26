"""
Query patterns for Pascal files.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

PASCAL_PATTERNS_FOR_LEARNING = {
    "program_structure": {
        "pattern": """
        [
            (program
                name: (identifier) @prog.name
                block: (block) @prog.body) @prog.def,
                
            (unit
                name: (identifier) @unit.name
                interface: (interface_section) @unit.interface
                implementation: (implementation_section) @unit.implementation) @unit.def,
                
            (uses_clause
                units: (identifier_list) @uses.units) @uses.clause
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "program_structure",
            "is_program": "prog.def" in node["captures"],
            "is_unit": "unit.def" in node["captures"],
            "is_uses_clause": "uses.clause" in node["captures"],
            "name": (
                node["captures"].get("prog.name", {}).get("text", "") or
                node["captures"].get("unit.name", {}).get("text", "")
            ),
            "has_interface": "unit.interface" in node["captures"],
            "has_implementation": "unit.implementation" in node["captures"],
            "imported_units": node["captures"].get("uses.units", {}).get("text", ""),
            "unit_count": len((node["captures"].get("uses.units", {}).get("text", "") or "").split(","))
        }
    },
    
    "procedural_patterns": {
        "pattern": """
        [
            (function_declaration
                name: (identifier) @func.name
                parameters: (formal_parameter_list)? @func.params
                return_type: (type_identifier)? @func.return
                body: (block) @func.body) @func.def,
                
            (procedure_declaration
                name: (identifier) @proc.name
                parameters: (formal_parameter_list)? @proc.params
                body: (block) @proc.body) @proc.def,
                
            (function_call 
                name: (identifier) @call.name
                arguments: (argument_list)? @call.args) @call.expr
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "procedural",
            "is_function": "func.def" in node["captures"],
            "is_procedure": "proc.def" in node["captures"],
            "is_call": "call.expr" in node["captures"],
            "name": (
                node["captures"].get("func.name", {}).get("text", "") or
                node["captures"].get("proc.name", {}).get("text", "") or
                node["captures"].get("call.name", {}).get("text", "")
            ),
            "param_count": len((
                node["captures"].get("func.params", {}).get("text", "") or
                node["captures"].get("proc.params", {}).get("text", "") or
                "").split(";")
            ) if (
                node["captures"].get("func.params", {}).get("text", "") or
                node["captures"].get("proc.params", {}).get("text", "")
            ) else 0,
            "return_type": node["captures"].get("func.return", {}).get("text", ""),
            "arg_count": len((node["captures"].get("call.args", {}).get("text", "") or "").split(",")) if node["captures"].get("call.args", {}).get("text", "") else 0
        }
    },
    
    "object_oriented": {
        "pattern": """
        [
            (class_type
                name: (identifier) @class.name
                heritage: (heritage_list)? @class.heritage
                members: (class_member_list)? @class.members) @class.def,
                
            (object_type
                members: (object_member_list)? @object.members) @object.def,
                
            (method_call
                object: (_) @method.obj
                name: (identifier) @method.name
                arguments: (argument_list)? @method.args) @method.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "object_oriented",
            "is_class": "class.def" in node["captures"],
            "is_object": "object.def" in node["captures"],
            "is_method_call": "method.call" in node["captures"],
            "class_name": node["captures"].get("class.name", {}).get("text", ""),
            "heritage": node["captures"].get("class.heritage", {}).get("text", ""),
            "method_name": node["captures"].get("method.name", {}).get("text", ""),
            "has_inheritance": "class.heritage" in node["captures"] and node["captures"].get("class.heritage", {}).get("text", ""),
            "member_count": len((
                node["captures"].get("class.members", {}).get("text", "") or 
                node["captures"].get("object.members", {}).get("text", "") or
                "").split(";")
            ) if (
                node["captures"].get("class.members", {}).get("text", "") or
                node["captures"].get("object.members", {}).get("text", "")
            ) else 0
        }
    },
    
    "type_safety": {
        "pattern": """
        [
            (type_declaration
                name: (identifier) @type.name
                type: (_) @type.def) @type.decl,
                
            (record_type
                fields: (field_list) @record.fields) @record.type,
                
            (enum_type
                identifiers: (identifier_list) @enum.values) @enum.type,
                
            (variable_declaration
                names: (identifier_list) @var.names
                type: (_) @var.type) @var.decl
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "type_safety",
            "is_type_declaration": "type.decl" in node["captures"],
            "is_record": "record.type" in node["captures"],
            "is_enum": "enum.type" in node["captures"],
            "is_variable": "var.decl" in node["captures"],
            "type_name": node["captures"].get("type.name", {}).get("text", ""),
            "record_field_count": len((node["captures"].get("record.fields", {}).get("text", "") or "").split(";")) if node["captures"].get("record.fields", {}).get("text", "") else 0,
            "enum_value_count": len((node["captures"].get("enum.values", {}).get("text", "") or "").split(",")) if node["captures"].get("enum.values", {}).get("text", "") else 0,
            "variable_type": node["captures"].get("var.type", {}).get("text", ""),
            "variable_count": len((node["captures"].get("var.names", {}).get("text", "") or "").split(",")) if node["captures"].get("var.names", {}).get("text", "") else 0
        }
    }
}

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
    },
    
    "REPOSITORY_LEARNING": PASCAL_PATTERNS_FOR_LEARNING
} 