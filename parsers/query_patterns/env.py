"""
Query patterns for .env files with enhanced pattern support.

The parser produces an AST with a root node 'env_file' and children of type 'env_var'.
"""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

ENVIRONMENT_PATTERNS = {
    "syntax": {
        "export": {
            "pattern": r'^export\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$',
            "extract": lambda match: {
                "type": "export",
                "name": match.group(1),
                "value": match.group(2)
            }
        },
        "variable": {
            "pattern": r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$',
            "extract": lambda match: {
                "type": "variable",
                "name": match.group(1),
                "value": match.group(2)
            }
        }
    },
    "structure": {
        "quoted_value": {
            "pattern": r'^[A-Za-z_][A-Za-z0-9_]*\s*=\s*([\'"](.*)[\'"])$',
            "extract": lambda match: {
                "type": "quoted_value",
                "value": match.group(2),
                "quote_type": match.group(1)[0]
            }
        },
        "multiline": {
            "pattern": r'^[A-Za-z_][A-Za-z0-9_]*\s*=\s*`(.*)`$',
            "extract": lambda match: {
                "type": "multiline",
                "value": match.group(1)
            }
        }
    },
    "documentation": {
        "comment": {
            "pattern": r'^#\s*(.*)$',
            "extract": lambda match: {
                "type": "comment",
                "content": match.group(1).strip()
            }
        }
    },
    "semantics": {
        "url": {
            "pattern": r'=\s*(https?://\S+)',
            "extract": lambda match: {
                "type": "url",
                "value": match.group(1)
            }
        },
        "path": {
            "pattern": r'=\s*([/~][\w/.-]+)',
            "extract": lambda match: {
                "type": "path",
                "value": match.group(1)
            }
        }
    }
}

def extract_comment(match: Match) -> Dict[str, Any]:
    """Extract comment information."""
    return {
        "content": match.group(1).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_variable(match: Match) -> Dict[str, Any]:
    """Extract variable information."""
    return {
        "type": "variable",
        "name": match.group(1),
        "value": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

ENV_PATTERNS = {
    PatternCategory.SYNTAX: {
        "variable": QueryPattern(
            pattern=r'^([A-Za-z0-9_]+)=(.*)$',
            extract=extract_variable,
            description="Matches .env variables",
            examples=["DATABASE_URL=postgres://user:pass@localhost/db"]
        ),
        "export": QueryPattern(
            pattern=r'^export\s+([A-Za-z0-9_]+)=(.*)$',
            extract=lambda m: {
                "type": "export",
                "name": m.group(1),
                "value": m.group(2),
                "is_export": True,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches export statements",
            examples=["export API_KEY=abcdef12345"]
        ),
        "unset": QueryPattern(
            pattern=r'^unset\s+([A-Za-z0-9_]+)\s*$',
            extract=lambda m: {
                "type": "unset",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches unset statements",
            examples=["unset DEBUG"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "quoted_value": QueryPattern(
            pattern=r'^[A-Za-z_][A-Za-z0-9_]*\s*=\s*([\'"](.*)[\'"])$',
            extract=lambda m: {
                "type": "quoted_value",
                "value": m.group(2),
                "quote_type": m.group(1)[0],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches quoted values",
            examples=['SECRET="my-secret"', "KEY='value'"]
        ),
        "multiline": QueryPattern(
            pattern=r'^[A-Za-z_][A-Za-z0-9_]*\s*=\s*`(.*)`$',
            extract=lambda m: {
                "type": "multiline",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches multiline values",
            examples=["CERT=`-----BEGIN CERTIFICATE-----\n...`"]
        ),
        "group": QueryPattern(
            pattern=r'^#\s*\[(.*?)\]\s*$',
            extract=lambda m: {
                "type": "group",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches variable groups",
            examples=["# [Database]"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": QueryPattern(
            pattern=r'^#\s*(.*)$',
            extract=extract_comment,
            description="Matches comments",
            examples=["# Database configuration"]
        ),
        "doc_comment": QueryPattern(
            pattern=r'^#\s*@(\w+)\s+(.*)$',
            extract=lambda m: {
                "type": "doc_comment",
                "tag": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches documentation comments",
            examples=["# @description API configuration"]
        ),
        "section_comment": QueryPattern(
            pattern=r'^#\s*={3,}\s*([^=]+?)\s*={3,}\s*$',
            extract=lambda m: {
                "type": "section_comment",
                "title": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches section comments",
            examples=["# ===== Database Settings ====="]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "url": QueryPattern(
            pattern=r'^([A-Za-z_][A-Za-z0-9_]*_URL)\s*=\s*([^#\n]+)',
            extract=lambda m: {
                "type": "url",
                "name": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches URL variables",
            examples=["DATABASE_URL=postgres://localhost:5432/db"]
        ),
        "path": QueryPattern(
            pattern=r'^([A-Za-z_][A-Za-z0-9_]*_PATH)\s*=\s*([^#\n]+)',
            extract=lambda m: {
                "type": "path",
                "name": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches path variables",
            examples=["LOG_PATH=/var/log/app"]
        ),
        "reference": QueryPattern(
            pattern=r'\$\{([^}]+)\}',
            extract=lambda m: {
                "type": "reference",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches variable references",
            examples=["BASE_URL=${HOST}:${PORT}"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "conditional": QueryPattern(
            pattern=r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\$\{([^:-]+):-([^}]+)\}$',
            extract=lambda m: {
                "type": "conditional",
                "name": m.group(1),
                "variable": m.group(2),
                "default": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches conditional assignments",
            examples=["PORT=${PORT:-3000}"]
        ),
        "command_substitution": QueryPattern(
            pattern=r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\$\((.*?)\)$',
            extract=lambda m: {
                "type": "command_substitution",
                "name": m.group(1),
                "command": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches command substitutions",
            examples=["TIMESTAMP=$(date +%s)"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "import": QueryPattern(
            pattern=r'^source\s+([^#\n]+)',
            extract=lambda m: {
                "type": "import",
                "path": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches source statements",
            examples=["source .env.local"]
        ),
        "dependency_var": QueryPattern(
            pattern=r'^([A-Za-z_][A-Za-z0-9_]*_VERSION)\s*=\s*([^#\n]+)',
            extract=lambda m: {
                "type": "dependency_var",
                "name": m.group(1),
                "version": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches dependency version variables",
            examples=["NODE_VERSION=18.15.0"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "naming_convention": QueryPattern(
            pattern=r'^([A-Za-z][A-Za-z0-9_]*)\s*=',
            extract=lambda m: {
                "type": "naming_convention",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_convention": m.group(1).isupper() and '_' in m.group(1)
            },
            description="Checks variable naming conventions",
            examples=["GOOD_NAME=value", "badName=value"]
        ),
        "sensitive_value": QueryPattern(
            pattern=r'^([A-Za-z_][A-Za-z0-9_]*(?:PASSWORD|SECRET|KEY|TOKEN))\s*=\s*([^#\n]+)',
            extract=lambda m: {
                "type": "sensitive_value",
                "name": m.group(1),
                "is_protected": bool(re.match(r'^[\'"`].*[\'"`]$', m.group(2))),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Checks sensitive value handling",
            examples=["API_KEY=\"secret\"", "PASSWORD=exposed"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "duplicate_variable": QueryPattern(
            pattern=r'^([A-Za-z0-9_]+)\s*=.*\n(?:.*\n)*?\1\s*=',
            extract=lambda m: {
                "type": "duplicate_variable",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_duplicate": True
            },
            description="Detects duplicate variables",
            examples=["DEBUG=true\nDEBUG=false"]
        ),
        "invalid_reference": QueryPattern(
            pattern=r'\$\{([^}]+)\}',
            extract=lambda m: {
                "type": "invalid_reference",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            description="Detects potentially invalid references",
            examples=["URL=${MISSING_VAR}"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_prefix": QueryPattern(
            pattern=r'^([A-Z]+)_[A-Z0-9_]+=',
            extract=lambda m: {
                "type": "custom_prefix",
                "prefix": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom variable prefixes",
            examples=["APP_NAME=myapp", "DB_HOST=localhost"]
        ),
        "custom_format": QueryPattern(
            pattern=r'^format\s*=\s*"([^"]+)".*?pattern\s*=\s*"([^"]+)"',
            extract=lambda m: {
                "type": "custom_format",
                "format": m.group(1),
                "pattern": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom format definitions",
            examples=["format=\"env\"\npattern=\"KEY=VALUE\""]
        )
    }
}

# Add the repository learning patterns
ENV_PATTERNS[PatternCategory.LEARNING] = {
    "variable_patterns": QueryPattern(
        pattern=r'^([A-Za-z0-9_]+)=(.*)$',
        extract=lambda m: {
            "type": "variable_pattern",
            "name": m.group(1),
            "value": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1,
            "naming_style": "uppercase" if m.group(1).isupper() else "mixed"
        },
        description="Learns variable naming patterns",
        examples=["APP_NAME=myapp", "apiKey=abc123"]
    ),
    "group_patterns": QueryPattern(
        pattern=r'(?s)^#\s*\[(.*?)\]\s*\n(.*?)(?=\n#\s*\[|$)',
        extract=lambda m: {
            "type": "group_pattern",
            "name": m.group(1),
            "content": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Learns variable grouping patterns",
        examples=["# [Database]\nDB_HOST=localhost"]
    )
}

# Function to extract patterns for repository learning
def extract_env_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from ENV content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in ENV_PATTERNS:
            category_patterns = ENV_PATTERNS[category]
            for pattern_name, pattern in category_patterns.items():
                if isinstance(pattern, QueryPattern):
                    if isinstance(pattern.pattern, str):
                        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
                            pattern_data = pattern.extract(match)
                            patterns.append({
                                "name": pattern_name,
                                "category": category.value,
                                "content": match.group(0),
                                "metadata": pattern_data,
                                "confidence": 0.85
                            })
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["variable", "export", "comment", "group"],
        "can_be_contained_by": []
    },
    "group": {
        "can_contain": ["variable", "export", "comment"],
        "can_be_contained_by": ["document"]
    },
    "variable": {
        "can_contain": ["reference"],
        "can_be_contained_by": ["document", "group"]
    },
    "export": {
        "can_contain": ["variable"],
        "can_be_contained_by": ["document", "group"]
    }
}

def extract_env_features(ast: dict) -> dict:
    """Extract features that align with pattern categories."""
    features = {
        "syntax": {
            "variables": [],
            "exports": [],
            "unsets": []
        },
        "structure": {
            "quoted_values": [],
            "multilines": [],
            "groups": []
        },
        "semantics": {
            "urls": [],
            "paths": [],
            "references": []
        },
        "documentation": {
            "comments": [],
            "doc_comments": [],
            "section_comments": []
        }
    }
    return features 