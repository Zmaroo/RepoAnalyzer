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

# Enhanced patterns for repository learning
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
        ),
        "insert_final_newline": QueryPattern(
            pattern=r'(?s)\[(.*?)\].*?insert_final_newline\s*=\s*(true|false)',
            extract=lambda m: {
                "type": "newline_config",
                "glob": m.group(1),
                "insert_final_newline": m.group(2).lower() == "true",
                "follows_best_practice": m.group(2).lower() == "true"
            },
            description="Matches final newline configuration",
            examples=["[*]\ninsert_final_newline = true"]
        ),
        "max_line_length": QueryPattern(
            pattern=r'(?s)\[(.*?)\].*?max_line_length\s*=\s*(\d+|off)',
            extract=lambda m: {
                "type": "line_length_config",
                "glob": m.group(1),
                "max_length": m.group(2),
                "has_limit": m.group(2).lower() != "off",
                "is_standard_value": m.group(2) in ["80", "88", "100", "120"]
            },
            description="Matches line length configuration",
            examples=["[*.py]\nmax_line_length = 88"]
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
        ),
        "web_config": QueryPattern(
            pattern=r'(?s)\[\*\.(?:html|css|htm)\](.*?)(?=\[|$)',
            extract=lambda m: {
                "type": "language_config_pattern",
                "language": "web",
                "content": m.group(1),
                "has_language_config": True
            },
            description="Matches web files configuration",
            examples=["[*.html]\nindent_size = 2"]
        ),
        "markup_config": QueryPattern(
            pattern=r'(?s)\[\*\.(?:md|markdown|rst|xml|json|yaml|yml|toml)\](.*?)(?=\[|$)',
            extract=lambda m: {
                "type": "language_config_pattern",
                "language": "markup",
                "content": m.group(1),
                "has_language_config": True
            },
            description="Matches markup files configuration",
            examples=["[*.md]\ntrim_trailing_whitespace = false"]
        ),
        "system_config": QueryPattern(
            pattern=r'(?s)\[(?:Makefile|makefile|*.mk)\](.*?)(?=\[|$)',
            extract=lambda m: {
                "type": "language_config_pattern",
                "language": "makefile",
                "content": m.group(1),
                "forces_tabs": "indent_style = tab" in m.group(1)
            },
            description="Matches Makefile configuration",
            examples=["[Makefile]\nindent_style = tab"]
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
        ),
        "quote_type": QueryPattern(
            pattern=r'quote_type\s*=\s*(single|double|auto)',
            extract=lambda m: {
                "type": "quote_pattern",
                "quote_type": m.group(1),
                "is_consistent": m.group(1) in ["single", "double"]
            },
            description="Matches quote type configuration",
            examples=["quote_type = single"]
        )
    },
    "section_patterns": {
        "wildcard_section": QueryPattern(
            pattern=r'\[\*\](.*?)(?=\[|$)',
            extract=lambda m: {
                "type": "wildcard_section_pattern",
                "content": m.group(1),
                "has_universal_settings": len(m.group(1).strip()) > 0
            },
            description="Matches wildcard section that applies to all files",
            examples=["[*]\nindent_style = space"]
        ),
        "complex_glob_section": QueryPattern(
            pattern=r'\[\*\.(?:\{[^}]+\}|\*|[\w.]+(?:,[\w.]+)+)\](.*?)(?=\[|$)',
            extract=lambda m: {
                "type": "complex_glob_pattern",
                "glob": m.group(0).split(']')[0] + ']',
                "content": m.group(1),
                "uses_braces": '{' in m.group(0).split(']')[0]
            },
            description="Matches sections with complex glob patterns",
            examples=["[*.{js,py}]\ncharset = utf-8"]
        ),
        "nested_glob_section": QueryPattern(
            pattern=r'\[(?:\*\*/|\*\*/)[\w*./]+\](.*?)(?=\[|$)',
            extract=lambda m: {
                "type": "nested_glob_pattern",
                "glob": m.group(0).split(']')[0] + ']',
                "content": m.group(1),
                "uses_double_star": '**' in m.group(0).split(']')[0]
            },
            description="Matches sections with nested directory patterns",
            examples=["[**/node_modules/**]\nindent_size = 2"]
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
    
    # Process section patterns
    for pattern_name, pattern in EDITORCONFIG_PATTERNS_FOR_LEARNING["section_patterns"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "section_pattern"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.8
            })
            
    return patterns 