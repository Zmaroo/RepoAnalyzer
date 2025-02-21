"""Query patterns for QML directory files."""

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
    }
} 