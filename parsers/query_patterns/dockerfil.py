"""
Query patterns for Dockerfile parsing.
This module is named 'dockerfil' to avoid conflicts with 'dockerfile'.
"""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)

DOCKERFILE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "instruction": QueryPattern(
                pattern=r"^\s*(FROM|MAINTAINER|RUN|CMD|ENTRYPOINT|LABEL|ENV|ADD|COPY|VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL)\s+(.+)$",
                extract=lambda node: {
                    "instruction": node.group(1),
                    "value": node.group(2)
                }
            ),
            "base_image": QueryPattern(
                pattern=r"^\s*FROM\s+(?:--platform=[^\s]+\s+)?([^\s:]+)(?::([^\s]+))?(?:\s+(?:as|AS)\s+([^\s]+))?",
                extract=lambda node: {
                    "image": node.group(1),
                    "tag": node.group(2) or "latest",
                    "alias": node.group(3)
                }
            ),
            "expose": QueryPattern(
                pattern=r"^\s*EXPOSE\s+(\d+(?:-\d+)?(?:\/(?:tcp|udp))?(?:\s+\d+(?:-\d+)?(?:\/(?:tcp|udp))?)*)",
                extract=lambda node: {
                    "ports": node.group(1).split()
                }
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern=r"^\s*#\s*(.+)$",
                extract=lambda node: {
                    "comment": node.group(1)
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern=r"\$(?:\{([A-Za-z0-9_]+)(?::-([^}]+))?\}|([A-Za-z0-9_]+))",
                extract=lambda node: {
                    "variable": node.group(1) or node.group(3),
                    "default": node.group(2)
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "base_image_patterns": QueryPattern(
                pattern=r"^\s*FROM\s+(?:--platform=[^\s]+\s+)?([^\s:]+)(?::([^\s]+))?(?:\s+(?:as|AS)\s+([^\s]+))?",
                extract=lambda node: {
                    "type": "base_image_pattern",
                    "image": node.group(1),
                    "tag": node.group(2) or "latest",
                    "uses_alias": bool(node.group(3)),
                    "uses_platform": bool("--platform" in node.group(0))
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "run_command_patterns": QueryPattern(
                pattern=r"^\s*RUN\s+(.+)$",
                extract=lambda node: {
                    "type": "run_command_pattern",
                    "command": node.group(1),
                    "uses_shell_form": not node.group(1).startswith("["),
                    "uses_exec_form": node.group(1).startswith("["),
                    "has_multiple_commands": "&&" in node.group(1) or ";" in node.group(1)
                }
            )
        }
    }
}

# Module identification
LANGUAGE = "dockerfile" 