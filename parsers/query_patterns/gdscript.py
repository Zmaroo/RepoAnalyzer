"""Query patterns for GDScript files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

GDSCRIPT_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_definition
                        name: (_) @syntax.function.name
                        parameters: (_)? @syntax.function.params
                        return_type: (_)? @syntax.function.return) @syntax.function.def,
                    (method_definition
                        name: (_) @syntax.function.name
                        parameters: (_)? @syntax.function.params
                        return_type: (_)? @syntax.function.return) @syntax.function.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function"
                }
            ),
            "class": QueryPattern(
                pattern="""
                [
                    (class_definition
                        name: (_) @syntax.class.name
                        extends: (_)? @syntax.class.extends) @syntax.class.def,
                    (inner_class_definition
                        name: (_) @syntax.class.name
                        extends: (_)? @syntax.class.extends) @syntax.class.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                    "type": "class",
                    "extends": node["captures"].get("syntax.class.extends", {}).get("text", "")
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (variable_declaration
                        name: (_) @semantics.variable.name
                        type: (_)? @semantics.variable.type
                        value: (_)? @semantics.variable.value) @semantics.variable.def,
                    (export_variable
                        name: (_) @semantics.variable.name
                        type: (_)? @semantics.variable.type
                        value: (_)? @semantics.variable.value) @semantics.variable.export
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                    "type": "variable",
                    "is_export": "semantics.variable.export" in node["captures"]
                }
            ),
            "signal": QueryPattern(
                pattern="""
                [
                    (signal_declaration
                        name: (_) @semantics.signal.name
                        parameters: (_)? @semantics.signal.params) @semantics.signal.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.signal.name", {}).get("text", ""),
                    "type": "signal"
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
            "scene_tree": QueryPattern(
                pattern="""
                [
                    (node_path
                        path: (_) @structure.node.path) @structure.node.ref,
                    (get_node
                        path: (_) @structure.node.path) @structure.node.get
                ]
                """,
                extract=lambda node: {
                    "path": node["captures"].get("structure.node.path", {}).get("text", ""),
                    "type": "node_reference"
                }
            ),
            "resource": QueryPattern(
                pattern="""
                [
                    (preload
                        path: (_) @structure.resource.path) @structure.resource.preload,
                    (load
                        path: (_) @structure.resource.path) @structure.resource.load
                ]
                """,
                extract=lambda node: {
                    "path": node["captures"].get("structure.resource.path", {}).get("text", ""),
                    "type": "resource",
                    "is_preload": "structure.resource.preload" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "godot_patterns": QueryPattern(
                pattern="""
                [
                    (function_definition
                        name: (_) @godot.lifecycle.name
                        (#match? @godot.lifecycle.name "^_")) @godot.lifecycle.def,
                    (signal_declaration
                        name: (_) @godot.signal.name) @godot.signal.def,
                    (export_variable
                        name: (_) @godot.export.name
                        type: (_)? @godot.export.type) @godot.export.def,
                    (get_node
                        path: (_) @godot.node.path) @godot.node.get
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "lifecycle_method" if "godot.lifecycle.def" in node["captures"] else
                        "signal_definition" if "godot.signal.def" in node["captures"] else
                        "export_property" if "godot.export.def" in node["captures"] else
                        "node_access" if "godot.node.get" in node["captures"] else
                        "other"
                    ),
                    "uses_lifecycle": "godot.lifecycle.def" in node["captures"],
                    "uses_signals": "godot.signal.def" in node["captures"],
                    "uses_exports": "godot.export.def" in node["captures"],
                    "uses_node_access": "godot.node.get" in node["captures"]
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "scene_structure": QueryPattern(
                pattern="""
                [
                    (class_definition
                        name: (_) @scene.class.name
                        extends: (_) @scene.class.extends) @scene.class.def,
                    (signal_declaration
                        name: (_) @scene.signal.name) @scene.signal.def,
                    (function_definition
                        name: (_) @scene.function.name
                        (#match? @scene.function.name "^_ready|^_process|^_physics_process|^_input")) @scene.function.def
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "scene_class" if "scene.class.def" in node["captures"] else
                        "signal" if "scene.signal.def" in node["captures"] else
                        "lifecycle_function" if "scene.function.def" in node["captures"] else
                        "other"
                    ),
                    "extends_node": any(
                        node_type in (node["captures"].get("scene.class.extends", {}).get("text", "") or "")
                        for node_type in ["Node", "Node2D", "Spatial", "Control"]
                    ),
                    "has_signals": "scene.signal.def" in node["captures"],
                    "has_lifecycle": "scene.function.def" in node["captures"]
                }
            )
        },
        PatternPurpose.ERROR_HANDLING: {
            "resource_management": QueryPattern(
                pattern="""
                [
                    (preload
                        path: (_) @resource.preload.path) @resource.preload,
                    (load
                        path: (_) @resource.load.path) @resource.load,
                    (get_node
                        path: (_) @resource.node.path) @resource.node.get
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "preload" if "resource.preload" in node["captures"] else
                        "load" if "resource.load" in node["captures"] else
                        "get_node" if "resource.node.get" in node["captures"] else
                        "other"
                    ),
                    "uses_preload": "resource.preload" in node["captures"],
                    "uses_load": "resource.load" in node["captures"],
                    "uses_get_node": "resource.node.get" in node["captures"]
                }
            )
        }
    }
} 