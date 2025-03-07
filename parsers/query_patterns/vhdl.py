"""
Query patterns for VHDL files.
"""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

VHDL_PATTERNS_FOR_LEARNING = {
    "entity_architecture": {
        "pattern": """
        [
            (design_unit
                (entity_declaration
                    name: (identifier) @entity.name
                    port_clause: (port_clause
                        (interface_list
                            (interface_element
                                name: (identifier) @entity.port.name
                                mode: [(in) (out) (inout) (buffer) (linkage)] @entity.port.mode
                                type: (_) @entity.port.type)+ @entity.port.list) @entity.port.elements) @entity.port) @entity.decl),
                    
            (design_unit
                (architecture_body
                    name: (identifier) @arch.name
                    entity: (identifier) @arch.entity
                    declarative_part: (architecture_declarative_part
                        [(signal_declaration) (constant_declaration) (component_declaration) (subtype_declaration) (function_body) (procedure_body)]* @arch.decl_items) @arch.decl
                    statement_part: (concurrent_statement_part
                        [(process_statement) (concurrent_procedure_call) (concurrent_signal_assignment) (component_instantiation) (generate_statement)]* @arch.stmt_items) @arch.stmts) @arch.body)
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "entity_architecture",
            "is_entity": "entity.decl" in node["captures"],
            "is_architecture": "arch.body" in node["captures"],
            "entity_name": node["captures"].get("entity.name", {}).get("text", ""),
            "arch_name": node["captures"].get("arch.name", {}).get("text", ""),
            "arch_entity": node["captures"].get("arch.entity", {}).get("text", ""),
            "port_names": [p.get("text", "") for p in node["captures"].get("entity.port.name", [])],
            "port_modes": [m.get("text", "") for m in node["captures"].get("entity.port.mode", [])],
            "port_types": [t.get("text", "") for t in node["captures"].get("entity.port.type", [])],
            "has_ports": "entity.port" in node["captures"] and len([p for p in node["captures"].get("entity.port.name", [])]) > 0,
            "structure_type": (
                "entity" if "entity.decl" in node["captures"] else
                "architecture" if "arch.body" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "processes_signals": {
        "pattern": """
        [
            (process_statement
                label: (identifier)? @process.label
                sensitivity_list: (sensitivity_list
                    (identifier)* @process.sensitivity) @process.sens_list
                declarative_part: (process_declarative_part
                    [(variable_declaration) (constant_declaration) (subtype_declaration)]* @process.decls) @process.decl_part
                statement_part: (sequence_of_statements
                    [(signal_assignment_statement) (variable_assignment_statement) (if_statement) (case_statement) (loop_statement)]* @process.stmts) @process.stmt_part) @process,
                
            (signal_declaration
                identifier_list: (identifier_list
                    (identifier)+ @signal.name) @signal.names
                type: (_) @signal.type) @signal.decl,
                
            (signal_assignment_statement
                target: (name 
                    (identifier) @signal.assign.target) @signal.assign.name
                waveform: [(waveform
                              [(waveform_element) (unaffected)] @signal.assign.wave)
                          (conditional_waveforms) (selected_waveforms)] @signal.assign.value) @signal.assign,
                
            (variable_assignment_statement
                target: (name
                    (identifier) @variable.assign.target) @variable.assign.name
                expression: (_) @variable.assign.value) @variable.assign
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "processes_signals",
            "is_process": "process" in node["captures"],
            "is_signal_decl": "signal.decl" in node["captures"],
            "is_signal_assign": "signal.assign" in node["captures"],
            "is_variable_assign": "variable.assign" in node["captures"],
            "process_label": node["captures"].get("process.label", {}).get("text", ""),
            "sensitivity_signals": [s.get("text", "") for s in node["captures"].get("process.sensitivity", [])],
            "signal_names": [s.get("text", "") for s in node["captures"].get("signal.name", [])],
            "signal_type": node["captures"].get("signal.type", {}).get("text", ""),
            "assignment_target": node["captures"].get("signal.assign.target", {}).get("text", "") or node["captures"].get("variable.assign.target", {}).get("text", ""),
            "is_clocked_process": "process.sensitivity" in node["captures"] and any("clk" in s.get("text", "").lower() or "clock" in s.get("text", "").lower() for s in node["captures"].get("process.sensitivity", [])),
            "process_signal_type": (
                "process" if "process" in node["captures"] else
                "signal_declaration" if "signal.decl" in node["captures"] else
                "signal_assignment" if "signal.assign" in node["captures"] else
                "variable_assignment" if "variable.assign" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "components_instantiation": {
        "pattern": """
        [
            (component_declaration
                name: (identifier) @component.name
                port_clause: (port_clause
                    (interface_list
                        (interface_element
                            name: (identifier) @component.port.name
                            mode: [(in) (out) (inout) (buffer) (linkage)] @component.port.mode
                            type: (_) @component.port.type)+ @component.port.list) @component.port.elements) @component.port) @component.decl,
                
            (component_instantiation
                label: (identifier) @instance.label
                name: (name
                    (identifier) @instance.component) @instance.name
                port_map: (port_map
                    (association_list
                        (association_element
                            formal_part: [(identifier) (name)] @instance.port.formal
                            actual_part: (_) @instance.port.actual)+ @instance.port.assocs) @instance.port.list) @instance.port) @instance,
                
            (generate_statement
                label: (identifier) @gen.label
                [(for_generate_scheme
                    parameter: (identifier) @gen.for.param
                    range: (_) @gen.for.range) @gen.for
                 (if_generate_scheme
                    condition: (_) @gen.if.cond) @gen.if]
                (generate_statement_body
                    (concurrent_statement)+ @gen.body.stmts) @gen.body) @gen
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "components_instantiation",
            "is_component_decl": "component.decl" in node["captures"],
            "is_component_inst": "instance" in node["captures"],
            "is_generate": "gen" in node["captures"],
            "component_name": node["captures"].get("component.name", {}).get("text", ""),
            "instance_label": node["captures"].get("instance.label", {}).get("text", ""),
            "instance_component": node["captures"].get("instance.component", {}).get("text", ""),
            "port_names": [p.get("text", "") for p in node["captures"].get("component.port.name", [])],
            "formal_ports": [p.get("text", "") for p in node["captures"].get("instance.port.formal", [])],
            "generate_type": (
                "for_generate" if "gen.for" in node["captures"] else
                "if_generate" if "gen.if" in node["captures"] else
                "unknown" if "gen" in node["captures"] else
                None
            ),
            "component_type": (
                "component_declaration" if "component.decl" in node["captures"] else
                "component_instantiation" if "instance" in node["captures"] else
                "generate_statement" if "gen" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "packages_libraries": {
        "pattern": """
        [
            (design_unit
                (package_declaration
                    name: (identifier) @pkg.name
                    declarative_part: (package_declarative_part
                        [(type_declaration) (subtype_declaration) (constant_declaration) (function_declaration) (procedure_declaration) (component_declaration)]* @pkg.decls) @pkg.decl_part) @pkg.decl),
                
            (design_unit
                (package_body
                    name: (identifier) @pkg.body.name
                    declarative_part: (package_body_declarative_part
                        [(subprogram_body) (type_declaration) (subtype_declaration) (constant_declaration)]* @pkg.body.decls) @pkg.body.decl_part) @pkg.body),
                
            (library_clause
                (identifier)+ @lib.name) @lib,
                
            (use_clause
                selected_name: (selected_name
                    prefix: (name
                        (identifier) @use.prefix) @use.lib
                    suffix: (identifier) @use.suffix) @use.name) @use,
                
            (function_body
                name: (identifier) @func.name
                parameter_list: (interface_list
                    (interface_element
                        name: (identifier) @func.param.name
                        mode: [(in) (out) (inout)]? @func.param.mode
                        type: (_) @func.param.type)* @func.param.elements) @func.params
                return_type: (_) @func.return
                declarative_part: (subprogram_declarative_part)? @func.decls
                statement_part: (sequence_of_statements)? @func.stmts) @func
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "packages_libraries",
            "is_package_decl": "pkg.decl" in node["captures"],
            "is_package_body": "pkg.body" in node["captures"],
            "is_library_clause": "lib" in node["captures"],
            "is_use_clause": "use" in node["captures"],
            "is_function": "func" in node["captures"],
            "package_name": node["captures"].get("pkg.name", {}).get("text", "") or node["captures"].get("pkg.body.name", {}).get("text", ""),
            "library_names": [l.get("text", "") for l in node["captures"].get("lib.name", [])],
            "use_prefix": node["captures"].get("use.prefix", {}).get("text", ""),
            "use_suffix": node["captures"].get("use.suffix", {}).get("text", ""),
            "function_name": node["captures"].get("func.name", {}).get("text", ""),
            "function_params": [p.get("text", "") for p in node["captures"].get("func.param.name", [])],
            "package_type": (
                "package_declaration" if "pkg.decl" in node["captures"] else
                "package_body" if "pkg.body" in node["captures"] else
                "library_clause" if "lib" in node["captures"] else
                "use_clause" if "use" in node["captures"] else
                "function_body" if "func" in node["captures"] else
                "unknown"
            )
        }
    }
}

VHDL_PATTERNS = {
    **COMMON_PATTERNS,
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "entity": QueryPattern(
                pattern="""
                (design_unit
                    (entity_declaration
                        name: (identifier) @syntax.entity.name
                        generic_clause: (generic_clause)? @syntax.entity.generics
                        port_clause: (port_clause
                            (interface_list
                                (interface_element
                                    name: (identifier) @syntax.entity.port.name
                                    mode: [(in) (out) (inout) (buffer) (linkage)] @syntax.entity.port.mode
                                    type: (_) @syntax.entity.port.type)+) @syntax.entity.ports)) @syntax.entity
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.entity.name", {}).get("text", ""),
                    "ports": [p.get("text", "") for p in node["captures"].get("syntax.entity.port.name", [])]
                }
            ),
            
            "architecture": QueryPattern(
                pattern="""
                (design_unit
                    (architecture_body
                        name: (identifier) @syntax.architecture.name
                        entity: (identifier) @syntax.architecture.entity
                        declarative_part: (architecture_declarative_part)? @syntax.architecture.declarations
                        statement_part: (concurrent_statement_part)? @syntax.architecture.statements)) @syntax.architecture
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.architecture.name", {}).get("text", ""),
                    "entity": node["captures"].get("syntax.architecture.entity", {}).get("text", "")
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "signal": QueryPattern(
                pattern="""
                [
                    (signal_declaration
                        identifier_list: (identifier_list
                            (identifier)+ @semantics.signal.name) @semantics.signal.names
                        type: (_) @semantics.signal.type) @semantics.signal.declaration,
                    
                    (signal_assignment_statement
                        target: (name) @semantics.signal.assignment.target
                        waveform: (_) @semantics.signal.assignment.value) @semantics.signal.assignment
                ]
                """,
                extract=lambda node: {
                    "name": [n.get("text", "") for n in node["captures"].get("semantics.signal.name", [])],
                    "type": node["captures"].get("semantics.signal.type", {}).get("text", ""),
                    "kind": "declaration" if "semantics.signal.declaration" in node["captures"] else
                           "assignment" if "semantics.signal.assignment" in node["captures"] else
                           "unknown"
                }
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "process": QueryPattern(
                pattern="""
                (process_statement
                    label: (identifier)? @structure.process.label
                    sensitivity_list: (sensitivity_list
                        (identifier)* @structure.process.sensitivity) @structure.process.sensitivity_list
                    declarative_part: (process_declarative_part)? @structure.process.declarations
                    statement_part: (sequence_of_statements)? @structure.process.statements) @structure.process
                """,
                extract=lambda node: {
                    "label": node["captures"].get("structure.process.label", {}).get("text", ""),
                    "sensitivity": [s.get("text", "") for s in node["captures"].get("structure.process.sensitivity", [])]
                }
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", "")
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.HARDWARE: {
            "entity_architecture": QueryPattern(
                pattern="""
                [
                    (design_unit
                        (entity_declaration
                            name: (identifier) @entity.name
                            port_clause: (port_clause
                                (interface_list
                                    (interface_element
                                        name: (identifier) @entity.port.name
                                        mode: [(in) (out) (inout) (buffer) (linkage)] @entity.port.mode
                                        type: (_) @entity.port.type)+ @entity.port.list) @entity.port.elements) @entity.port) @entity.decl),
                            
                    (design_unit
                        (architecture_body
                            name: (identifier) @arch.name
                            entity: (identifier) @arch.entity
                            declarative_part: (architecture_declarative_part
                                [(signal_declaration) (constant_declaration) (component_declaration) (subtype_declaration) (function_body) (procedure_body)]* @arch.decl_items) @arch.decl
                            statement_part: (concurrent_statement_part
                                [(process_statement) (concurrent_procedure_call) (concurrent_signal_assignment) (component_instantiation) (generate_statement)]* @arch.stmt_items) @arch.stmts) @arch.body)
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "entity_architecture",
                    "is_entity": "entity.decl" in node["captures"],
                    "is_architecture": "arch.body" in node["captures"],
                    "entity_name": node["captures"].get("entity.name", {}).get("text", ""),
                    "arch_name": node["captures"].get("arch.name", {}).get("text", ""),
                    "arch_entity": node["captures"].get("arch.entity", {}).get("text", ""),
                    "port_names": [p.get("text", "") for p in node["captures"].get("entity.port.name", [])],
                    "port_modes": [m.get("text", "") for m in node["captures"].get("entity.port.mode", [])],
                    "port_types": [t.get("text", "") for t in node["captures"].get("entity.port.type", [])],
                    "has_ports": "entity.port" in node["captures"] and len([p for p in node["captures"].get("entity.port.name", [])]) > 0,
                    "structure_type": (
                        "entity" if "entity.decl" in node["captures"] else
                        "architecture" if "arch.body" in node["captures"] else
                        "unknown"
                    )
                }
            )
        }
    },
    
    "REPOSITORY_LEARNING": VHDL_PATTERNS_FOR_LEARNING
} 