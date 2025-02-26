"""Query patterns for reStructuredText files."""

from typing import Dict, Any, List, Match, Optional
import re
from parsers.types import QueryPattern, PatternCategory, PatternInfo

# Language identifier
LANGUAGE = "rst"

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "marker": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_directive(match: Match) -> Dict[str, Any]:
    """Extract directive information."""
    return {
        "type": "directive",
        "name": match.group(1),
        "content": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

RST_PATTERNS = {
    PatternCategory.SYNTAX: {
        "section": QueryPattern(
            pattern=r'^([=`~:\'"^_*+#-])\1{3,}\s*$',
            extract=extract_section,
            description="Matches section underlines",
            examples=["====", "----"]
        ),
        "directive": QueryPattern(
            pattern=r'\.\.\s+(\w+)::\s*(.*)$',
            extract=extract_directive,
            description="Matches directives",
            examples=[".. note::", ".. code-block:: python"]
        ),
        "role": QueryPattern(
            pattern=r':([^:]+):`([^`]+)`',
            extract=lambda m: {
                "type": "role",
                "role_type": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches inline roles",
            examples=[":ref:`link`", ":class:`name`"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "reference": QueryPattern(
            pattern=r'`([^`]+)`_',
            extract=lambda m: {
                "type": "reference",
                "target": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches references",
            examples=["`link`_"]
        ),
        "include": QueryPattern(
            pattern=r'\.\.\s+include::\s*(.+)$',
            extract=lambda m: {
                "type": "include",
                "path": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include directives",
            examples=[".. include:: file.rst"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "field": QueryPattern(
            pattern=r':([^:]+):\s+(.+)$',
            extract=lambda m: {
                "type": "field",
                "name": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches field lists",
            examples=[":author: Name"]
        ),
        "admonition": QueryPattern(
            pattern=r'\.\.\s+(note|warning|important|tip|caution)::\s*(.*)$',
            extract=lambda m: {
                "type": "admonition",
                "admonition_type": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches admonitions",
            examples=[".. note::", ".. warning::"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "link": QueryPattern(
            pattern=r'`([^`]+)\s*<([^>]+)>`_',
            extract=lambda m: {
                "type": "link",
                "text": m.group(1),
                "url": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches external links",
            examples=["`Python <https://python.org>`_"]
        ),
        "substitution": QueryPattern(
            pattern=r'\|([^|]+)\|',
            extract=lambda m: {
                "type": "substitution",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches substitutions",
            examples=["|name|"]
        )
    }
}

# RST patterns specifically for repository learning
RST_PATTERNS_FOR_LEARNING = {
    # Section patterns
    'section_marker': PatternInfo(
        pattern=r'^([=`~:\'"^_*+#-])\1{3,}\s*$',
        extract=lambda match: {
            'marker': match.group(1),
            'type': 'section_marker'
        }
    ),
    
    'section_title': PatternInfo(
        pattern=r'^([^\n]+)\n([=`~:\'"^_*+#-])\2{3,}\s*$',
        extract=lambda match: {
            'title': match.group(1),
            'marker': match.group(2),
            'type': 'section_title'
        }
    ),
    
    # Directive patterns
    'directive': PatternInfo(
        pattern=r'\.\.\s+(\w+)::\s*(.*)$',
        extract=lambda match: {
            'name': match.group(1),
            'content': match.group(2),
            'type': 'directive'
        }
    ),
    
    'admonition': PatternInfo(
        pattern=r'\.\.\s+(note|warning|important|tip|caution)::\s*(.*)$',
        extract=lambda match: {
            'type': match.group(1),
            'content': match.group(2),
            'category': 'admonition'
        }
    ),
    
    'code_block': PatternInfo(
        pattern=r'\.\.\s+code(?:-block)?::\s*(\w+)\s*$',
        extract=lambda match: {
            'language': match.group(1),
            'type': 'code_block'
        }
    ),
    
    # Role patterns
    'role': PatternInfo(
        pattern=r':([^:]+):`([^`]+)`',
        extract=lambda match: {
            'role_type': match.group(1),
            'content': match.group(2),
            'type': 'role'
        }
    ),
    
    # Reference patterns
    'reference': PatternInfo(
        pattern=r'`([^`]+)`_',
        extract=lambda match: {
            'target': match.group(1),
            'type': 'reference'
        }
    ),
    
    'external_link': PatternInfo(
        pattern=r'`([^`]+)\s*<([^>]+)>`_',
        extract=lambda match: {
            'text': match.group(1),
            'url': match.group(2),
            'type': 'external_link'
        }
    ),
    
    # Include patterns
    'include': PatternInfo(
        pattern=r'\.\.\s+include::\s*(.+)$',
        extract=lambda match: {
            'path': match.group(1),
            'type': 'include'
        }
    ),
    
    # Field list patterns
    'field': PatternInfo(
        pattern=r':([^:]+):\s+(.+)$',
        extract=lambda match: {
            'name': match.group(1),
            'content': match.group(2),
            'type': 'field'
        }
    ),
    
    # List patterns
    'bullet_list': PatternInfo(
        pattern=r'^\s*[-*+•]\s+(.+)$',
        extract=lambda match: {
            'content': match.group(1),
            'type': 'bullet_list'
        }
    ),
    
    'enumerated_list': PatternInfo(
        pattern=r'^\s*(\d+|[a-zA-Z]|[ivxlcdmIVXLCDM]+)[.)]\s+(.+)$',
        extract=lambda match: {
            'enumeration': match.group(1),
            'content': match.group(2),
            'type': 'enumerated_list'
        }
    )
}

# Update RST_PATTERNS with learning patterns
RST_PATTERNS[PatternCategory.LEARNING] = RST_PATTERNS_FOR_LEARNING

def extract_rst_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """
    Extract RST patterns from content for repository learning.
    
    Args:
        content: The RST content to analyze
        
    Returns:
        List of extracted patterns with metadata
    """
    patterns = []
    
    # Compile patterns
    compiled_patterns = {
        name: re.compile(pattern_info.pattern, re.MULTILINE)
        for name, pattern_info in RST_PATTERNS_FOR_LEARNING.items()
    }
    
    # Process section patterns
    section_markers = {}
    for match in compiled_patterns['section_marker'].finditer(content):
        marker = match.group(1)
        if marker not in section_markers:
            section_markers[marker] = 0
        section_markers[marker] += 1
    
    section_titles = []
    for match in compiled_patterns['section_title'].finditer(content):
        extracted = RST_PATTERNS_FOR_LEARNING['section_title'].extract(match)
        section_titles.append(extracted)
    
    if section_markers:
        patterns.append({
            'name': 'rst_section_structure',
            'content': f"Document uses {len(section_markers)} different section levels",
            'metadata': {
                'markers': section_markers,
                'titles': [title.get('title', '') for title in section_titles[:5]]
            },
            'confidence': 0.9
        })
    
    # Process directive patterns
    directives = {}
    for directive_type in ['directive', 'admonition', 'code_block']:
        if directive_type in compiled_patterns:
            for match in compiled_patterns[directive_type].finditer(content):
                extracted = RST_PATTERNS_FOR_LEARNING[directive_type].extract(match)
                directive_name = extracted.get('name', extracted.get('type', 'unknown'))
                if directive_name not in directives:
                    directives[directive_name] = []
                directives[directive_name].append(extracted)
    
    for directive_name, instances in directives.items():
        if len(instances) >= 2:  # Only include if used multiple times
            patterns.append({
                'name': f'rst_directive_{directive_name}',
                'content': f"Document uses {len(instances)} '{directive_name}' directives",
                'metadata': {
                    'directive_type': directive_name,
                    'count': len(instances),
                    'examples': instances[:3]  # Include up to 3 examples
                },
                'confidence': 0.85
            })
    
    # Process role patterns
    roles = {}
    for match in compiled_patterns['role'].finditer(content):
        extracted = RST_PATTERNS_FOR_LEARNING['role'].extract(match)
        role_type = extracted.get('role_type', 'unknown')
        if role_type not in roles:
            roles[role_type] = []
        roles[role_type].append(extracted)
    
    for role_type, instances in roles.items():
        patterns.append({
            'name': f'rst_role_{role_type}',
            'content': f"Document uses {len(instances)} '{role_type}' roles",
            'metadata': {
                'role_type': role_type,
                'count': len(instances),
                'examples': instances[:3]  # Include up to 3 examples
            },
            'confidence': 0.8
        })
    
    # Process reference patterns
    references = []
    for pattern_name in ['reference', 'external_link']:
        for match in compiled_patterns[pattern_name].finditer(content):
            extracted = RST_PATTERNS_FOR_LEARNING[pattern_name].extract(match)
            references.append(extracted)
    
    if references:
        patterns.append({
            'name': 'rst_references',
            'content': f"Document contains {len(references)} references/links",
            'metadata': {
                'references': references[:5],  # Include up to 5 examples
                'count': len(references)
            },
            'confidence': 0.85
        })
    
    # Process include patterns
    includes = []
    for match in compiled_patterns['include'].finditer(content):
        extracted = RST_PATTERNS_FOR_LEARNING['include'].extract(match)
        includes.append(extracted)
    
    if includes:
        patterns.append({
            'name': 'rst_modular_documentation',
            'content': f"Document uses modular structure with {len(includes)} includes",
            'metadata': {
                'includes': [include.get('path', '') for include in includes],
                'count': len(includes)
            },
            'confidence': 0.9
        })
    
    # Process field patterns
    fields = []
    for match in compiled_patterns['field'].finditer(content):
        extracted = RST_PATTERNS_FOR_LEARNING['field'].extract(match)
        fields.append(extracted)
    
    if fields:
        patterns.append({
            'name': 'rst_metadata_fields',
            'content': f"Document contains {len(fields)} metadata fields",
            'metadata': {
                'fields': fields[:5],  # Include up to 5 examples
                'count': len(fields)
            },
            'confidence': 0.85
        })
    
    # Process list patterns
    bullet_items = []
    for match in compiled_patterns['bullet_list'].finditer(content):
        extracted = RST_PATTERNS_FOR_LEARNING['bullet_list'].extract(match)
        bullet_items.append(extracted)
    
    enumerated_items = []
    for match in compiled_patterns['enumerated_list'].finditer(content):
        extracted = RST_PATTERNS_FOR_LEARNING['enumerated_list'].extract(match)
        enumerated_items.append(extracted)
    
    if bullet_items or enumerated_items:
        patterns.append({
            'name': 'rst_lists',
            'content': f"Document contains {len(bullet_items)} bullet list items and {len(enumerated_items)} enumerated list items",
            'metadata': {
                'bullet_items': [item.get('content', '') for item in bullet_items[:3]],
                'enumerated_items': [item.get('content', '') for item in enumerated_items[:3]],
                'bullet_count': len(bullet_items),
                'enumerated_count': len(enumerated_items)
            },
            'confidence': 0.8
        })
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["section", "directive", "field", "admonition"],
        "can_be_contained_by": []
    },
    "section": {
        "can_contain": ["section", "directive", "field", "reference", "link"],
        "can_be_contained_by": ["document", "section"]
    },
    "directive": {
        "can_contain": ["field"],
        "can_be_contained_by": ["document", "section"]
    }
} 