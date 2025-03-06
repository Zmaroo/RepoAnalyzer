"""
Query patterns for EditorConfig files aligned with PATTERN_CATEGORIES.

These patterns target the custom AST produced by our custom editorconfig parser.
"""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternPurpose
import re

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "glob": match.group(1).strip(),
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

EDITORCONFIG_PATTERNS = {
    PatternCategory.SYNTAX: {
        "section": QueryPattern(
            pattern=r'^\[(.*)\]$',
            extract=extract_section,
            description="Matches EditorConfig section headers",
            examples=["[*.py]", "[*.{js,py}]"]
        ),
        "property": QueryPattern(
            pattern=r'^([^=]+)=(.*)$',
            extract=extract_property,
            description="Matches EditorConfig property assignments",
            examples=["indent_size = 4", "end_of_line = lf"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "root": QueryPattern(
            pattern=r'^root\s*=\s*(true|false)$',
            extract=lambda m: {
                "type": "root",
                "value": m.group(1).lower() == "true",
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig root declaration",
            examples=["root = true"]
        ),
        "glob_pattern": QueryPattern(
            pattern=r'^\[([^\]]+)\]$',
            extract=lambda m: {
                "type": "glob_pattern",
                "pattern": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches glob patterns in section headers",
            examples=["[*.{js,py}]", "[lib/**.js]"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": QueryPattern(
            pattern=r'^[#;](.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig comments",
            examples=["# This is a comment", "; Another comment"]
        ),
        "section_comment": QueryPattern(
            pattern=r'^[#;]\s*Section:\s*(.*)$',
            extract=lambda m: {
                "type": "section_comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches section documentation",
            examples=["# Section: JavaScript files"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "indent": QueryPattern(
            pattern=r'^indent_(style|size)\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "indent",
                "property": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig indentation settings",
            examples=["indent_style = space", "indent_size = 2"]
        ),
        "charset": QueryPattern(
            pattern=r'^charset\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "charset",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig charset settings",
            examples=["charset = utf-8"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "file_type_pattern": QueryPattern(
            pattern=r'^\[.*\.([\w,{}]+)\]$',
            extract=lambda m: {
                "type": "file_type_pattern",
                "extensions": m.group(1).split(','),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches file type patterns",
            examples=["[*.{js,ts}]", "[*.py]"]
        ),
        "code_style": QueryPattern(
            pattern=r'^(max_line_length|tab_width|quote_type)\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "code_style",
                "property": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches code style settings",
            examples=["max_line_length = 80", "quote_type = single"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "include_pattern": QueryPattern(
            pattern=r'^\[.*/?([\w-]+/)*\*\*?/.*\]$',
            extract=lambda m: {
                "type": "include_pattern",
                "path": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches dependency inclusion patterns",
            examples=["[lib/**.js]", "[vendor/**/*.ts]"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "whitespace": QueryPattern(
            pattern=r'^(trim_trailing_whitespace|insert_final_newline)\s*=\s*(true|false)$',
            extract=lambda m: {
                "type": "whitespace",
                "property": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches whitespace best practices",
            examples=["trim_trailing_whitespace = true"]
        ),
        "end_of_line": QueryPattern(
            pattern=r'^end_of_line\s*=\s*(lf|crlf|cr)$',
            extract=lambda m: {
                "type": "end_of_line",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches line ending settings",
            examples=["end_of_line = lf"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "invalid_value": QueryPattern(
            pattern=r'^([^=]+)=\s*(.*?)\s*$',
            extract=lambda m: {
                "type": "invalid_value",
                "key": m.group(1).strip(),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects potentially invalid values",
            examples=["indent_size = invalid"]
        ),
        "duplicate_section": QueryPattern(
            pattern=r'^\[(.*)\]$',
            extract=lambda m: {
                "type": "duplicate_section",
                "glob": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects duplicate section headers",
            examples=["[*.py]", "[*.py]"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_property": QueryPattern(
            pattern=r'^([a-z][a-z0-9_]*)\s*=\s*(.*)$',
            extract=lambda m: {
                "type": "custom_property",
                "key": m.group(1),
                "value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom EditorConfig properties",
            examples=["my_setting = value"]
        )
    }
}

# Add repository learning patterns
EDITORCONFIG_PATTERNS[PatternCategory.LEARNING] = {
    "configuration_patterns": QueryPattern(
        pattern=r'(?s)\[\*\].*?indent_style\s*=\s*(tab|space).*?indent_size\s*=\s*(\d+)',
        extract=lambda m: {
            "type": "indentation_config",
            "indent_style": m.group(1),
            "indent_size": m.group(2),
            "complete_config": True,
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches complete indentation configuration",
        examples=["[*]\nindent_style = space\nindent_size = 2"]
    ),
    "language_specific_patterns": QueryPattern(
        pattern=r'(?s)\[\*\.(?:py|js|jsx|ts|tsx|html|css|htm)\](.*?)(?=\[|$)',
        extract=lambda m: {
            "type": "language_config_pattern",
            "language": m.group(0).split('.')[1].split(']')[0],
            "content": m.group(1),
            "has_language_config": True,
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches language-specific configuration",
        examples=["[*.py]\nindent_size = 4"]
    ),
    "best_practices_patterns": QueryPattern(
        pattern=r'(?s)\[(.*?)\].*?(end_of_line|trim_trailing_whitespace|insert_final_newline)\s*=\s*(.*?)(?=\n|$)',
        extract=lambda m: {
            "type": "best_practice_pattern",
            "glob": m.group(1),
            "property": m.group(2),
            "value": m.group(3),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches best practice configurations",
        examples=["[*]\nend_of_line = lf"]
    )
}

# Function to extract patterns for repository learning
def extract_editorconfig_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from EditorConfig content for repository learning."""
    patterns = []
    
    # Process each pattern category
    for category in PatternCategory:
        if category in EDITORCONFIG_PATTERNS:
            category_patterns = EDITORCONFIG_PATTERNS[category]
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
        "can_be_contained_by": ["editorconfig"]
    },
    "property": {
        "can_be_contained_by": ["section"]
    },
    "comment": {
        "can_be_contained_by": ["section", "editorconfig"]
    }
} 