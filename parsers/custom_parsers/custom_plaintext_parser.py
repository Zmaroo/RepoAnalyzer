"""
Enhanced Plain Text parser.

Provides richer structure detection and documentation parsing while maintaining
compatibility with our standard pattern categories.
"""

from typing import List, Dict, Any
from parsers.common_parser_utils import build_parser_output
import re

def parse_plaintext_code(source_code: str) -> dict:
    """
    Parse plain text with enhanced structure detection.
    
    Features:
    - Section detection (headers, paragraphs)
    - List recognition (bullet points, numbered lists)
    - Code-like block detection
    - Documentation markers
    - Table-like structure detection
    - Reference and link detection
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    
    features: Dict[str, Any] = {
        "syntax": {
            "indented_blocks": [],  # Code-like structures
            "tables": [],           # Table-like structures
            "lists": []            # Structured lists
        },
        "structure": {
            "sections": [],        # Document sections
            "paragraphs": [],      # Text paragraphs
            "references": []       # Cross-references
        },
        "semantics": {
            "urls": [],           # URL detection
            "emails": [],         # Email addresses
            "paths": []           # File paths
        },
        "documentation": {
            "comments": [],       # Comment-like lines
            "headers": [],        # Section headers
            "metadata": {}        # Document metadata
        }
    }
    
    # Enhanced pattern matching
    patterns = {
        'header': re.compile(r'^(={2,}|-{2,}|\*{2,}|#{1,6})\s*(.+?)(?:\s*\1)?$'),
        'bullet_list': re.compile(r'^\s*[-*+•]\s+(.+)$'),
        'numbered_list': re.compile(r'^\s*\d+[.)]\s+(.+)$'),
        'code_block': re.compile(r'^(?:\s{4,}|\t+)(.+)$'),
        'table_row': re.compile(r'^\s*\|.*\|\s*$|^\s*[+\-]+$'),
        'url': re.compile(r'https?://\S+|www\.\S+'),
        'email': re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w+\b'),
        'path': re.compile(r'(?:^|[\s(])(?:/[\w.-]+)+|\b[\w.-]+/[\w.-/]+'),
        'metadata': re.compile(r'^@(\w+):\s*(.+)$')
    }
    
    def process_section(lines: List[str], start_line: int, header: str = None) -> Dict:
        """Process a section of text with enhanced structure detection."""
        section_data = {
            "type": "section",
            "header": header,
            "content": [],
            "start_line": start_line,
            "end_line": start_line + len(lines) - 1,
            "children": []
        }
        
        current_list = None
        current_code_block = None
        current_table = None
        current_paragraph = []
        
        for i, line in enumerate(lines):
            line_number = start_line + i
            stripped = line.strip()
            
            # Check for metadata
            metadata_match = patterns['metadata'].match(line)
            if metadata_match:
                key, value = metadata_match.groups()
                features["documentation"]["metadata"][key] = value
                continue
            
            # Process lists
            list_match = patterns['bullet_list'].match(line) or patterns['numbered_list'].match(line)
            if list_match:
                if current_paragraph:
                    section_data["children"].append({
                        "type": "paragraph",
                        "content": "\n".join(current_paragraph),
                        "line": line_number - len(current_paragraph)
                    })
                    current_paragraph = []
                
                if not current_list:
                    current_list = {
                        "type": "list",
                        "items": [],
                        "start_line": line_number
                    }
                
                current_list["items"].append({
                    "content": list_match.group(1),
                    "line": line_number
                })
                continue
            elif current_list:
                features["syntax"]["lists"].append(current_list)
                section_data["children"].append(current_list)
                current_list = None
            
            # Process code blocks
            code_match = patterns['code_block'].match(line)
            if code_match:
                if not current_code_block:
                    current_code_block = {
                        "type": "code_block",
                        "content": [],
                        "start_line": line_number
                    }
                current_code_block["content"].append(code_match.group(1))
                continue
            elif current_code_block:
                features["syntax"]["indented_blocks"].append(current_code_block)
                section_data["children"].append(current_code_block)
                current_code_block = None
            
            # Process tables
            if patterns['table_row'].match(line):
                if not current_table:
                    current_table = {
                        "type": "table",
                        "rows": [],
                        "start_line": line_number
                    }
                current_table["rows"].append(line)
                continue
            elif current_table:
                features["syntax"]["tables"].append(current_table)
                section_data["children"].append(current_table)
                current_table = None
            
            # Process URLs, emails, and paths
            for url in patterns['url'].finditer(line):
                features["semantics"]["urls"].append({
                    "url": url.group(),
                    "line": line_number
                })
            
            for email in patterns['email'].finditer(line):
                features["semantics"]["emails"].append({
                    "email": email.group(),
                    "line": line_number
                })
            
            for path in patterns['path'].finditer(line):
                features["semantics"]["paths"].append({
                    "path": path.group().strip(),
                    "line": line_number
                })
            
            # Add to current paragraph
            if stripped:
                current_paragraph.append(line)
            elif current_paragraph:
                section_data["children"].append({
                    "type": "paragraph",
                    "content": "\n".join(current_paragraph),
                    "line": line_number - len(current_paragraph)
                })
                current_paragraph = []
        
        # Handle any remaining structures
        if current_paragraph:
            section_data["children"].append({
                "type": "paragraph",
                "content": "\n".join(current_paragraph),
                "line": start_line + len(lines) - len(current_paragraph)
            })
        
        features["structure"]["sections"].append(section_data)
        return section_data
    
    # Process the file
    current_section_lines = []
    current_section_start = 0
    current_header = None
    
    for i, line in enumerate(lines):
        header_match = patterns['header'].match(line)
        
        if header_match:
            # Process previous section
            if current_section_lines:
                children.append(process_section(
                    current_section_lines,
                    current_section_start,
                    current_header
                ))
            
            current_section_lines = []
            current_section_start = i + 1
            current_header = header_match.group(2)
            features["documentation"]["headers"].append({
                "content": current_header,
                "level": len(header_match.group(1)),
                "line": i + 1
            })
        else:
            current_section_lines.append(line)
    
    # Process final section
    if current_section_lines:
        children.append(process_section(
            current_section_lines,
            current_section_start,
            current_header
        ))
    
    # Build AST
    ast = {
        "type": "document",
        "children": children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }
    
    # Extract documentation
    documentation = "\n".join(
        header["content"] for header in features["documentation"]["headers"]
    )
    
    return build_parser_output(
        source_code=source_code,
        language="plaintext",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=len(features["structure"]["sections"])
    )