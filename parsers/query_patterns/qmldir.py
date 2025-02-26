"""Query patterns for QML directory files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

QMLDIR_PATTERNS_FOR_LEARNING = {
    "module_patterns": {
        "pattern": """
        (module_definition
            commands: (command)* @module.commands) @module.def
        """,
        "extract": lambda node: {
            "pattern_type": "module_patterns",
            "is_module_definition": "module.def" in node["captures"],
            "command_count": len(node["captures"].get("module.commands", [])),
            "module_structure": "qmldir_module"
        }
    },
    
    "component_registration": {
        "pattern": """
        [
            (command
                name: (identifier) @comp.name
                type: (classname) @comp.type
                version: (number)? @comp.version) @comp.def,
                
            (command
                keyword: "singleton" @comp.singleton
                name: (identifier) @comp.singleton.name
                type: (classname) @comp.singleton.type) @comp.singleton.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "component_registration",
            "is_component": "comp.def" in node["captures"],
            "is_singleton": "comp.singleton.def" in node["captures"],
            "component_name": node["captures"].get("comp.name", {}).get("text", "") or node["captures"].get("comp.singleton.name", {}).get("text", ""),
            "component_type": node["captures"].get("comp.type", {}).get("text", "") or node["captures"].get("comp.singleton.type", {}).get("text", ""),
            "has_version": "comp.version" in node["captures"],
            "component_version": node["captures"].get("comp.version", {}).get("text", "")
        }
    },
    
    "dependency_management": {
        "pattern": """
        [
            (command
                keyword: "depends" @dep.type
                value: (_) @dep.value) @dep.def,
                
            (command
                keyword: "plugin" @plugin.type
                value: (_) @plugin.value) @plugin.def,
                
            (command
                keyword: "import" @import.type
                value: (_) @import.value) @import.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "dependency_management",
            "is_dependency": "dep.def" in node["captures"],
            "is_plugin": "plugin.def" in node["captures"],
            "is_import": "import.def" in node["captures"],
            "dependency_value": node["captures"].get("dep.value", {}).get("text", ""),
            "plugin_value": node["captures"].get("plugin.value", {}).get("text", ""),
            "import_value": node["captures"].get("import.value", {}).get("text", ""),
            "dependency_type": (
                "module_dependency" if "dep.def" in node["captures"] else
                "plugin_dependency" if "plugin.def" in node["captures"] else
                "import_dependency" if "import.def" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "file_organization": {
        "pattern": """
        [
            (command
                keyword: "designersupported" @design.key) @design.def,
                
            (command
                keyword: "typeinfo" @typeinfo.key
                value: (_) @typeinfo.value) @typeinfo.def,
                
            (command
                keyword: "classname" @classname.key
                value: (_) @classname.value) @classname.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "file_organization",
            "supports_designer": "design.def" in node["captures"],
            "has_typeinfo": "typeinfo.def" in node["captures"],
            "has_classname": "classname.def" in node["captures"],
            "typeinfo_path": node["captures"].get("typeinfo.value", {}).get("text", ""),
            "classname_value": node["captures"].get("classname.value", {}).get("text", "")
        }
    }
}

QMLDIR_PATTERNS = {
    "syntax": {
        "module": {
            "pattern": """
            (module_definition
                commands: (command)* @syntax.module.command) @syntax.module.def
            """
        },
        "command": {
            "pattern": """
            [
                (command
                    name: (identifier) @syntax.command.name
                    type: (classname) @syntax.command.type
                    version: (number)? @syntax.command.version) @syntax.command.def,
                
                (command
                    keyword: (keyword) @syntax.command.keyword
                    value: (_) @syntax.command.value) @syntax.command.property
            ]
            """
        }
    },
    "structure": {
        "dependency": {
            "pattern": """
            [
                (command
                    keyword: "depends" @structure.dependency.type
                    value: (_) @structure.dependency.value) @structure.dependency.def,
                
                (command
                    keyword: "plugin" @structure.dependency.type
                    value: (_) @structure.dependency.value) @structure.dependency.def
            ]
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    },
    
    "REPOSITORY_LEARNING": QMLDIR_PATTERNS_FOR_LEARNING
} 