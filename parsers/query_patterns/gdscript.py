"""Query patterns for GDScript files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

GDSCRIPT_PATTERNS_FOR_LEARNING = {
    "game_development_patterns": {
        "pattern": """
        [
            (class_definition
                name: (_) @game.class.name
                extends: (_)? @game.class.extends
                body: (_) @game.class.body) @game.class,
                
            (function_definition
                name: (_) @game.func.name
                parameters: (_)? @game.func.params
                body: (_) @game.func.body) @game.func,
                
            (call
                function: (_) @game.call.name
                arguments: (_)? @game.call.args) @game.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": (
                "class_definition" if "game.class" in node["captures"] else
                "function_definition" if "game.func" in node["captures"] else
                "function_call" if "game.call" in node["captures"] else
                "other"
            ),
            "extends_node": any(
                node_type in (node["captures"].get("game.class.extends", {}).get("text", "") or "")
                for node_type in ["Node", "Node2D", "Spatial", "Control", "CanvasItem", "Area2D", "RigidBody2D", "KinematicBody2D"]
            ),
            "uses_lifecycle_method": any(
                lifecycle in (node["captures"].get("game.func.name", {}).get("text", "") or "")
                for lifecycle in ["_ready", "_process", "_physics_process", "_input", "_unhandled_input", "_draw"]
            ),
            "uses_engine_call": any(
                engine_func in (node["captures"].get("game.call.name", {}).get("text", "") or "")
                for engine_func in ["get_node", "instance", "queue_free", "emit_signal", "connect"]
            ),
            "class_name": node["captures"].get("game.class.name", {}).get("text", ""),
            "function_name": node["captures"].get("game.func.name", {}).get("text", "")
        }
    },
    
    "node_interactions": {
        "pattern": """
        [
            (call
                function: (_) @node.call.name
                (#match? @node.call.name "get_node")
                arguments: (_) @node.call.path) @node.get,
                
            (assignment
                left: (_) @node.var.name
                right: (call
                    function: (_) @node.var.get
                    (#match? @node.var.get "get_node")
                    arguments: (_) @node.var.path)) @node.var.assign,
                    
            (call
                function: (attribute
                    value: (_) @node.ref.var
                    attribute: (_) @node.ref.method) 
                arguments: (_)? @node.ref.args) @node.ref.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": (
                "get_node" if "node.get" in node["captures"] else
                "node_variable_assignment" if "node.var.assign" in node["captures"] else
                "node_method_call" if "node.ref.call" in node["captures"] else
                "other"
            ),
            "uses_direct_path": "$" in (node["captures"].get("node.call.path", {}).get("text", "") or ""),
            "uses_variable_reference": "node.ref.var" in node["captures"],
            "method_name": node["captures"].get("node.ref.method", {}).get("text", ""),
            "node_path": (
                node["captures"].get("node.call.path", {}).get("text", "") or
                node["captures"].get("node.var.path", {}).get("text", "") or
                ""
            ).strip('"\'')
        }
    },
    
    "signal_handling": {
        "pattern": """
        [
            (expression_statement
                (call
                    function: (_) @signal.def.name
                    (#eq? @signal.def.name "signal")
                    arguments: (_) @signal.def.args)) @signal.def,
                    
            (expression_statement
                (call
                    function: (_) @signal.emit.func
                    (#eq? @signal.emit.func "emit_signal")
                    arguments: (_) @signal.emit.args)) @signal.emit,
                    
            (expression_statement
                (call
                    function: (_) @signal.connect.func
                    (#eq? @signal.connect.func "connect")
                    arguments: (_) @signal.connect.args)) @signal.connect
        ]
        """,
        "extract": lambda node: {
            "pattern_type": (
                "signal_definition" if "signal.def" in node["captures"] else
                "signal_emission" if "signal.emit" in node["captures"] else
                "signal_connection" if "signal.connect" in node["captures"] else
                "other"
            ),
            "signal_name": (
                node["captures"].get("signal.def.args", {}).get("text", "").strip('()"\' ') if "signal.def" in node["captures"] else
                node["captures"].get("signal.emit.args", {}).get("text", "").split(",")[0].strip('"\' ') if "signal.emit" in node["captures"] else
                node["captures"].get("signal.connect.args", {}).get("text", "").split(",")[0].strip('"\' ') if "signal.connect" in node["captures"] else
                ""
            ),
            "uses_signal_definition": "signal.def" in node["captures"],
            "uses_signal_emission": "signal.emit" in node["captures"],
            "uses_signal_connection": "signal.connect" in node["captures"]
        }
    },
    
    "resource_management": {
        "pattern": """
        [
            (call
                function: (_) @res.func.name
                (#match? @res.func.name "load|preload|ResourceLoader\\.load")
                arguments: (_) @res.func.path) @res.load,
                
            (assignment
                left: (_) @res.var.name
                right: (call
                    function: (_) @res.var.load
                    (#match? @res.var.load "load|preload|ResourceLoader\\.load")
                    arguments: (_) @res.var.path)) @res.var.assign,
                    
            (call
                function: (_) @res.inst.name
                (#eq? @res.inst.name "instance")
                arguments: (_)? @res.inst.args) @res.instance
        ]
        """,
        "extract": lambda node: {
            "pattern_type": (
                "resource_load" if "res.load" in node["captures"] else
                "resource_assignment" if "res.var.assign" in node["captures"] else
                "resource_instantiation" if "res.instance" in node["captures"] else
                "other"
            ),
            "uses_preload": (
                "preload" in (node["captures"].get("res.func.name", {}).get("text", "") or "") or
                "preload" in (node["captures"].get("res.var.load", {}).get("text", "") or "")
            ),
            "resource_path": (
                node["captures"].get("res.func.path", {}).get("text", "") or
                node["captures"].get("res.var.path", {}).get("text", "") or
                ""
            ).strip('"\''),
            "resource_variable": node["captures"].get("res.var.name", {}).get("text", ""),
            "resource_type": (
                "scene" if ".tscn" in ((node["captures"].get("res.func.path", {}).get("text", "") or
                                      node["captures"].get("res.var.path", {}).get("text", "") or "")) else
                "texture" if ".png" in ((node["captures"].get("res.func.path", {}).get("text", "") or
                                      node["captures"].get("res.var.path", {}).get("text", "") or "")) else
                "audio" if any(ext in ((node["captures"].get("res.func.path", {}).get("text", "") or
                                      node["captures"].get("res.var.path", {}).get("text", "") or ""))
                             for ext in [".wav", ".ogg", ".mp3"]) else
                "script" if ".gd" in ((node["captures"].get("res.func.path", {}).get("text", "") or
                                     node["captures"].get("res.var.path", {}).get("text", "") or "")) else
                "other"
            )
        }
    }
}

GDSCRIPT_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (function_definition
                name: (_) @syntax.function.name
                parameters: (_)? @syntax.function.params
                body: (_) @syntax.function.body) @syntax.function.def
            """
        },
        "class": {
            "pattern": """
            (class_definition
                name: (_) @syntax.class.name
                extends: (_)? @syntax.class.extends
                body: (_) @syntax.class.body) @syntax.class.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (assignment
                    left: (_) @semantics.variable.name
                    right: (_) @semantics.variable.value) @semantics.variable.def,
                (variable_declaration
                    name: (_) @semantics.variable.name
                    type: (_)? @semantics.variable.type
                    value: (_)? @semantics.variable.value) @semantics.variable.decl
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (call
                    function: (_) @semantics.expression.func
                    arguments: (_)? @semantics.expression.args) @semantics.expression.call,
                (binary_operator
                    left: (_) @semantics.expression.left
                    operator: (_) @semantics.expression.op
                    right: (_) @semantics.expression.right) @semantics.expression.binary
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (docstring) @documentation.docstring
            ]
            """
        }
    },

    "structure": {
        "export": {
            "pattern": """
            (export_variable
                type: (_)? @structure.export.type
                default_value: (_)? @structure.export.default
                name: (_) @structure.export.name) @structure.export.def
            """
        },
        "import": {
            "pattern": """
            (preload
                path: (_) @structure.import.path) @structure.import.preload
            """
        }
    },
    
    "REPOSITORY_LEARNING": GDSCRIPT_PATTERNS_FOR_LEARNING
} 