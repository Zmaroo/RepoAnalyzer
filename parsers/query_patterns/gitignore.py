"""Query patterns for gitignore files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

GITIGNORE_PATTERNS_FOR_LEARNING = {
    "pattern_types": {
        "pattern": """
        [
            (pattern) @pattern.line,
            (negated_pattern) @pattern.negated,
            (directory_pattern) @pattern.directory
        ]
        """,
        "extract": lambda node: {
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
    },
    
    "organization_patterns": {
        "pattern": """
        [
            (section_header) @org.section,
            (blank_line) @org.blank,
            (comment) @org.comment
        ]
        """,
        "extract": lambda node: {
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
    },
    
    "language_specific_patterns": {
        "pattern": """
        [
            (pattern) @lang.pattern,
            (negated_pattern) @lang.negated,
            (directory_pattern) @lang.directory,
            (comment) @lang.comment
        ]
        """,
        "extract": lambda node: {
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
    },
    
    "best_practices": {
        "pattern": """
        [
            (root_gitignore) @best.root,
            (global_gitignore) @best.global,
            (pattern) @best.pattern
        ]
        """,
        "extract": lambda node: {
            "pattern_type": (
                "root_gitignore" if "best.root" in node["captures"] else
                "global_gitignore" if "best.global" in node["captures"] else
                "pattern" if "best.pattern" in node["captures"] else
                "other"
            ),
            "uses_global_patterns": "best.global" in node["captures"],
            "follows_root_convention": "best.root" in node["captures"],
            "ignores_editor_files": any(
                editor_pattern in node["captures"].get("best.pattern", {}).get("text", "")
                for editor_pattern in [".idea", ".vscode", "*.swp", "*.swo", ".DS_Store", "Thumbs.db"]
            ),
            "ignores_logs": any(
                log_pattern in node["captures"].get("best.pattern", {}).get("text", "")
                for log_pattern in ["*.log", "logs/", "npm-debug.log", "yarn-debug.log", "yarn-error.log"]
            ),
            "ignores_env_files": any(
                env_pattern in node["captures"].get("best.pattern", {}).get("text", "")
                for env_pattern in [".env", ".env.local", "*.env", ".envrc", ".direnv"]
            )
        }
    }
}

GITIGNORE_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "pattern": {
            "pattern": """
            [
                (pattern) @syntax.pattern.def,
                (negated_pattern) @syntax.pattern.negated,
                (directory_pattern) @syntax.pattern.directory
            ]
            """
        },
        "comment": {
            "pattern": "(comment) @syntax.comment"
        }
    },

    "semantics": {
        "section": {
            "pattern": "(section_header) @semantics.section.header"
        },
        "expression": {
            "pattern": """
            [
                (blank_line) @semantics.expression.blank,
                (pattern) @semantics.expression.pattern,
                (negated_pattern) @semantics.expression.negated
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": "(comment) @documentation.comment"
        }
    },

    "structure": {
        "root": {
            "pattern": "(root_gitignore) @structure.root"
        },
        "global": {
            "pattern": "(global_gitignore) @structure.global"
        }
    },
    
    "REPOSITORY_LEARNING": GITIGNORE_PATTERNS_FOR_LEARNING
} 