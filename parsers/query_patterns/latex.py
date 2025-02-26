"""
Query patterns for LaTeX files.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

LATEX_PATTERNS_FOR_LEARNING = {
    "document_structure": {
        "pattern": """
        [
            (generic_command
                command: (command_name) @doc.cmd.name
                (#match? @doc.cmd.name "\\\\documentclass|\\\\title|\\\\author|\\\\date|\\\\maketitle|\\\\tableofcontents")) @doc.cmd,
                
            (chapter
                command: (_) @doc.chapter.cmd
                text: (curly_group) @doc.chapter.title) @doc.chapter,
                
            (section
                command: (_) @doc.section.cmd
                text: (curly_group) @doc.section.title) @doc.section,
                
            (subsection
                command: (_) @doc.subsection.cmd
                text: (curly_group) @doc.subsection.title) @doc.subsection
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "document_structure",
            "structure_element": (
                "document_setup" if "doc.cmd" in node["captures"] and node["captures"].get("doc.cmd.name", {}).get("text", "") in ["\\documentclass", "\\title", "\\author", "\\date", "\\maketitle"] else
                "table_of_contents" if "doc.cmd" in node["captures"] and node["captures"].get("doc.cmd.name", {}).get("text", "") == "\\tableofcontents" else
                "chapter" if "doc.chapter" in node["captures"] else
                "section" if "doc.section" in node["captures"] else
                "subsection" if "doc.subsection" in node["captures"] else
                "other"
            ),
            "title_text": (
                node["captures"].get("doc.chapter.title", {}).get("text", "") or
                node["captures"].get("doc.section.title", {}).get("text", "") or
                node["captures"].get("doc.subsection.title", {}).get("text", "")
            ).strip("{}"),
            "uses_structure_hierarchy": any(key in node["captures"] for key in ["doc.chapter", "doc.section", "doc.subsection"]),
            "uses_starred_command": "*" in (
                node["captures"].get("doc.chapter.cmd", {}).get("text", "") or
                node["captures"].get("doc.section.cmd", {}).get("text", "") or
                node["captures"].get("doc.subsection.cmd", {}).get("text", "") or ""
            )
        }
    },
    
    "custom_commands": {
        "pattern": """
        [
            (new_command_definition
                command: (command_name) @custom.cmd.name
                arguments: (_)* @custom.cmd.args) @custom.cmd,
                
            (new_environment_definition
                name: (curly_group_text) @custom.env.name
                arguments: (_)* @custom.env.args) @custom.env
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "custom_definitions",
            "is_command_definition": "custom.cmd" in node["captures"],
            "is_environment_definition": "custom.env" in node["captures"],
            "command_name": node["captures"].get("custom.cmd.name", {}).get("text", ""),
            "environment_name": node["captures"].get("custom.env.name", {}).get("text", ""),
            "has_arguments": (
                "custom.cmd.args" in node["captures"] and node["captures"].get("custom.cmd.args", {}).get("text", "") or
                "custom.env.args" in node["captures"] and node["captures"].get("custom.env.args", {}).get("text", "")
            ),
            "definition_type": "command" if "custom.cmd" in node["captures"] else "environment" if "custom.env" in node["captures"] else "other"
        }
    },
    
    "bibliography_usage": {
        "pattern": """
        [
            (generic_command
                command: (command_name) @bib.cmd.name
                (#match? @bib.cmd.name "\\\\bibliography|\\\\bibliographystyle|\\\\addbibresource|\\\\printbibliography")) @bib.cmd,
                
            (generic_command
                command: (command_name) @bib.cite.name
                (#match? @bib.cite.name "\\\\cite|\\\\textcite|\\\\parencite|\\\\footcite|\\\\autocite")) @bib.cite
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "bibliography",
            "is_bibliography_setup": "bib.cmd" in node["captures"],
            "is_citation": "bib.cite" in node["captures"],
            "command_name": (
                node["captures"].get("bib.cmd.name", {}).get("text", "") or
                node["captures"].get("bib.cite.name", {}).get("text", "")
            ),
            "uses_bibtex": "\\bibliography" in (node["captures"].get("bib.cmd.name", {}).get("text", "") or ""),
            "uses_biblatex": any(
                biblatex in (node["captures"].get("bib.cmd.name", {}).get("text", "") or "")
                for biblatex in ["\\addbibresource", "\\printbibliography"]
            ),
            "citation_type": (
                "standard" if "bib.cite" in node["captures"] and node["captures"].get("bib.cite.name", {}).get("text", "") == "\\cite" else
                "textual" if "bib.cite" in node["captures"] and node["captures"].get("bib.cite.name", {}).get("text", "") == "\\textcite" else
                "parenthetical" if "bib.cite" in node["captures"] and node["captures"].get("bib.cite.name", {}).get("text", "") == "\\parencite" else
                "footnote" if "bib.cite" in node["captures"] and node["captures"].get("bib.cite.name", {}).get("text", "") == "\\footcite" else
                "auto" if "bib.cite" in node["captures"] and node["captures"].get("bib.cite.name", {}).get("text", "") == "\\autocite" else
                "other"
            )
        }
    },
    
    "math_expressions": {
        "pattern": """
        [
            (inline_formula
                content: (_) @math.inline.content) @math.inline,
                
            (displayed_formula
                content: (_) @math.display.content) @math.display,
                
            (generic_environment
                name: (curly_group_text) @math.env.name
                (#match? @math.env.name "^(equation|align|gather|multiline)\\*?$")
                content: (_) @math.env.content) @math.env
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "math_expressions",
            "math_mode": (
                "inline" if "math.inline" in node["captures"] else
                "display" if "math.display" in node["captures"] else
                "environment" if "math.env" in node["captures"] else
                "other"
            ),
            "environment_name": node["captures"].get("math.env.name", {}).get("text", ""),
            "math_content": (
                node["captures"].get("math.inline.content", {}).get("text", "") or
                node["captures"].get("math.display.content", {}).get("text", "") or
                node["captures"].get("math.env.content", {}).get("text", "")
            ),
            "uses_alignment": "align" in (node["captures"].get("math.env.name", {}).get("text", "") or ""),
            "is_numbered": not (node["captures"].get("math.env.name", {}).get("text", "") or "").endswith("*") if "math.env" in node["captures"] else False
        }
    }
}

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
    },
    
    "REPOSITORY_LEARNING": LATEX_PATTERNS_FOR_LEARNING
} 