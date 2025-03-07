"""
Query patterns for Pascal files.
"""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
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

    "exception": {
        "pattern": """
        (try_statement
            body: (_) @structure.exception.try
            handlers: (except_handler_list)? @structure.exception.handlers
            finally: (finally_clause)? @structure.exception.finally) @structure.exception.try
        """
    }
}

PASCAL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
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
                """,
                extract=lambda node: {
                    "name": (
                        node["captures"].get("syntax.function.name", {}).get("text", "") or
                        node["captures"].get("syntax.procedure.name", {}).get("text", "")
                    ),
                    "type": "function" if "syntax.function.def" in node["captures"] else "procedure",
                    "has_params": any(
                        key in node["captures"] for key in 
                        ["syntax.function.params", "syntax.procedure.params"]
                    ),
                    "has_return_type": "syntax.function.return" in node["captures"]
                }
            ),
            "class": QueryPattern(
                pattern="""
                [
                    (class_type
                        name: (identifier) @syntax.class.name
                        heritage: (heritage_list)? @syntax.class.heritage
                        members: (class_member_list)? @syntax.class.members) @syntax.class.def,
                    (object_type
                        members: (object_member_list)? @syntax.object.members) @syntax.object.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                    "type": "class" if "syntax.class.def" in node["captures"] else "object",
                    "has_heritage": "syntax.class.heritage" in node["captures"],
                    "has_members": any(
                        key in node["captures"] for key in 
                        ["syntax.class.members", "syntax.object.members"]
                    )
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "program": QueryPattern(
                pattern="""
                [
                    (program
                        name: (identifier) @structure.program.name
                        block: (block) @structure.program.body) @structure.program.def,
                    (unit
                        name: (identifier) @structure.unit.name
                        interface: (interface_section) @structure.unit.interface
                        implementation: (implementation_section) @structure.unit.implementation) @structure.unit.def
                ]
                """,
                extract=lambda node: {
                    "type": "program" if "structure.program.def" in node["captures"] else "unit",
                    "name": (
                        node["captures"].get("structure.program.name", {}).get("text", "") or
                        node["captures"].get("structure.unit.name", {}).get("text", "")
                    ),
                    "has_interface": "structure.unit.interface" in node["captures"],
                    "has_implementation": "structure.unit.implementation" in node["captures"]
                }
            ),
            "uses": QueryPattern(
                pattern="""
                (uses_clause
                    units: (identifier_list) @structure.uses.units) @structure.uses.def
                """,
                extract=lambda node: {
                    "type": "uses",
                    "units": node["captures"].get("structure.uses.units", {}).get("text", ""),
                    "unit_count": len((node["captures"].get("structure.uses.units", {}).get("text", "") or "").split(","))
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
                    (directive) @documentation.directive
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment", {}).get("text", "") or
                        node["captures"].get("documentation.directive", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_directive": "documentation.directive" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.OOP: {
            "object_oriented": QueryPattern(
                pattern="""
                [
                    (class_type
                        name: (identifier) @learning.class.name
                        heritage: (heritage_list)? @learning.class.heritage
                        members: (class_member_list)? @learning.class.members) @learning.class.def,
                    (object_type
                        members: (object_member_list)? @learning.object.members) @learning.object.def,
                    (method_call
                        object: (_) @learning.method.obj
                        name: (identifier) @learning.method.name
                        arguments: (argument_list)? @learning.method.args) @learning.method.call
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "object_oriented",
                    "is_class": "learning.class.def" in node["captures"],
                    "is_object": "learning.object.def" in node["captures"],
                    "is_method_call": "learning.method.call" in node["captures"],
                    "class_name": node["captures"].get("learning.class.name", {}).get("text", ""),
                    "heritage": node["captures"].get("learning.class.heritage", {}).get("text", ""),
                    "method_name": node["captures"].get("learning.method.name", {}).get("text", ""),
                    "has_inheritance": "learning.class.heritage" in node["captures"],
                    "member_count": len((
                        node["captures"].get("learning.class.members", {}).get("text", "") or 
                        node["captures"].get("learning.object.members", {}).get("text", "") or
                        "").split(";")
                    ) if (
                        node["captures"].get("learning.class.members", {}).get("text", "") or
                        node["captures"].get("learning.object.members", {}).get("text", "")
                    ) else 0
                }
            )
        },
        PatternPurpose.TYPE_SAFETY: {
            "type_safety": QueryPattern(
                pattern="""
                [
                    (type_declaration
                        name: (identifier) @learning.type.name
                        type: (_) @learning.type.def) @learning.type.decl,
                    (record_type
                        fields: (field_list) @learning.record.fields) @learning.record.type,
                    (enum_type
                        identifiers: (identifier_list) @learning.enum.values) @learning.enum.type,
                    (variable_declaration
                        names: (identifier_list) @learning.var.names
                        type: (_) @learning.var.type) @learning.var.decl
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "type_safety",
                    "is_type_declaration": "learning.type.decl" in node["captures"],
                    "is_record": "learning.record.type" in node["captures"],
                    "is_enum": "learning.enum.type" in node["captures"],
                    "is_variable": "learning.var.decl" in node["captures"],
                    "type_name": node["captures"].get("learning.type.name", {}).get("text", ""),
                    "record_field_count": len((node["captures"].get("learning.record.fields", {}).get("text", "") or "").split(";")) if node["captures"].get("learning.record.fields", {}).get("text", "") else 0,
                    "enum_value_count": len((node["captures"].get("learning.enum.values", {}).get("text", "") or "").split(",")) if node["captures"].get("learning.enum.values", {}).get("text", "") else 0,
                    "variable_type": node["captures"].get("learning.var.type", {}).get("text", ""),
                    "variable_count": len((node["captures"].get("learning.var.names", {}).get("text", "") or "").split(",")) if node["captures"].get("learning.var.names", {}).get("text", "") else 0
                }
            )
        },
        PatternPurpose.PROCEDURES: {
            "procedural_patterns": QueryPattern(
                pattern="""
                [
                    (function_declaration
                        name: (identifier) @learning.func.name
                        parameters: (formal_parameter_list)? @learning.func.params
                        return_type: (type_identifier)? @learning.func.return
                        body: (block) @learning.func.body) @learning.func.def,
                    (procedure_declaration
                        name: (identifier) @learning.proc.name
                        parameters: (formal_parameter_list)? @learning.proc.params
                        body: (block) @learning.proc.body) @learning.proc.def,
                    (function_call 
                        name: (identifier) @learning.call.name
                        arguments: (argument_list)? @learning.call.args) @learning.call.expr
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "procedural",
                    "is_function": "learning.func.def" in node["captures"],
                    "is_procedure": "learning.proc.def" in node["captures"],
                    "is_call": "learning.call.expr" in node["captures"],
                    "name": (
                        node["captures"].get("learning.func.name", {}).get("text", "") or
                        node["captures"].get("learning.proc.name", {}).get("text", "") or
                        node["captures"].get("learning.call.name", {}).get("text", "")
                    ),
                    "param_count": len((
                        node["captures"].get("learning.func.params", {}).get("text", "") or
                        node["captures"].get("learning.proc.params", {}).get("text", "") or
                        "").split(";")
                    ) if (
                        node["captures"].get("learning.func.params", {}).get("text", "") or
                        node["captures"].get("learning.proc.params", {}).get("text", "")
                    ) else 0,
                    "return_type": node["captures"].get("learning.func.return", {}).get("text", ""),
                    "arg_count": len((node["captures"].get("learning.call.args", {}).get("text", "") or "").split(",")) if node["captures"].get("learning.call.args", {}).get("text", "") else 0
                }
            )
        }
    },
    "REPOSITORY_LEARNING": PASCAL_PATTERNS_FOR_LEARNING
} 