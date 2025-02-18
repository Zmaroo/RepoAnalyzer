"""Custom parser for AsciiDoc with enhanced documentation features."""

from typing import Dict, List, Any
from parsers.common_parser_utils import build_parser_output
import re
from utils.logger import log

def parse_asciidoc_code(source_code: str) -> dict:
    """
    Parse AsciiDoc content as structured documentation while preserving semantic features.
    
    Handles:
    - Document structure (sections, blocks)
    - Attributes and macros
    - Include directives
    - Cross-references
    - Tables and lists
    """
    features: Dict[str, Any] = {
        "syntax": {
            "sections": [],     # Document sections
            "blocks": [],       # Content blocks
            "macros": [],       # AsciiDoc macros
            "attributes": [],   # Document attributes
            "lists": []         # List structures
        },
        "structure": {
            "hierarchy": [],    # Section hierarchy
            "includes": [],     # Include directives
            "references": [],   # Cross-references
            "anchors": []       # Named anchors
        },
        "semantics": {
            "links": [],        # External links
            "callouts": [],     # Code callouts
            "footnotes": [],    # Footnote references
            "terms": []         # Glossary terms
        },
        "documentation": {
            "metadata": {},     # Document header
            "comments": [],     # AsciiDoc comments
            "admonitions": [],  # NOTE, TIP, etc.
            "annotations": []   # Inline annotations
        }
    }
    
    # Enhanced patterns for AsciiDoc parsing
    patterns = {
        'header': re.compile(r'^=\s+(.+)$'),
        'section': re.compile(r'^(=+)\s+(.+)$'),
        'attribute': re.compile(r'^:([^:]+):\s*(.*)$'),
        'block': re.compile(r'^(----|\[.*?\])\s*$'),
        'include': re.compile(r'^include::([^[\]]+)(?:\[(.*?)\])?$'),
        'macro': re.compile(r'([a-z]+)::([^[\]]+)(?:\[(.*?)\])?'),
        'anchor': re.compile(r'^\[\[([^\]]+)\]\]$'),
        'admonition': re.compile(r'^(NOTE|TIP|IMPORTANT|WARNING|CAUTION):\s+(.+)$'),
        'comment': re.compile(r'^//\s*(.*)$'),
        'callout': re.compile(r'<(\d+)>')
    }
    
    def process_section(title: str, level: int, line_number: int) -> Dict:
        """Process a section and determine its hierarchy."""
        section_data = {
            "title": title,
            "level": level,
            "line": line_number
        }
        
        features["syntax"]["sections"].append(section_data)
        
        # Update hierarchy
        while (section_stack and 
               section_stack[-1]["level"] >= level):
            section_stack.pop()
        
        if section_stack:
            section_data["parent"] = section_stack[-1]["title"]
        
        section_stack.append(section_data)
        features["structure"]["hierarchy"].append(section_data)
        
        return section_data
    
    def process_block(block_type: str, content: str, line_number: int) -> Dict:
        """Process a block and its attributes."""
        block_data = {
            "type": block_type,
            "content": content,
            "line": line_number
        }
        
        features["syntax"]["blocks"].append(block_data)
        
        # Handle special blocks
        if block_type == "source":
            features["syntax"]["blocks"].append({
                "type": "code",
                "language": content.split(",")[0] if "," in content else "",
                "line": line_number
            })
        elif block_type in ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"]:
            features["documentation"]["admonitions"].append({
                "type": block_type.lower(),
                "content": content,
                "line": line_number
            })
        
        return block_data
    
    try:
        lines = source_code.splitlines()
        section_stack = []
        in_block = False
        current_block = None
        header_processed = False
        
        for i, line in enumerate(lines):
            line_number = i + 1
            
            # Process document header
            if not header_processed:
                header_match = patterns['header'].match(line)
                if header_match:
                    features["documentation"]["metadata"]["title"] = header_match.group(1)
                    header_processed = True
                    continue
            
            # Process sections
            section_match = patterns['section'].match(line)
            if section_match and not in_block:
                level = len(section_match.group(1))
                title = section_match.group(2)
                process_section(title, level, line_number)
                continue
            
            # Process attributes
            attr_match = patterns['attribute'].match(line)
            if attr_match and not in_block:
                name, value = attr_match.groups()
                features["syntax"]["attributes"].append({
                    "name": name,
                    "value": value,
                    "line": line_number
                })
                continue
            
            # Process blocks
            block_match = patterns['block'].match(line)
            if block_match:
                if not in_block:
                    in_block = True
                    current_block = {
                        "type": block_match.group(1),
                        "content": [],
                        "start": line_number
                    }
                else:
                    if current_block:
                        current_block["end"] = line_number
                        process_block(
                            current_block["type"],
                            "\n".join(current_block["content"]),
                            current_block["start"]
                        )
                    in_block = False
                    current_block = None
                continue
            
            # Collect block content
            if in_block and current_block:
                current_block["content"].append(line)
                continue
            
            # Process includes
            include_match = patterns['include'].match(line)
            if include_match:
                path, options = include_match.groups()
                features["structure"]["includes"].append({
                    "path": path,
                    "options": options,
                    "line": line_number
                })
                continue
            
            # Process macros
            for macro_match in patterns['macro'].finditer(line):
                name, target, attrs = macro_match.groups()
                features["syntax"]["macros"].append({
                    "name": name,
                    "target": target,
                    "attributes": attrs,
                    "line": line_number
                })
            
            # Process anchors
            anchor_match = patterns['anchor'].match(line)
            if anchor_match:
                features["structure"]["anchors"].append({
                    "id": anchor_match.group(1),
                    "line": line_number
                })
                continue
            
            # Process comments
            comment_match = patterns['comment'].match(line)
            if comment_match:
                features["documentation"]["comments"].append({
                    "content": comment_match.group(1),
                    "line": line_number
                })
                continue
            
            # Process callouts
            for callout_match in patterns['callout'].finditer(line):
                features["semantics"]["callouts"].append({
                    "number": callout_match.group(1),
                    "line": line_number
                })
        
        # Build AST
        ast = {
            "type": "asciidoc_document",
            "metadata": features["documentation"]["metadata"],
            "sections": features["syntax"]["sections"],
            "blocks": features["syntax"]["blocks"],
            "start_point": [0, 0],
            "end_point": [len(lines) - 1, len(lines[-1]) if lines else 0],
            "start_byte": 0,
            "end_byte": len(source_code)
        }
        
        # Extract documentation
        documentation = "\n".join(
            comment["content"] for comment in features["documentation"]["comments"]
        )
        
        # Calculate complexity
        complexity = (
            len(features["syntax"]["sections"]) +
            len(features["syntax"]["blocks"]) +
            len(features["syntax"]["macros"])
        )
        
        return build_parser_output(
            source_code=source_code,
            language="asciidoc",
            ast=ast,
            features=features,
            total_lines=len(lines),
            documentation=documentation,
            complexity=complexity
        )
        
    except Exception as e:
        log(f"Error in AsciiDoc parser: {e}", level="error")
        return build_parser_output(
            source_code=source_code,
            language="asciidoc",
            ast={"type": "error", "message": str(e)},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        ) 