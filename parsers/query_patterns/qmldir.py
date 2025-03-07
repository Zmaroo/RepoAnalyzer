"""Query patterns for QML directory files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)

QMLDIR_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "module": QueryPattern(
                pattern="""
                (module_definition
                    commands: (command)* @syntax.module.command) @syntax.module.def
                """,
                extract=lambda node: {
                    "type": "module",
                    "has_commands": "syntax.module.command" in node["captures"]
                }
            ),
            "command": QueryPattern(
                pattern="""
                [
                    (command
                        name: (identifier) @syntax.command.name
                        type: (classname) @syntax.command.type
                        version: (number)? @syntax.command.version) @syntax.command.def,
                    (command
                        keyword: (keyword) @syntax.command.keyword
                        value: (_) @syntax.command.value) @syntax.command.property
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.command.name", {}).get("text", ""),
                    "type": (
                        "component" if "syntax.command.def" in node["captures"] else
                        "property" if "syntax.command.property" in node["captures"] else
                        "other"
                    ),
                    "has_version": "syntax.command.version" in node["captures"]
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                (comment) @documentation.comment
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "type": "comment"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.MODULE_PATTERNS: {
            "module_patterns": QueryPattern(
                pattern="""
                (module_definition
                    commands: (command)* @learning.module.commands) @learning.module.def
                """,
                extract=lambda node: {
                    "pattern_type": "module_patterns",
                    "is_module_definition": "learning.module.def" in node["captures"],
                    "command_count": len(node["captures"].get("learning.module.commands", [])),
                    "module_structure": "qmldir_module"
                }
            )
        },
        PatternPurpose.COMPONENT_REGISTRATION: {
            "component_registration": QueryPattern(
                pattern="""
                [
                    (command
                        name: (identifier) @learning.comp.name
                        type: (classname) @learning.comp.type
                        version: (number)? @learning.comp.version) @learning.comp.def,
                    (command
                        keyword: "singleton" @learning.comp.singleton
                        name: (identifier) @learning.comp.singleton.name
                        type: (classname) @learning.comp.singleton.type) @learning.comp.singleton.def
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "component_registration",
                    "is_component": "learning.comp.def" in node["captures"],
                    "is_singleton": "learning.comp.singleton.def" in node["captures"],
                    "component_name": node["captures"].get("learning.comp.name", {}).get("text", "") or node["captures"].get("learning.comp.singleton.name", {}).get("text", ""),
                    "component_type": node["captures"].get("learning.comp.type", {}).get("text", "") or node["captures"].get("learning.comp.singleton.type", {}).get("text", ""),
                    "has_version": "learning.comp.version" in node["captures"],
                    "component_version": node["captures"].get("learning.comp.version", {}).get("text", "")
                }
            )
        },
        PatternPurpose.DEPENDENCIES: {
            "dependency_management": QueryPattern(
                pattern="""
                [
                    (command
                        keyword: "depends" @learning.dep.type
                        value: (_) @learning.dep.value) @learning.dep.def,
                    (command
                        keyword: "plugin" @learning.plugin.type
                        value: (_) @learning.plugin.value) @learning.plugin.def,
                    (command
                        keyword: "import" @learning.import.type
                        value: (_) @learning.import.value) @learning.import.def
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "dependency_management",
                    "is_dependency": "learning.dep.def" in node["captures"],
                    "is_plugin": "learning.plugin.def" in node["captures"],
                    "is_import": "learning.import.def" in node["captures"],
                    "dependency_value": node["captures"].get("learning.dep.value", {}).get("text", ""),
                    "plugin_value": node["captures"].get("learning.plugin.value", {}).get("text", ""),
                    "import_value": node["captures"].get("learning.import.value", {}).get("text", ""),
                    "dependency_type": (
                        "module_dependency" if "learning.dep.def" in node["captures"] else
                        "plugin_dependency" if "learning.plugin.def" in node["captures"] else
                        "import_dependency" if "learning.import.def" in node["captures"] else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.FILE_ORGANIZATION: {
            "file_organization": QueryPattern(
                pattern="""
                [
                    (command
                        keyword: "designersupported" @learning.design.key) @learning.design.def,
                    (command
                        keyword: "typeinfo" @learning.typeinfo.key
                        value: (_) @learning.typeinfo.value) @learning.typeinfo.def,
                    (command
                        keyword: "classname" @learning.classname.key
                        value: (_) @learning.classname.value) @learning.classname.def
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "file_organization",
                    "supports_designer": "learning.design.def" in node["captures"],
                    "has_typeinfo": "learning.typeinfo.def" in node["captures"],
                    "has_classname": "learning.classname.def" in node["captures"],
                    "typeinfo_path": node["captures"].get("learning.typeinfo.value", {}).get("text", ""),
                    "classname_value": node["captures"].get("learning.classname.value", {}).get("text", "")
                }
            )
        }
    }
} 