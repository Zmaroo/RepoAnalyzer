"""Query patterns for plaintext files."""

from typing import Dict, Any, List, Match, Optional
import re
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternInfo

# Language identifier
LANGUAGE = "plaintext"

def extract_list_item(match: Match) -> Dict[str, Any]:
    """Extract list item information."""
    return {
        "type": "list_item",
        "content": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_header(match: Match) -> Dict[str, Any]:
    """Extract header information."""
    return {
        "type": "header",
        "level": len(match.group(1)),
        "content": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

PLAINTEXT_PATTERNS = {
    PatternCategory.SYNTAX: {
        "list_item": QueryPattern(
            pattern=r'^\s*[-*+•]\s+(.+)$',
            extract=extract_list_item,
            description="Matches unordered list items",
            examples=["* Item", "- Point"]
        ),
        "numbered_item": QueryPattern(
            pattern=r'^\s*\d+[.)]\s+(.+)$',
            extract=lambda m: {
                "type": "numbered_item",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches numbered list items",
            examples=["1. First", "2. Second"]
        ),
        "code_block": QueryPattern(
            pattern=r'^(?:\s{4,}|\t+)(.+)$',
            extract=lambda m: {
                "type": "code_block",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches indented code blocks",
            examples=["    code here", "\tcode here"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "header": QueryPattern(
            pattern=r'^(={2,}|-{2,}|\*{2,}|#{1,6})\s*(.+?)(?:\s*\1)?$',
            extract=extract_header,
            description="Matches headers",
            examples=["# Title", "=== Title ==="]
        ),
        "paragraph": QueryPattern(
            pattern=r'^(?!\s*[-*+•]|\d+[.)]|\s{4}|\t|\|)(.+)$',
            extract=lambda m: {
                "type": "paragraph",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches paragraphs",
            examples=["This is a paragraph"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "metadata": QueryPattern(
            pattern=r'^@(\w+):\s*(.+)$',
            extract=lambda m: {
                "type": "metadata",
                "key": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches metadata tags",
            examples=["@author: John Doe"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "url": QueryPattern(
            pattern=r'https?://\S+',
            extract=lambda m: {
                "type": "url",
                "url": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches URLs",
            examples=["https://example.com"]
        ),
        "email": QueryPattern(
            pattern=r'\b[\w\.-]+@[\w\.-]+\.\w+\b',
            extract=lambda m: {
                "type": "email",
                "address": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches email addresses",
            examples=["user@example.com"]
        )
    }
}

# Plaintext patterns specifically for repository learning
PLAINTEXT_PATTERNS_FOR_LEARNING = {
    # Structure patterns
    'header_pattern': PatternInfo(
        pattern=r'^(#{1,6})\s+(.+)$|^(.+)\n(=+|-+)$',
        extract=lambda match: {
            'level': len(match.group(1)) if match.group(1) else (1 if match.group(4)[0] == '=' else 2),
            'content': match.group(2) if match.group(2) else match.group(3),
            'style': 'hash' if match.group(1) else ('equals' if match.group(4)[0] == '=' else 'dash')
        }
    ),
    
    'bullet_list_item': PatternInfo(
        pattern=r'^\s*([-*+•])\s+(.+)$',
        extract=lambda match: {
            'marker': match.group(1),
            'content': match.group(2),
            'type': 'bullet'
        }
    ),
    
    'numbered_list_item': PatternInfo(
        pattern=r'^\s*(\d+)([.):])\s+(.+)$',
        extract=lambda match: {
            'number': match.group(1),
            'delimiter': match.group(2),
            'content': match.group(3),
            'type': 'numbered'
        }
    ),
    
    # Text block patterns
    'paragraph_pattern': PatternInfo(
        pattern=r'([^\n]+(?:\n(?!\n)[^\n]+)*)',
        extract=lambda match: {
            'content': match.group(1),
            'length': len(match.group(1)),
            'word_count': len(re.findall(r'\b\w+\b', match.group(1)))
        }
    ),
    
    'code_block_pattern': PatternInfo(
        pattern=r'(?:^```(\w*)\n(.*?)^```)|(?:^(?:\s{4}|\t)(.+)(?:\n(?:\s{4}|\t).*)*)',
        extract=lambda match: {
            'language': match.group(1) if match.group(1) else None,
            'content': match.group(2) if match.group(2) else match.group(3),
            'style': 'fenced' if match.group(1) is not None else 'indented'
        }
    ),
    
    # Common formatting patterns
    'emphasis_pattern': PatternInfo(
        pattern=r'(\*|_)([^*_]+)(\*|_)',
        extract=lambda match: {
            'marker': match.group(1),
            'content': match.group(2),
            'type': 'emphasis'
        }
    ),
    
    'strong_pattern': PatternInfo(
        pattern=r'(\*\*|__)([^*_]+)(\*\*|__)',
        extract=lambda match: {
            'marker': match.group(1),
            'content': match.group(2),
            'type': 'strong'
        }
    ),
    
    # Reference patterns
    'url_pattern': PatternInfo(
        pattern=r'(https?://[^\s<>"]+)',
        extract=lambda match: {
            'url': match.group(1),
            'type': 'url'
        }
    ),
    
    'email_pattern': PatternInfo(
        pattern=r'\b([\w.%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b',
        extract=lambda match: {
            'email': match.group(1),
            'type': 'email'
        }
    ),
    
    # Metadata patterns
    'metadata_pattern': PatternInfo(
        pattern=r'^@(\w+):\s+(.+)$',
        extract=lambda match: {
            'key': match.group(1),
            'value': match.group(2),
            'type': 'metadata'
        }
    ),
    
    # Text analysis patterns
    'sentence_pattern': PatternInfo(
        pattern=r'([^.!?]+[.!?])',
        extract=lambda match: {
            'content': match.group(1),
            'length': len(match.group(1)),
            'word_count': len(re.findall(r'\b\w+\b', match.group(1))),
            'type': 'sentence'
        }
    )
}

# Update PLAINTEXT_PATTERNS with learning patterns
PLAINTEXT_PATTERNS[PatternCategory.LEARNING] = PLAINTEXT_PATTERNS_FOR_LEARNING

def extract_plaintext_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """
    Extract plaintext patterns from content for repository learning.
    
    Args:
        content: The plaintext content to analyze
        
    Returns:
        List of extracted patterns with metadata
    """
    patterns = []
    
    # Process headers
    headers = []
    header_matcher = re.compile(PLAINTEXT_PATTERNS_FOR_LEARNING['header_pattern'].pattern, re.MULTILINE)
    for match in header_matcher.finditer(content):
        extracted = PLAINTEXT_PATTERNS_FOR_LEARNING['header_pattern'].extract(match)
        headers.append(extracted)
    
    if headers:
        # Analyze header hierarchy
        header_levels = {}
        for header in headers:
            level = header.get('level', 1)
            if level not in header_levels:
                header_levels[level] = []
            header_levels[level].append(header.get('content', ''))
        
        patterns.append({
            'name': 'plaintext_header_structure',
            'content': f"Document uses {len(header_levels)} header levels",
            'metadata': {
                'header_levels': header_levels,
                'header_count': len(headers),
                'levels': sorted(header_levels.keys())
            },
            'confidence': 0.9
        })
    
    # Process lists
    bullet_items = []
    bullet_matcher = re.compile(PLAINTEXT_PATTERNS_FOR_LEARNING['bullet_list_item'].pattern, re.MULTILINE)
    for match in bullet_matcher.finditer(content):
        extracted = PLAINTEXT_PATTERNS_FOR_LEARNING['bullet_list_item'].extract(match)
        bullet_items.append(extracted)
    
    numbered_items = []
    numbered_matcher = re.compile(PLAINTEXT_PATTERNS_FOR_LEARNING['numbered_list_item'].pattern, re.MULTILINE)
    for match in numbered_matcher.finditer(content):
        extracted = PLAINTEXT_PATTERNS_FOR_LEARNING['numbered_list_item'].extract(match)
        numbered_items.append(extracted)
    
    if bullet_items:
        patterns.append({
            'name': 'plaintext_bullet_lists',
            'content': f"Document contains {len(bullet_items)} bullet list items",
            'metadata': {
                'items': [item.get('content', '') for item in bullet_items[:10]],
                'count': len(bullet_items),
                'markers': list(set(item.get('marker', '') for item in bullet_items))
            },
            'confidence': 0.85
        })
    
    if numbered_items:
        patterns.append({
            'name': 'plaintext_numbered_lists',
            'content': f"Document contains {len(numbered_items)} numbered list items",
            'metadata': {
                'items': [item.get('content', '') for item in numbered_items[:10]],
                'count': len(numbered_items),
                'delimiters': list(set(item.get('delimiter', '') for item in numbered_items))
            },
            'confidence': 0.85
        })
    
    # Process code blocks
    code_blocks = []
    code_matcher = re.compile(PLAINTEXT_PATTERNS_FOR_LEARNING['code_block_pattern'].pattern, re.MULTILINE | re.DOTALL)
    for match in code_matcher.finditer(content):
        extracted = PLAINTEXT_PATTERNS_FOR_LEARNING['code_block_pattern'].extract(match)
        code_blocks.append(extracted)
    
    if code_blocks:
        patterns.append({
            'name': 'plaintext_code_blocks',
            'content': f"Document contains {len(code_blocks)} code blocks",
            'metadata': {
                'count': len(code_blocks),
                'languages': list(set(block.get('language', '') for block in code_blocks if block.get('language'))),
                'styles': list(set(block.get('style', '') for block in code_blocks))
            },
            'confidence': 0.8
        })
    
    # Process metadata tags
    metadata = {}
    metadata_matcher = re.compile(PLAINTEXT_PATTERNS_FOR_LEARNING['metadata_pattern'].pattern, re.MULTILINE)
    for match in metadata_matcher.finditer(content):
        extracted = PLAINTEXT_PATTERNS_FOR_LEARNING['metadata_pattern'].extract(match)
        metadata[extracted.get('key', '')] = extracted.get('value', '')
    
    if metadata:
        patterns.append({
            'name': 'plaintext_metadata_tags',
            'content': f"Document contains metadata tags: {', '.join(metadata.keys())}",
            'metadata': {
                'tags': metadata,
                'count': len(metadata)
            },
            'confidence': 0.9
        })
    
    # Process URLs and emails
    urls = []
    url_matcher = re.compile(PLAINTEXT_PATTERNS_FOR_LEARNING['url_pattern'].pattern)
    for match in url_matcher.finditer(content):
        extracted = PLAINTEXT_PATTERNS_FOR_LEARNING['url_pattern'].extract(match)
        urls.append(extracted.get('url', ''))
    
    emails = []
    email_matcher = re.compile(PLAINTEXT_PATTERNS_FOR_LEARNING['email_pattern'].pattern)
    for match in email_matcher.finditer(content):
        extracted = PLAINTEXT_PATTERNS_FOR_LEARNING['email_pattern'].extract(match)
        emails.append(extracted.get('email', ''))
    
    if urls:
        patterns.append({
            'name': 'plaintext_urls',
            'content': f"Document contains {len(urls)} URLs",
            'metadata': {
                'urls': urls[:10],  # Limit to 10 URLs
                'count': len(urls)
            },
            'confidence': 0.8
        })
    
    if emails:
        patterns.append({
            'name': 'plaintext_emails',
            'content': f"Document contains {len(emails)} email addresses",
            'metadata': {
                'emails': emails[:10],  # Limit to 10 emails
                'count': len(emails)
            },
            'confidence': 0.8
        })
    
    # Process text metrics
    if content:
        # Calculate basic metrics
        words = re.findall(r'\b\w+\b', content)
        sentences = re.findall(r'[^.!?]+[.!?]', content)
        paragraphs = re.split(r'\n\s*\n', content)
        
        word_count = len(words)
        sentence_count = len(sentences)
        paragraph_count = len(paragraphs)
        
        if word_count > 0:
            avg_sentence_length = word_count / max(1, sentence_count)
            avg_paragraph_length = word_count / max(1, paragraph_count)
            
            patterns.append({
                'name': 'plaintext_metrics',
                'content': f"Document has {word_count} words in {sentence_count} sentences and {paragraph_count} paragraphs",
                'metadata': {
                    'word_count': word_count,
                    'sentence_count': sentence_count,
                    'paragraph_count': paragraph_count,
                    'avg_sentence_length': avg_sentence_length,
                    'avg_paragraph_length': avg_paragraph_length
                },
                'confidence': 0.9
            })
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["header", "paragraph", "list_item", "numbered_item", "code_block"],
        "can_be_contained_by": []
    },
    "paragraph": {
        "can_contain": ["url", "email"],
        "can_be_contained_by": ["document"]
    },
    "list_item": {
        "can_contain": ["url", "email"],
        "can_be_contained_by": ["document"]
    }
}

def extract_plaintext_features(node: dict) -> dict:
    """Extract features from plaintext AST nodes."""
    features = {
        "structure": {
            "sections": [],
            "paragraphs": []
        },
        "syntax": {
            "lists": [],
            "code_blocks": [],
            "tables": []
        },
        "semantics": {
            "references": []
        },
        "documentation": {
            "headers": [],
            "metadata": {}
        }
    }
    
    def process_node(node: dict):
        if not isinstance(node, dict):
            return
            
        node_type = node.get("type")
        if node_type == "section":
            features["structure"]["sections"].append(node)
        elif node_type == "paragraph":
            features["structure"]["paragraphs"].append(node)
        elif node_type in ("bullet_list", "numbered_list"):
            features["syntax"]["lists"].append(node)
        elif node_type == "code_block":
            features["syntax"]["code_blocks"].append(node)
        elif node_type == "table":
            features["syntax"]["tables"].append(node)
        elif node_type in ("url", "email", "path"):
            features["semantics"]["references"].append(node)
        elif node_type == "header":
            features["documentation"]["headers"].append(node)
        elif node_type == "metadata":
            features["documentation"]["metadata"][node["key"]] = node["value"]
        
        # Process children
        for child in node.get("children", []):
            process_node(child)
    
    process_node(node)
    return features 