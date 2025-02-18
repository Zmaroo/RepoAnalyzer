"""Custom parser for reStructuredText with enhanced documentation features."""

from typing import Dict, List, Any
from parsers.common_parser_utils import build_parser_output
import re
from utils.logger import log

def parse_rst_code(source_code: str) -> dict:
    """
    Parse RST content as structured documentation while preserving semantic features.
    
    Handles:
    - Document structure (sections, directives)
    - Cross-references and links
    - Directives and roles
    - Code blocks and literals
    - Tables and lists
    """
    features: Dict[str, Any] = {
        "syntax": {
            "sections": [],      # Document sections
            "directives": [],    # RST directives
            "roles": [],         # Inline roles
            "code_blocks": [],   # Code examples
            "literals": []       # Literal blocks
        },
        "structure": {
            "hierarchy": [],     # Section hierarchy
            "references": [],    # Cross-references
            "includes": [],      # Include directives
            "toc": []           # Table of contents
        },
        "semantics": {
            "links": [],        # External links
            "definitions": [],  # Term definitions
            "citations": [],    # Citations
            "substitutions": [] # Substitution definitions
        },
        "documentation": {
            "metadata": {},     # Document metadata
            "comments": [],     # RST comments
            "admonitions": [],  # Warning, note, etc.
            "fields": []        # Field lists
        }
    }
    
    # Enhanced patterns for RST parsing
    patterns = {
        'section': re.compile(r'^([-=`:\'"~^_*+#])\1{3,}$'),
        'directive': re.compile(r'\.\. (\w+)::\s*(.*)$'),
        'role': re.compile(r':(\w+):`([^`]+)`'),
        'comment': re.compile(r'\.\. (.*)$'),
        'field': re.compile(r':([^:]+):\s*(.*)$'),
        'link': re.compile(r'`([^`]+)`_'),
        'reference': re.compile(r':ref:`([^`]+)`'),
        'code_block': re.compile(r'\.\. code-block::\s*(\w+)')
    }
    
    def get_section_level(char: str) -> int:
        """Determine section level based on underline character."""
        levels = {
            '=': 1, '-': 2, '~': 3, 
            '^': 4, '"': 5, '+': 6
        }
        return levels.get(char, 99)  # High number for unknown chars
    
    def process_directive(name: str, content: str, line_number: int) -> Dict:
        """Process an RST directive and its content."""
        directive_data = {
            "type": "directive",
            "name": name,
            "content": content,
            "line": line_number
        }
        
        features["syntax"]["directives"].append(directive_data)
        
        # Handle special directives
        if name == 'include':
            features["structure"]["includes"].append({
                "path": content.strip(),
                "line": line_number
            })
        elif name == 'code-block':
            features["syntax"]["code_blocks"].append({
                "language": content.strip(),
                "line": line_number
            })
        elif name in ['note', 'warning', 'important', 'tip', 'caution']:
            features["documentation"]["admonitions"].append({
                "type": name,
                "content": content,
                "line": line_number
            })
        
        return directive_data
    
    try:
        lines = source_code.splitlines()
        current_section = None
        current_content = []
        section_stack = []
        
        for i, line in enumerate(lines):
            line_number = i + 1
            
            # Check for section underlines
            if patterns['section'].match(line) and current_content:
                section_title = current_content[-1]
                section_level = get_section_level(line[0])
                
                section_data = {
                    "title": section_title,
                    "level": section_level,
                    "line": line_number - 1
                }
                
                features["syntax"]["sections"].append(section_data)
                
                # Update hierarchy
                while (section_stack and 
                       section_stack[-1]["level"] >= section_level):
                    section_stack.pop()
                
                if section_stack:
                    section_data["parent"] = section_stack[-1]["title"]
                
                section_stack.append(section_data)
                features["structure"]["hierarchy"].append(section_data)
                current_content = []
                continue
            
            # Check for directives
            directive_match = patterns['directive'].match(line)
            if directive_match:
                name, content = directive_match.groups()
                process_directive(name, content, line_number)
                continue
            
            # Check for roles
            for role_match in patterns['role'].finditer(line):
                role_type, content = role_match.groups()
                features["syntax"]["roles"].append({
                    "type": role_type,
                    "content": content,
                    "line": line_number
                })
            
            # Check for comments
            comment_match = patterns['comment'].match(line)
            if comment_match and not line.startswith('.. '):
                features["documentation"]["comments"].append({
                    "content": comment_match.group(1),
                    "line": line_number
                })
                continue
            
            # Check for field lists
            field_match = patterns['field'].match(line)
            if field_match:
                name, content = field_match.groups()
                features["documentation"]["fields"].append({
                    "name": name,
                    "content": content,
                    "line": line_number
                })
                continue
            
            # Check for links and references
            for link_match in patterns['link'].finditer(line):
                features["semantics"]["links"].append({
                    "text": link_match.group(1),
                    "line": line_number
                })
            
            for ref_match in patterns['reference'].finditer(line):
                features["structure"]["references"].append({
                    "target": ref_match.group(1),
                    "line": line_number
                })
            
            # Collect content for section processing
            if line.strip():
                current_content.append(line)
        
        # Build AST
        ast = {
            "type": "rst_document",
            "sections": features["syntax"]["sections"],
            "directives": features["syntax"]["directives"],
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
            len(features["syntax"]["directives"]) +
            len(features["structure"]["references"])
        )
        
        return build_parser_output(
            source_code=source_code,
            language="rst",
            ast=ast,
            features=features,
            total_lines=len(lines),
            documentation=documentation,
            complexity=complexity
        )
        
    except Exception as e:
        log(f"Error in RST parser: {e}", level="error")
        return build_parser_output(
            source_code=source_code,
            language="rst",
            ast={"type": "error", "message": str(e)},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        ) 