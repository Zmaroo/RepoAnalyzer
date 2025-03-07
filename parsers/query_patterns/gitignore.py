"""Query patterns for gitignore files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

GITIGNORE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "pattern": QueryPattern(
                pattern="""
                [
                    (pattern) @syntax.pattern.def,
                    (negated_pattern) @syntax.pattern.negated,
                    (directory_pattern) @syntax.pattern.directory
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "negated" if "syntax.pattern.negated" in node["captures"] else
                        "directory" if "syntax.pattern.directory" in node["captures"] else
                        "file"
                    ),
                    "text": (
                        node["captures"].get("syntax.pattern.negated", {}).get("text", "") or
                        node["captures"].get("syntax.pattern.directory", {}).get("text", "") or
                        node["captures"].get("syntax.pattern.def", {}).get("text", "")
                    )
                }
            ),
            "comment": QueryPattern(
                pattern="(comment) @syntax.comment",
                extract=lambda node: {
                    "text": node["captures"].get("syntax.comment", {}).get("text", ""),
                    "type": "comment"
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "section": QueryPattern(
                pattern="(section_header) @semantics.section.header",
                extract=lambda node: {
                    "text": node["captures"].get("semantics.section.header", {}).get("text", "").strip("# "),
                    "type": "section"
                }
            ),
            "expression": QueryPattern(
                pattern="""
                [
                    (blank_line) @semantics.expression.blank,
                    (pattern) @semantics.expression.pattern,
                    (negated_pattern) @semantics.expression.negated
                ]
                """,
                extract=lambda node: {
                    "type": "expression",
                    "expression_type": (
                        "blank" if "semantics.expression.blank" in node["captures"] else
                        "negated" if "semantics.expression.negated" in node["captures"] else
                        "pattern"
                    )
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
            "root": QueryPattern(
                pattern="(root_gitignore) @structure.root",
                extract=lambda node: {
                    "type": "root_gitignore"
                }
            ),
            "global": QueryPattern(
                pattern="(global_gitignore) @structure.global",
                extract=lambda node: {
                    "type": "global_gitignore"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "pattern_types": QueryPattern(
                pattern="""
                [
                    (pattern) @pattern.line,
                    (negated_pattern) @pattern.negated,
                    (directory_pattern) @pattern.directory
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "negated" if "pattern.negated" in node["captures"] else
                        "directory" if "pattern.directory" in node["captures"] else
                        "file" if "pattern.line" in node["captures"] else
                        "other"
                    ),
                    "pattern_text": (
                        node["captures"].get("pattern.negated", {}).get("text", "") or
                        node["captures"].get("pattern.directory", {}).get("text", "") or
                        node["captures"].get("pattern.line", {}).get("text", "")
                    ),
                    "is_negated": "pattern.negated" in node["captures"],
                    "is_directory": "pattern.directory" in node["captures"] or (
                        "pattern.line" in node["captures"] and 
                        node["captures"].get("pattern.line", {}).get("text", "").endswith("/")
                    ),
                    "uses_wildcard": any(
                        wildcard in (
                            node["captures"].get("pattern.negated", {}).get("text", "") or
                            node["captures"].get("pattern.directory", {}).get("text", "") or
                            node["captures"].get("pattern.line", {}).get("text", "")
                        )
                        for wildcard in ["*", "?", "[", "]"]
                    )
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "organization_patterns": QueryPattern(
                pattern="""
                [
                    (section_header) @org.section,
                    (blank_line) @org.blank,
                    (comment) @org.comment
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "section_header" if "org.section" in node["captures"] else
                        "blank_line" if "org.blank" in node["captures"] else
                        "comment" if "org.comment" in node["captures"] else
                        "other"
                    ),
                    "section_name": node["captures"].get("org.section", {}).get("text", "").strip("# "),
                    "comment_text": node["captures"].get("org.comment", {}).get("text", "").strip("# "),
                    "uses_section_headers": "org.section" in node["captures"],
                    "has_comments": "org.comment" in node["captures"]
                }
            )
        },
        PatternPurpose.BEST_PRACTICES: {
            "language_specific_patterns": QueryPattern(
                pattern="""
                [
                    (pattern) @lang.pattern,
                    (negated_pattern) @lang.negated,
                    (directory_pattern) @lang.directory,
                    (comment) @lang.comment
                ]
                """,
                extract=lambda node: {
                    "pattern_text": (
                        node["captures"].get("lang.pattern", {}).get("text", "") or
                        node["captures"].get("lang.negated", {}).get("text", "") or
                        node["captures"].get("lang.directory", {}).get("text", "") or
                        node["captures"].get("lang.comment", {}).get("text", "")
                    ),
                    "language_category": (
                        "python" if any(py_pattern in (
                            node["captures"].get("lang.pattern", {}).get("text", "") or
                            node["captures"].get("lang.negated", {}).get("text", "") or
                            node["captures"].get("lang.directory", {}).get("text", "") or
                            node["captures"].get("lang.comment", {}).get("text", "")
                        ) for py_pattern in ["*.py", "__pycache__", "*.pyc", "venv", ".env", ".venv", "pip-log.txt"]) else
                        
                        "javascript" if any(js_pattern in (
                            node["captures"].get("lang.pattern", {}).get("text", "") or
                            node["captures"].get("lang.negated", {}).get("text", "") or
                            node["captures"].get("lang.directory", {}).get("text", "") or
                            node["captures"].get("lang.comment", {}).get("text", "")
                        ) for js_pattern in ["node_modules", "npm-debug.log", "*.js", "package-lock.json", "yarn.lock"]) else
                        
                        "java" if any(java_pattern in (
                            node["captures"].get("lang.pattern", {}).get("text", "") or
                            node["captures"].get("lang.negated", {}).get("text", "") or
                            node["captures"].get("lang.directory", {}).get("text", "") or
                            node["captures"].get("lang.comment", {}).get("text", "")
                        ) for java_pattern in ["*.class", "*.jar", ".gradle", "build/", "target/"]) else
                        
                        "editor" if any(editor_pattern in (
                            node["captures"].get("lang.pattern", {}).get("text", "") or
                            node["captures"].get("lang.negated", {}).get("text", "") or
                            node["captures"].get("lang.directory", {}).get("text", "") or
                            node["captures"].get("lang.comment", {}).get("text", "")
                        ) for editor_pattern in [".idea/", ".vscode/", "*.swp", "*.swo", ".DS_Store", "Thumbs.db"]) else
                        
                        "system" if any(system_pattern in (
                            node["captures"].get("lang.pattern", {}).get("text", "") or
                            node["captures"].get("lang.negated", {}).get("text", "") or
                            node["captures"].get("lang.directory", {}).get("text", "") or
                            node["captures"].get("lang.comment", {}).get("text", "")
                        ) for system_pattern in [".DS_Store", "Thumbs.db", "desktop.ini"]) else
                        
                        "other"
                    ),
                    "is_dependency_related": any(
                        dep_pattern in (
                            node["captures"].get("lang.pattern", {}).get("text", "") or
                            node["captures"].get("lang.negated", {}).get("text", "") or
                            node["captures"].get("lang.directory", {}).get("text", "") or
                            node["captures"].get("lang.comment", {}).get("text", "")
                        )
                        for dep_pattern in ["node_modules", "vendor/", "bower_components", ".gradle", "pip-log.txt", "venv", "__pycache__"]
                    ),
                    "is_build_output": any(
                        build_pattern in (
                            node["captures"].get("lang.pattern", {}).get("text", "") or
                            node["captures"].get("lang.negated", {}).get("text", "") or
                            node["captures"].get("lang.directory", {}).get("text", "") or
                            node["captures"].get("lang.comment", {}).get("text", "")
                        )
                        for build_pattern in ["build/", "dist/", "out/", "target/", "*.exe", "*.dll", "*.so", "*.o", "*.obj", "*.class"]
                    )
                }
            )
        }
    }
} 