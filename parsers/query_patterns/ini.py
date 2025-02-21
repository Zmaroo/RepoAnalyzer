"""Query patterns for INI/Properties files."""

from parsers.pattern_processor import QueryPattern, PatternCategory
from typing import Dict, Any, Match

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
    }
}

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