"""Query patterns for INI/Properties files."""

from typing import Dict, Any, List, Match, Optional
import re
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternPurpose

# Language identifier
LANGUAGE = "ini"

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "name": match.group(1).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_property(match: Match) -> Dict[str, Any]:
    """Extract property information."""
    return {
        "type": "property",
        "key": match.group(1).strip(),
        "value": match.group(2).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

INI_PATTERNS = {
    PatternCategory.SYNTAX: {
        "section": QueryPattern(
            pattern=r'^\s*\[(.*?)\]\s*$',
            extract=extract_section,
            description="Matches INI section headers",
            examples=["[database]", "[server]"]
        ),
        "property": QueryPattern(
            pattern=r'^\s*([^=]+?)\s*=\s*(.*)$',
            extract=extract_property,
            description="Matches INI property assignments",
            examples=["host = localhost", "port = 8080"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "include": QueryPattern(
            pattern=r'^\s*include\s*=\s*(.*)$',
            extract=lambda m: {
                "type": "include",
                "path": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include directives",
            examples=["include = config.ini"]
        ),
        "reference": QueryPattern(
            pattern=r'^\s*([^=]+?)\s*=\s*\$\{([^}]+)\}',
            extract=lambda m: {
                "type": "reference",
                "key": m.group(1).strip(),
                "target": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches variable references",
            examples=["password = ${DB_PASSWORD}"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": QueryPattern(
            pattern=r'^\s*[;#]\s*(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches INI comments",
            examples=["# Database configuration", "; Server settings"]
        ),
        "inline_comment": QueryPattern(
            pattern=r'([^;#]*?)\s*[;#]\s*(.*)$',
            extract=lambda m: {
                "type": "inline_comment",
                "code": m.group(1).strip(),
                "content": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches inline comments",
            examples=["port = 8080  # Default port"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "environment": QueryPattern(
            pattern=r'^\s*([^=]+?)\s*=\s*\$\{?(\w+)\}?',
            extract=lambda m: {
                "type": "environment",
                "key": m.group(1).strip(),
                "variable": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches environment variable references",
            examples=["password = ${DB_PASS}", "api_key = $API_KEY"]
        ),
        "path": QueryPattern(
            pattern=r'^\s*([^=]+?)\s*=\s*([\/\\][^;#\n]+)',
            extract=lambda m: {
                "type": "path",
                "key": m.group(1).strip(),
                "value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches filesystem paths",
            examples=["log_file = /var/log/app.log"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "command": QueryPattern(
            pattern=r'^\s*command\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "command",
                "command": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches command definitions",
            examples=["command = python script.py"]
        ),
        "script": QueryPattern(
            pattern=r'^\s*script\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "script",
                "script": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches script definitions",
            examples=["script = ./run.sh"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "requires": QueryPattern(
            pattern=r'^\s*requires\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "requires",
                "dependencies": [d.strip() for d in m.group(1).split(',')],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches dependency requirements",
            examples=["requires = config.ini, data.ini"]
        ),
        "import": QueryPattern(
            pattern=r'^\s*import\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "import",
                "module": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches import statements",
            examples=["import = common.ini"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "default_value": QueryPattern(
            pattern=r'^\s*([^=]+?)\s*=\s*\$\{([^}:]+):([^}]+)\}',
            extract=lambda m: {
                "type": "default_value",
                "key": m.group(1).strip(),
                "variable": m.group(2),
                "default": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches variables with default values",
            examples=["timeout = ${TIMEOUT:30}"]
        ),
        "validation": QueryPattern(
            pattern=r'^\s*validate_\w+\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "validation",
                "rule": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches validation rules",
            examples=["validate_port = 1024-65535"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "duplicate_key": QueryPattern(
            pattern=r'^\s*([^=]+?)\s*=\s*(.*)$',
            extract=lambda m: {
                "type": "duplicate_key",
                "key": m.group(1).strip(),
                "value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects potential duplicate keys",
            examples=["key = value1", "key = value2"]
        ),
        "invalid_section": QueryPattern(
            pattern=r'^\s*\[(.*?)\]\s*$',
            extract=lambda m: {
                "type": "invalid_section",
                "name": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects potentially invalid sections",
            examples=["[invalid section name]"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_section": QueryPattern(
            pattern=r'^\s*\[([a-z][a-z0-9_-]*)\]\s*$',
            extract=lambda m: {
                "type": "custom_section",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom section names",
            examples=["[my_section]"]
        ),
        "custom_property": QueryPattern(
            pattern=r'^\s*([a-z][a-z0-9_-]*)\s*=\s*(.*)$',
            extract=lambda m: {
                "type": "custom_property",
                "key": m.group(1),
                "value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom property names",
            examples=["my_setting = value"]
        )
    }
}

# Add repository learning patterns
INI_PATTERNS[PatternCategory.LEARNING] = {
    "section_patterns": QueryPattern(
        pattern=r'^\s*\[(.*?)\]\s*\n((?:(?:[^[\n].*?\n)|(?:\s*\n))*)',
        extract=lambda m: {
            "type": "section_pattern",
            "name": m.group(1).strip(),
            "content": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches section patterns",
        examples=["[section]\nkey1 = value1\nkey2 = value2\n"]
    ),
    "property_patterns": QueryPattern(
        pattern=r'^\s*([a-z][a-z0-9_-]*)\s*=\s*([^;#\n]+)',
        extract=lambda m: {
            "type": "property_pattern",
            "key": m.group(1),
            "value": m.group(2).strip(),
            "naming_convention": "snake_case" if "_" in m.group(1) else "kebab-case" if "-" in m.group(1) else "lowercase",
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches property patterns",
        examples=["database_host = localhost"]
    ),
    "value_patterns": QueryPattern(
        pattern=r'^\s*[^=]+=\s*(\$\{[^}]+\}|\$\w+|[\/\\][^;#\n]+|https?://[^;#\n]+)',
        extract=lambda m: {
            "type": "value_pattern",
            "value": m.group(1),
            "value_type": "environment" if m.group(1).startswith("$") else
                         "path" if m.group(1).startswith(("/", "\\")) else
                         "url" if m.group(1).startswith(("http://", "https://")) else
                         "unknown",
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches common value patterns",
        examples=["password = ${DB_PASS}", "log_path = /var/log/app.log"]
    )
}

# Function to extract patterns for repository learning
def extract_ini_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from INI content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in INI_PATTERNS:
            category_patterns = INI_PATTERNS[category]
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
    "section": {
        "can_contain": ["property", "comment"],
        "can_be_contained_by": ["ini_file"]
    },
    "property": {
        "can_contain": ["inline_comment"],
        "can_be_contained_by": ["section", "ini_file"]
    },
    "comment": {
        "can_be_contained_by": ["section", "ini_file"]
    }
} 