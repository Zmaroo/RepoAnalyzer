"""
Query patterns for Verilog files.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

VERILOG_PATTERNS_FOR_LEARNING = {
    "module_patterns": {
        "pattern": """
        [
            (module_declaration
                name: (simple_identifier) @module.name
                ports: (port_declaration_list
                    (port_declaration
                        direction: [(input_declaration) (output_declaration) (inout_declaration)] @module.port.direction
                        name: (list_of_port_identifiers
                            (port_identifier) @module.port.name)) @module.port)*
                items: (module_item
                    [(always_construct) (continuous_assign) (initial_construct) (function_declaration)]*) @module.item) @module.decl,
                
            (module_instantiation
                module: (simple_identifier) @module.inst.type
                name: (instance_identifier) @module.inst.name
                connections: (list_of_port_connections
                    [(named_port_connection
                        name: (port_identifier) @module.inst.port.name
                        expression: (_) @module.inst.port.value)
                     (ordered_port_connection
                        expression: (_) @module.inst.port.expr)]* @module.inst.port.connections) @module.inst.ports) @module.inst,
                
            (parameter_declaration
                [(parameter_identifier) 
                 (list_of_param_assignments
                    (param_assignment
                        name: (parameter_identifier) @module.param.name
                        value: (_) @module.param.value))] @module.param.items) @module.param,
                
            (port_declaration
                (list_of_port_identifiers
                    (port_identifier) @module.port.decl.name)* @module.port.decl.names
                [(net_type) (reg_declaration)]? @module.port.decl.type) @module.port.decl
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "module_patterns",
            "is_module_decl": "module.decl" in node["captures"],
            "is_module_inst": "module.inst" in node["captures"],
            "is_param_decl": "module.param" in node["captures"],
            "is_port_decl": "module.port.decl" in node["captures"],
            "module_name": node["captures"].get("module.name", {}).get("text", ""),
            "instance_name": node["captures"].get("module.inst.name", {}).get("text", ""),
            "instance_type": node["captures"].get("module.inst.type", {}).get("text", ""),
            "param_names": [p.get("text", "") for p in node["captures"].get("module.param.name", [])],
            "port_names": [p.get("text", "") for p in node["captures"].get("module.port.name", []) + node["captures"].get("module.port.decl.name", [])],
            "module_pattern_type": (
                "module_declaration" if "module.decl" in node["captures"] else
                "module_instantiation" if "module.inst" in node["captures"] else
                "parameter_declaration" if "module.param" in node["captures"] else
                "port_declaration" if "module.port.decl" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "sequential_logic": {
        "pattern": """
        [
            (always_construct
                (event_control
                    (event_expression
                        (edge_identifier) @seq.always.edge {
                            match: "^(posedge|negedge)$"
                        }
                        (expression) @seq.always.signal) @seq.always.event) @seq.always.control
                (statement
                    [(seq_block) (conditional_statement) (case_statement) (procedural_continuous_assignment)]+ @seq.always.body) @seq.always.stmt) @seq.always,
                
            (always_construct
                (statement
                    [(seq_block) (conditional_statement) (case_statement) (procedural_continuous_assignment)]+ @seq.comb.body) @seq.comb.stmt) @seq.comb {
                filter: { @seq.always.edge is null }
            },
                
            (initial_construct
                (statement) @seq.initial.stmt) @seq.initial,
                
            (blocking_assignment
                left: (_) @seq.blocking.left
                right: (_) @seq.blocking.right) @seq.blocking,
                
            (nonblocking_assignment
                left: (_) @seq.nonblocking.left
                right: (_) @seq.nonblocking.right) @seq.nonblocking
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "sequential_logic",
            "is_sequential_always": "seq.always" in node["captures"] and node["captures"].get("seq.always.edge", {}).get("text", "") in ["posedge", "negedge"],
            "is_combinational_always": "seq.comb" in node["captures"],
            "is_initial": "seq.initial" in node["captures"],
            "is_blocking_assignment": "seq.blocking" in node["captures"],
            "is_nonblocking_assignment": "seq.nonblocking" in node["captures"],
            "clock_signal": node["captures"].get("seq.always.signal", {}).get("text", ""),
            "clock_edge": node["captures"].get("seq.always.edge", {}).get("text", ""),
            "assignment_target": node["captures"].get("seq.blocking.left", {}).get("text", "") or node["captures"].get("seq.nonblocking.left", {}).get("text", ""),
            "sequential_type": (
                "sequential_always" if "seq.always" in node["captures"] and node["captures"].get("seq.always.edge", {}).get("text", "") in ["posedge", "negedge"] else
                "combinational_always" if "seq.comb" in node["captures"] else
                "initial" if "seq.initial" in node["captures"] else
                "blocking_assignment" if "seq.blocking" in node["captures"] else
                "nonblocking_assignment" if "seq.nonblocking" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "datapath_elements": {
        "pattern": """
        [
            (reg_declaration
                [(list_of_variable_identifiers
                    (variable_identifier) @datapath.reg.name)
                 (variable_identifier) @datapath.reg.single_name]
                [(range)
                 (data_type_or_implicit)]? @datapath.reg.type) @datapath.reg,
                
            (net_declaration
                [(list_of_net_identifiers
                    (net_identifier) @datapath.net.name)
                 (net_identifier) @datapath.net.single_name]
                [(range)
                 (data_type_or_implicit)]? @datapath.net.type) @datapath.net,
                
            (continuous_assignment
                (list_of_net_assignments
                    (net_assignment
                        left: (_) @datapath.assign.left
                        right: (_) @datapath.assign.right)) @datapath.assign.list) @datapath.assign,
                
            (module_instantiation
                module: (simple_identifier) @datapath.mem.type {
                    match: "^(.*mem.*|.*RAM|.*ROM)$"
                }
                name: (instance_identifier) @datapath.mem.name
                connections: (list_of_port_connections) @datapath.mem.ports) @datapath.mem.instance,
                
            (function_declaration
                name: (function_identifier) @datapath.func.name
                [(port_identifier) (function_port_list)]? @datapath.func.ports
                (function_item_declaration)* @datapath.func.decls
                (statement) @datapath.func.body) @datapath.func
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "datapath_elements",
            "is_reg": "datapath.reg" in node["captures"],
            "is_net": "datapath.net" in node["captures"],
            "is_continuous_assign": "datapath.assign" in node["captures"],
            "is_memory": "datapath.mem.instance" in node["captures"],
            "is_function": "datapath.func" in node["captures"],
            "element_name": (
                node["captures"].get("datapath.reg.name", {}).get("text", "") or node["captures"].get("datapath.reg.single_name", {}).get("text", "") or
                node["captures"].get("datapath.net.name", {}).get("text", "") or node["captures"].get("datapath.net.single_name", {}).get("text", "") or
                node["captures"].get("datapath.mem.name", {}).get("text", "") or
                node["captures"].get("datapath.func.name", {}).get("text", "")
            ),
            "data_type": (
                node["captures"].get("datapath.reg.type", {}).get("text", "") or
                node["captures"].get("datapath.net.type", {}).get("text", "")
            ),
            "assignment_target": node["captures"].get("datapath.assign.left", {}).get("text", ""),
            "memory_type": node["captures"].get("datapath.mem.type", {}).get("text", ""),
            "datapath_type": (
                "register" if "datapath.reg" in node["captures"] else
                "net" if "datapath.net" in node["captures"] else
                "continuous_assignment" if "datapath.assign" in node["captures"] else
                "memory" if "datapath.mem.instance" in node["captures"] else
                "function" if "datapath.func" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "control_constructs": {
        "pattern": """
        [
            (conditional_statement
                condition: (_) @control.if.cond
                true_statement: (_) @control.if.then
                false_statement: (_)? @control.if.else) @control.if,
                
            (case_statement
                expression: (_) @control.case.expr
                (case_item
                    expression: (_)? @control.case.item.expr
                    statement: (_) @control.case.item.stmt)+ @control.case.items) @control.case,
                
            (loop_statement
                [(for_initialization
                    expression: (_) @control.loop.init)
                 (for_condition
                    expression: (_) @control.loop.cond)
                 (for_step
                    expression: (_) @control.loop.step)]
                statement: (_) @control.loop.body) @control.loop,
                
            (generate_for_statement
                initialization: (_) @control.gen_for.init
                condition: (_) @control.gen_for.cond
                update: (_) @control.gen_for.update
                statement: (_) @control.gen_for.body) @control.gen_for,
                
            (generate_if_statement
                condition: (_) @control.gen_if.cond
                true_statement: (_) @control.gen_if.then
                false_statement: (_)? @control.gen_if.else) @control.gen_if
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "control_constructs",
            "is_if": "control.if" in node["captures"],
            "is_case": "control.case" in node["captures"],
            "is_loop": "control.loop" in node["captures"],
            "is_generate_for": "control.gen_for" in node["captures"],
            "is_generate_if": "control.gen_if" in node["captures"],
            "condition": (
                node["captures"].get("control.if.cond", {}).get("text", "") or
                node["captures"].get("control.loop.cond", {}).get("text", "") or
                node["captures"].get("control.gen_for.cond", {}).get("text", "") or
                node["captures"].get("control.gen_if.cond", {}).get("text", "")
            ),
            "case_expression": node["captures"].get("control.case.expr", {}).get("text", ""),
            "has_else": (
                ("control.if" in node["captures"] and "control.if.else" in node["captures"] and node["captures"].get("control.if.else", {}).get("text", "") != "") or
                ("control.gen_if" in node["captures"] and "control.gen_if.else" in node["captures"] and node["captures"].get("control.gen_if.else", {}).get("text", "") != "")
            ),
            "case_items_count": len([item for item in node["captures"].get("control.case.items", [])]) if "control.case.items" in node["captures"] else 0,
            "control_type": (
                "if_statement" if "control.if" in node["captures"] else
                "case_statement" if "control.case" in node["captures"] else
                "loop_statement" if "control.loop" in node["captures"] else
                "generate_for" if "control.gen_for" in node["captures"] else
                "generate_if" if "control.gen_if" in node["captures"] else
                "unknown"
            )
        }
    }
}

VERILOG_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "module": {
            "pattern": """
            (module_declaration
                name: (simple_identifier) @syntax.module.name
                ports: (port_declaration_list)? @syntax.module.ports
                items: (module_item)* @syntax.module.items) @syntax.module
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.module.name", {}).get("text", ""),
                "has_ports": "syntax.module.ports" in node["captures"] and node["captures"].get("syntax.module.ports", {}).get("text", "") != ""
            }
        },
        
        "always": {
            "pattern": """
            (always_construct
                (event_control)? @syntax.always.event
                (statement) @syntax.always.statement) @syntax.always
            """,
            "extract": lambda node: {
                "has_event": "syntax.always.event" in node["captures"] and node["captures"].get("syntax.always.event", {}).get("text", "") != "",
                "event_type": (
                    "edge_triggered" if "syntax.always.event" in node["captures"] and "posedge" in node["captures"].get("syntax.always.event", {}).get("text", "") else
                    "level_sensitive" if "syntax.always.event" in node["captures"] else
                    "combinational"
                )
            }
        }
    },
    
    "semantics": {
        "signal": {
            "pattern": """
            [
                (net_declaration
                    (list_of_net_identifiers
                        (net_identifier) @semantics.signal.net.name)+ @semantics.signal.net.names) @semantics.signal.net,
                
                (reg_declaration
                    (list_of_variable_identifiers
                        (variable_identifier) @semantics.signal.reg.name)+ @semantics.signal.reg.names) @semantics.signal.reg
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.signal.net.name", {}).get("text", "") or
                       node["captures"].get("semantics.signal.reg.name", {}).get("text", ""),
                "type": "net" if "semantics.signal.net" in node["captures"] else "reg"
            }
        }
    },
    
    "structure": {
        "instance": {
            "pattern": """
            (module_instantiation
                module: (simple_identifier) @structure.instance.module
                name: (instance_identifier) @structure.instance.name
                connections: (list_of_port_connections
                    [(named_port_connection
                       name: (port_identifier) @structure.instance.port.name
                       expression: (_) @structure.instance.port.expr)
                     (ordered_port_connection
                       expression: (_) @structure.instance.port.ordered)]*) @structure.instance.ports) @structure.instance
            """,
            "extract": lambda node: {
                "module": node["captures"].get("structure.instance.module", {}).get("text", ""),
                "name": node["captures"].get("structure.instance.name", {}).get("text", ""),
                "ports": [p.get("text", "") for p in node["captures"].get("structure.instance.port.name", [])]
            }
        }
    },
    
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "")
            }
        }
    },
    
    "REPOSITORY_LEARNING": VERILOG_PATTERNS_FOR_LEARNING
} 