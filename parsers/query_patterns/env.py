"""
Query patterns for .env files aligned with PATTERN_CATEGORIES.

The parser produces an AST with a root node 'env_file' and children of type 'env_var'.
"""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory

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

def extract_variable(match: Match) -> Dict[str, Any]:
    """Extract variable information."""
    return {
        "type": "variable",
        "name": match.group(1),
        "value": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_export(match: Match) -> Dict[str, Any]:
    """Extract export information."""
    return {
        "type": "export",
        "name": match.group(1),
        "value": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

ENV_PATTERNS = {
    PatternCategory.SYNTAX: {
        "export": QueryPattern(
            pattern=r'^export\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$',
            extract=extract_export,
            description="Matches exported environment variables",
            examples=["export API_KEY=abc123"]
        ),
        "variable": QueryPattern(
            pattern=r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$',
            extract=extract_variable,
            description="Matches environment variable assignments",
            examples=["DEBUG=true"]
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
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": QueryPattern(
            pattern=r'^#\s*(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches comments",
            examples=["# API configuration"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "url": QueryPattern(
            pattern=r'=\s*(https?://\S+)',
            extract=lambda m: {
                "type": "url",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches URL values",
            examples=["API_URL=https://api.example.com"]
        ),
        "path": QueryPattern(
            pattern=r'=\s*([/~][\w/.-]+)',
            extract=lambda m: {
                "type": "path",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches filesystem paths",
            examples=["LOG_PATH=/var/log/app.log"]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "variable": {
        "can_contain": ["quoted_value", "multiline"],
        "can_be_contained_by": ["env_file"]
    },
    "export": {
        "can_contain": ["quoted_value", "multiline"],
        "can_be_contained_by": ["env_file"]
    },
    "comment": {
        "can_be_contained_by": ["env_file"]
    }
} 