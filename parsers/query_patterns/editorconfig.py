"""
Query patterns for EditorConfig files aligned with PATTERN_CATEGORIES.

These patterns target the custom AST produced by our custom editorconfig parser.
"""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
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
    }
}

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

# Add patterns for repository learning
EDITORCONFIG_PATTERNS_FOR_LEARNING = {
    "configuration_patterns": {
        "indentation_config": QueryPattern(
            pattern=r'(?s)\[\*\].*?indent_style\s*=\s*(tab|space).*?indent_size\s*=\s*(\d+)',
            extract=lambda m: {
                "type": "indentation_config",
                "indent_style": m.group(1),
                "indent_size": m.group(2),
                "complete_config": True
            },
            description="Matches complete indentation configuration",
            examples=["[*]\nindent_style = space\nindent_size = 2"]
        ),
        "charset_config": QueryPattern(
            pattern=r'(?s)\[(.*?)\].*?charset\s*=\s*([a-zA-Z0-9-]+)',
            extract=lambda m: {
                "type": "charset_config",
                "glob": m.group(1),
                "charset": m.group(2),
                "is_utf8": m.group(2).lower() == "utf-8"
            },
            description="Matches charset configuration",
            examples=["[*.txt]\ncharset = utf-8"]
        )
    },
    "language_specific_patterns": {
        "python_config": QueryPattern(
            pattern=r'(?s)\[\*\.py\](.*?)(?=\[|$)',
            extract=lambda m: {
                "type": "language_config_pattern",
                "language": "python",
                "content": m.group(1),
                "has_language_config": True
            },
            description="Matches Python-specific configuration",
            examples=["[*.py]\nindent_size = 4\nmax_line_length = 88"]
        ),
        "javascript_config": QueryPattern(
            pattern=r'(?s)\[\*\.(?:js|jsx|ts|tsx)\](.*?)(?=\[|$)',
            extract=lambda m: {
                "type": "language_config_pattern",
                "language": "javascript",
                "content": m.group(1),
                "has_language_config": True
            },
            description="Matches JavaScript/TypeScript configuration",
            examples=["[*.js]\nindent_size = 2"]
        )
    },
    "best_practices": {
        "eol_pattern": QueryPattern(
            pattern=r'end_of_line\s*=\s*(lf|cr|crlf)',
            extract=lambda m: {
                "type": "eol_pattern",
                "eol": m.group(1),
                "is_unix_style": m.group(1) == "lf",
                "is_windows_style": m.group(1) == "crlf"
            },
            description="Matches end of line configuration pattern",
            examples=["end_of_line = lf"]
        ),
        "trim_trailing_whitespace": QueryPattern(
            pattern=r'trim_trailing_whitespace\s*=\s*(true|false)',
            extract=lambda m: {
                "type": "whitespace_pattern",
                "trim_trailing": m.group(1) == "true",
                "is_recommended_practice": m.group(1) == "true"
            },
            description="Matches trailing whitespace configuration",
            examples=["trim_trailing_whitespace = true"]
        )
    }
}

# Add the repository learning patterns to the main patterns
EDITORCONFIG_PATTERNS['REPOSITORY_LEARNING'] = EDITORCONFIG_PATTERNS_FOR_LEARNING

# Function to extract patterns for repository learning
def extract_editorconfig_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from EditorConfig content for repository learning."""
    patterns = []
    
    # Process configuration patterns
    for pattern_name, pattern in EDITORCONFIG_PATTERNS_FOR_LEARNING["configuration_patterns"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "configuration_pattern"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.85
            })
    
    # Process language specific patterns
    for pattern_name, pattern in EDITORCONFIG_PATTERNS_FOR_LEARNING["language_specific_patterns"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "language_config_pattern"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.8
            })
    
    # Process best practices patterns
    for pattern_name, pattern in EDITORCONFIG_PATTERNS_FOR_LEARNING["best_practices"].items():
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