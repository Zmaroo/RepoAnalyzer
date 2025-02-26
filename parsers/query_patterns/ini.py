"""Query patterns for INI/Properties files."""

from typing import Dict, Any, List, Match, Optional
import re
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternInfo

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
    }
}

# INI patterns specifically for repository learning
INI_PATTERNS_FOR_LEARNING = {
    # Section patterns
    'common_sections': PatternInfo(
        pattern=r'^\s*\[(database|server|logging|app|application|web|api|security|auth|network|client|connection)\]\s*$',
        extract=lambda match: {
            'section_type': match.group(1).lower(),
            'name': match.group(1),
            'content': match.group(0)
        }
    ),
    
    # Property categories
    'connection_properties': PatternInfo(
        pattern=r'^\s*(host|server|url|endpoint|address|port)\s*=\s*(.*)$',
        extract=lambda match: {
            'category': 'connection',
            'key': match.group(1).strip(),
            'value': match.group(2).strip()
        }
    ),
    
    'auth_properties': PatternInfo(
        pattern=r'^\s*(user|username|password|auth|token|key|secret|credentials)\s*=\s*(.*)$',
        extract=lambda match: {
            'category': 'authentication',
            'key': match.group(1).strip(),
            'value': match.group(2).strip()
        }
    ),
    
    'logging_properties': PatternInfo(
        pattern=r'^\s*(log|debug|verbose|trace|level)\s*=\s*(.*)$',
        extract=lambda match: {
            'category': 'logging',
            'key': match.group(1).strip(),
            'value': match.group(2).strip()
        }
    ),
    
    'filesystem_properties': PatternInfo(
        pattern=r'^\s*(dir|directory|path|file|folder)\s*=\s*(.*)$',
        extract=lambda match: {
            'category': 'filesystem',
            'key': match.group(1).strip(),
            'value': match.group(2).strip()
        }
    ),
    
    # Reference patterns
    'env_var_references': PatternInfo(
        pattern=r'^\s*([^=]+?)\s*=\s*\$\{(\w+)\}',
        extract=lambda match: {
            'reference_type': 'environment',
            'key': match.group(1).strip(),
            'variable': match.group(2)
        }
    ),
    
    'include_references': PatternInfo(
        pattern=r'^\s*(include|import|require)\s*=\s*(.*)$',
        extract=lambda match: {
            'reference_type': 'include',
            'directive': match.group(1).strip(),
            'path': match.group(2).strip()
        }
    ),
    
    # Naming conventions
    'property_naming': PatternInfo(
        pattern=r'^\s*([a-zA-Z0-9_.-]+)\s*=',
        extract=lambda match: {
            'key': match.group(1).strip(),
            'convention': 'snake_case' if '_' in match.group(1) else
                         'kebab-case' if '-' in match.group(1) else
                         'camelCase' if match.group(1)[0].islower() and any(c.isupper() for c in match.group(1)) else
                         'lowercase' if match.group(1).islower() else
                         'UPPERCASE' if match.group(1).isupper() else
                         'mixed'
        }
    )
}

# Update INI_PATTERNS with learning patterns
INI_PATTERNS[PatternCategory.LEARNING] = INI_PATTERNS_FOR_LEARNING

def extract_ini_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """
    Extract INI patterns from content for repository learning.
    
    Args:
        content: The INI content to analyze
        
    Returns:
        List of extracted patterns with metadata
    """
    patterns = []
    
    # Compile patterns
    compiled_patterns = {
        name: re.compile(pattern_info.pattern, re.MULTILINE)
        for name, pattern_info in INI_PATTERNS_FOR_LEARNING.items()
    }
    
    # Process section patterns
    section_types = {}
    for match in compiled_patterns['common_sections'].finditer(content):
        extracted = INI_PATTERNS_FOR_LEARNING['common_sections'].extract(match)
        section_type = extracted['section_type']
        section_types[section_type] = section_types.get(section_type, 0) + 1
    
    if section_types:
        patterns.append({
            'name': 'ini_common_sections',
            'content': ', '.join(section_types.keys()),
            'metadata': {
                'section_types': section_types
            },
            'confidence': 0.9 if len(section_types) > 2 else 0.8
        })
    
    # Process property categories
    property_categories = {}
    for category in ['connection', 'auth', 'logging', 'filesystem']:
        pattern_name = f'{category}_properties'
        if pattern_name in compiled_patterns:
            properties = []
            for match in compiled_patterns[pattern_name].finditer(content):
                extracted = INI_PATTERNS_FOR_LEARNING[pattern_name].extract(match)
                properties.append({
                    'key': extracted['key'],
                    'value': extracted['value']
                })
            
            if properties:
                property_categories[category] = properties
    
    for category, props in property_categories.items():
        if props:
            patterns.append({
                'name': f'ini_{category}_properties',
                'content': '\n'.join(f"{prop['key']} = {prop['value']}" for prop in props[:3]),
                'metadata': {
                    'category': category,
                    'properties': props
                },
                'confidence': 0.85
            })
    
    # Process reference patterns
    references = {}
    for ref_type in ['env_var_references', 'include_references']:
        refs = []
        for match in compiled_patterns[ref_type].finditer(content):
            extracted = INI_PATTERNS_FOR_LEARNING[ref_type].extract(match)
            refs.append(extracted)
        
        if refs:
            ref_category = extracted['reference_type']
            references[ref_category] = refs
    
    for ref_category, refs in references.items():
        if refs:
            patterns.append({
                'name': f'ini_{ref_category}_references',
                'content': '\n'.join(str(ref) for ref in refs[:3]),
                'metadata': {
                    'reference_type': ref_category,
                    'references': refs
                },
                'confidence': 0.9
            })
    
    # Process naming conventions
    convention_counts = {}
    for match in compiled_patterns['property_naming'].finditer(content):
        extracted = INI_PATTERNS_FOR_LEARNING['property_naming'].extract(match)
        convention = extracted['convention']
        convention_counts[convention] = convention_counts.get(convention, 0) + 1
    
    if convention_counts:
        # Find the dominant convention
        dominant_convention = max(convention_counts.items(), key=lambda x: x[1])
        
        if dominant_convention[1] >= 3:  # Only include if we have enough examples
            # Get some examples of keys with this convention
            examples = []
            for match in compiled_patterns['property_naming'].finditer(content):
                extracted = INI_PATTERNS_FOR_LEARNING['property_naming'].extract(match)
                if extracted['convention'] == dominant_convention[0]:
                    examples.append(extracted['key'])
                    if len(examples) >= 5:
                        break
            
            patterns.append({
                'name': f'ini_naming_convention_{dominant_convention[0]}',
                'content': f"INI naming convention: {dominant_convention[0]}",
                'metadata': {
                    'convention': dominant_convention[0],
                    'count': dominant_convention[1],
                    'examples': examples,
                    'all_conventions': convention_counts
                },
                'confidence': min(0.7 + (dominant_convention[1] / 20), 0.95)  # Higher confidence with more instances
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