"""
Query patterns for .env files aligned with PATTERN_CATEGORIES.

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
                "name": m.group(1),
                "value": m.group(2),
                "is_export": True,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches export statements",
            examples=["export API_KEY=abcdef12345"]
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
            extract=extract_comment,
            description="Matches comments",
            examples=["# Database configuration"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "url": QueryPattern(
            pattern=r'(https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?::\d+)?(?:/[-\w%!$&\'()*+,;=:@/~]+)*(?:\?(?:[-\w%!$&\'()*+,;=:@/~]|(?:%[\da-fA-F]{2}))*)?(#(?:[-\w%!$&\'()*+,;=:@/~]|(?:%[\da-fA-F]{2}))*)?)',
            extract=lambda m: {
                "url": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches URLs",
            examples=["DATABASE_URL=https://user:pass@example.com/db"]
        ),
        "path": QueryPattern(
            pattern=r'((?:/[-\w.]+)+|(?:[-\w]+/[-\w./]+))',
            extract=lambda m: {
                "path": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches filesystem paths",
            examples=["LOG_FILE=/var/log/app.log"]
        )
    }
}

# Add patterns for repository learning
ENV_PATTERNS_FOR_LEARNING = {
    "configuration_patterns": {
        "database_config": QueryPattern(
            pattern=r'(?s)(?:DB|DATABASE)_(?:URL|HOST|NAME|USER|PASSWORD|PORT)=.+',
            extract=lambda m: {
                "type": "database_config",
                "content": m.group(0),
                "has_database_config": True
            },
            description="Matches database configuration variables",
            examples=["DATABASE_URL=postgres://user:pass@localhost/db"]
        ),
        "api_config": QueryPattern(
            pattern=r'(?s)(?:API_(?:KEY|SECRET|TOKEN|URL|ENDPOINT))=.+',
            extract=lambda m: {
                "type": "api_config",
                "content": m.group(0),
                "has_api_config": True
            },
            description="Matches API configuration variables",
            examples=["API_KEY=abc123def456"]
        ),
        "port_config": QueryPattern(
            pattern=r'PORT=(\d+)',
            extract=lambda m: {
                "type": "port_config",
                "port": int(m.group(1)),
                "is_standard_port": int(m.group(1)) in [80, 443, 3000, 8080]
            },
            description="Matches port configuration",
            examples=["PORT=3000"]
        )
    },
    "naming_conventions": {
        "screaming_snake_case": QueryPattern(
            pattern=r'^([A-Z][A-Z0-9_]*)=',
            extract=lambda m: {
                "type": "naming_convention",
                "convention": "screaming_snake_case",
                "variable": m.group(1),
                "follows_convention": True
            },
            description="Matches SCREAMING_SNAKE_CASE naming convention",
            examples=["DATABASE_URL=postgres://localhost/db"]
        ),
        "snake_case": QueryPattern(
            pattern=r'^([a-z][a-z0-9_]*)=',
            extract=lambda m: {
                "type": "naming_convention",
                "convention": "snake_case",
                "variable": m.group(1),
                "follows_convention": True
            },
            description="Matches snake_case naming convention",
            examples=["database_url=postgres://localhost/db"]
        )
    },
    "best_practices": {
        "secret_pattern": QueryPattern(
            pattern=r'(?:SECRET|PASSWORD|KEY|TOKEN)=([^#\n]+)',
            extract=lambda m: {
                "type": "secret_pattern",
                "masked_value": "*" * len(m.group(1)),
                "contains_sensitive_data": True
            },
            description="Matches patterns for sensitive data",
            examples=["API_SECRET=abcdef12345"]
        ),
        "commented_variable": QueryPattern(
            pattern=r'#\s*([A-Za-z0-9_]+=.+)',
            extract=lambda m: {
                "type": "commented_variable",
                "variable": m.group(1),
                "is_commented": True
            },
            description="Matches commented out environment variables",
            examples=["# DEBUG=true"]
        )
    }
}

# Add the repository learning patterns to the main patterns
ENV_PATTERNS['REPOSITORY_LEARNING'] = ENV_PATTERNS_FOR_LEARNING

# Function to extract patterns for repository learning
def extract_env_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from .env file content for repository learning."""
    patterns = []
    
    # Process configuration patterns
    for pattern_name, pattern in ENV_PATTERNS_FOR_LEARNING["configuration_patterns"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "configuration_pattern"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.85
            })
    
    # Process naming convention patterns
    for pattern_name, pattern in ENV_PATTERNS_FOR_LEARNING["naming_conventions"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "naming_convention"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.8
            })
    
    # Process best practices patterns
    for pattern_name, pattern in ENV_PATTERNS_FOR_LEARNING["best_practices"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "best_practice"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.75
            })
            
    return patterns

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