"""
Query patterns for LaTeX files.
"""

from parsers.file_classification import FileType
from .common import COMMON_PATTERNS

LATEX_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (generic_command
                    command: (command_name) @syntax.function.name
                    arguments: (_)* @syntax.function.args) @syntax.function.def,
                (new_command_definition
                    command: (command_name) @syntax.function.new.name
                    arguments: (_)* @syntax.function.new.args) @syntax.function.new.def
            ]
            """
        },
        "environment": {
            "pattern": """
            [
                (generic_environment
                    begin: (begin) @syntax.environment.begin
                    name: (curly_group_text) @syntax.environment.name
                    content: (_)* @syntax.environment.content
                    end: (end) @syntax.environment.end) @syntax.environment.def,
                (environment_definition
                    name: (curly_group_text) @syntax.environment.new.name
                    content: (_)* @syntax.environment.new.content) @syntax.environment.new.def
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (line_comment) @documentation.comment.line,
                (block_comment) @documentation.comment.block,
                (comment_environment) @documentation.comment.env
            ]
            """
        }
    },

    "structure": {
        "section": {
            "pattern": """
            [
                (chapter
                    command: [(\\chapter) (\\chapter*)] @structure.section.chapter.command
                    text: (curly_group) @structure.section.chapter.title) @structure.section.chapter,
                (section
                    command: [(\\section) (\\section*)] @structure.section.command
                    text: (curly_group) @structure.section.title) @structure.section,
                (subsection
                    command: [(\\subsection) (\\subsection*)] @structure.section.sub.command
                    text: (curly_group) @structure.section.sub.title) @structure.section.sub,
                (subsubsection
                    command: [(\\subsubsection) (\\subsubsection*)] @structure.section.subsub.command
                    text: (curly_group) @structure.section.subsub.title) @structure.section.subsub
            ]
            """
        },
        "import": {
            "pattern": """
            [
                (package_include
                    command: (\\usepackage) @structure.import.package.command
                    options: (brack_group)? @structure.import.package.options
                    paths: (curly_group) @structure.import.package.paths) @structure.import.package,
                (class_include
                    command: (\\documentclass) @structure.import.class.command
                    options: (brack_group)? @structure.import.class.options
                    name: (curly_group) @structure.import.class.name) @structure.import.class
            ]
            """
        }
    }
} 