"""Custom parser for Markdown with enhanced documentation features."""

from typing import Dict, List, Any
from parsers.common_parser_utils import build_parser_output
import re

def parse_markdown_code(source_code: str) -> dict:
    """
    Parse Markdown content as structured code while preserving documentation features.
    
    Generates an AST that captures both document structure and semantic content:
    - Headers become namespace/module-like structures
    - Code blocks are parsed as embedded code
    - Lists become structured data
    - Links become references
    - Metadata (frontmatter) becomes module-level attributes
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    
    # Track document structure
    current_section = None
    sections: List[Dict] = []
    features: Dict[str, Any] = {
        "syntax": {
            "headers": [],
            "code_blocks": [],
            "emphasis": []
        },
        "structure": {
            "sections": [],
            "lists": [],
            "tables": []
        },
        "semantics": {
            "links": [],
            "references": [],
            "definitions": []
        },
        "documentation": {
            "metadata": {},
            "comments": [],
            "blockquotes": []
        }
    }
    
    # Regex patterns for Markdown elements
    patterns = {
        'header': re.compile(r'^(#{1,6})\s+(.+)$'),
        'code_block': re.compile(r'^```(\w*)$'),
        'list_item': re.compile(r'^(\s*)[*+-]\s+(.+)$'),
        'numbered_list': re.compile(r'^(\s*)\d+\.\s+(.+)$'),
        'link': re.compile(r'\[([^\]]+)\]\(([^)]+)\)'),
        'emphasis': re.compile(r'[*_]{1,2}([^*_]+)[*_]{1,2}'),
        'blockquote': re.compile(r'^\s*>\s*(.+)$'),
        'table_header': re.compile(r'^\|(.+)\|$'),
        'frontmatter_delimiter': re.compile(r'^---\s*$')
    }
    
    def process_code_block(start_idx: int, language: str) -> Dict:
        """Process a code block and return its content and metadata."""
        code_content = []
        end_idx = start_idx + 1
        
        while end_idx < total_lines:
            if lines[end_idx].strip() == '```':
                break
            code_content.append(lines[end_idx])
            end_idx += 1
            
        return {
            "type": "code_block",
            "language": language,
            "content": "\n".join(code_content),
            "start_line": start_idx,
            "end_line": end_idx,
            "start_point": [start_idx, 0],
            "end_point": [end_idx, 3]
        }
    
    def process_list(start_idx: int, indent_level: int) -> Dict:
        """Process a list structure and return its items and metadata."""
        items = []
        current_idx = start_idx
        
        while current_idx < total_lines:
            line = lines[current_idx]
            list_match = (patterns['list_item'].match(line) or 
                         patterns['numbered_list'].match(line))
            
            if not list_match or len(list_match.group(1)) != indent_level:
                break
                
            items.append({
                "content": list_match.group(2),
                "line": current_idx + 1
            })
            current_idx += 1
            
        return {
            "type": "list",
            "items": items,
            "indent_level": indent_level,
            "start_line": start_idx,
            "end_line": current_idx - 1
        }
    
    # Process frontmatter if present
    i = 0
    if i < total_lines and patterns['frontmatter_delimiter'].match(lines[i]):
        frontmatter = []
        i += 1
        while i < total_lines and not patterns['frontmatter_delimiter'].match(lines[i]):
            frontmatter.append(lines[i])
            i += 1
        if i < total_lines:  # Skip closing delimiter
            i += 1
        features["documentation"]["metadata"]["frontmatter"] = "\n".join(frontmatter)
    
    # Main parsing loop
    while i < total_lines:
        line = lines[i]
        
        # Process headers
        header_match = patterns['header'].match(line)
        if header_match:
            level = len(header_match.group(1))
            content = header_match.group(2)
            header_node = {
                "type": "header",
                "level": level,
                "content": content,
                "line": i + 1,
                "children": []
            }
            features["syntax"]["headers"].append(header_node)
            current_section = header_node
            sections.append(current_section)
            i += 1
            continue
        
        # Process code blocks
        code_match = patterns['code_block'].match(line)
        if code_match:
            language = code_match.group(1)
            code_block = process_code_block(i, language)
            features["syntax"]["code_blocks"].append(code_block)
            if current_section:
                current_section["children"].append(code_block)
            i = code_block["end_line"] + 1
            continue
        
        # Process lists
        list_match = patterns['list_item'].match(line)
        if list_match:
            indent_level = len(list_match.group(1))
            list_struct = process_list(i, indent_level)
            features["structure"]["lists"].append(list_struct)
            if current_section:
                current_section["children"].append(list_struct)
            i = list_struct["end_line"] + 1
            continue
        
        # Process blockquotes
        blockquote_match = patterns['blockquote'].match(line)
        if blockquote_match:
            features["documentation"]["blockquotes"].append({
                "content": blockquote_match.group(1),
                "line": i + 1
            })
            i += 1
            continue
        
        # Process inline elements
        link_matches = patterns['link'].finditer(line)
        for match in link_matches:
            features["semantics"]["links"].append({
                "text": match.group(1),
                "url": match.group(2),
                "line": i + 1
            })
        
        emphasis_matches = patterns['emphasis'].finditer(line)
        for match in emphasis_matches:
            features["syntax"]["emphasis"].append({
                "content": match.group(1),
                "line": i + 1
            })
        
        i += 1
    
    # Build the AST
    ast = {
        "type": "document",
        "children": sections,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }
    
    return build_parser_output(
        source_code=source_code,
        language="markdown",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=source_code,  # Original content preserved as documentation
        complexity=len(sections)  # Complexity based on document structure
    ) 