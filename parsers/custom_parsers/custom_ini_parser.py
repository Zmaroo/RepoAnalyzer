"""Custom parser for INI/Properties files with enhanced documentation features."""

from typing import Dict, List, Any
from parsers.common_parser_utils import build_parser_output
import configparser
import re
from utils.logger import log

def parse_ini_code(source_code: str) -> dict:
    """
    Parse INI/Properties content as structured code while preserving documentation.
    
    Handles:
    - Section-based structure
    - Key-value pairs
    - Comments and documentation
    - Include directives
    - Environment variables
    - Cross-references
    """
    features: Dict[str, Any] = {
        "syntax": {
            "sections": [],     # INI sections
            "properties": [],   # Key-value pairs
            "includes": [],     # Include directives
            "variables": []     # Variable references
        },
        "structure": {
            "root": None,       # Global section
            "hierarchy": [],    # Section hierarchy
            "references": []    # Cross-references
        },
        "semantics": {
            "definitions": [], # Value definitions
            "environment": [], # Environment variables
            "paths": []       # File paths
        },
        "documentation": {
            "comments": [],    # Regular comments
            "metadata": {},    # Section metadata
            "descriptions": [] # Property descriptions
        }
    }
    
    # Enhanced patterns for INI/Properties parsing
    patterns = {
        'section': re.compile(r'^\s*\[(.*?)\]\s*(?:#\s*(.*))?$'),
        'property': re.compile(r'^\s*([\w.-]+)\s*[=:]\s*(.+?)(?:\s*[#;]\s*(.*))?$'),
        'comment': re.compile(r'^\s*[#;]\s*(.+)$'),
        'include': re.compile(r'^\s*[@!]include\s+(.+)$'),
        'env_var': re.compile(r'\${([^}]+)}'),
        'reference': re.compile(r'\${([\w.-]+)}')
    }
    
    def process_section(name: str, properties: Dict[str, str], 
                       comments: List[str], line_number: int) -> Dict:
        """Process a section and its properties."""
        section_data = {
            "type": "section",
            "name": name,
            "line": line_number,
            "properties": [],
            "comments": comments
        }
        
        features["syntax"]["sections"].append(section_data)
        
        # Add to hierarchy
        if name != "DEFAULT":
            features["structure"]["hierarchy"].append({
                "name": name,
                "line": line_number
            })
        
        # Process properties
        for key, value in properties.items():
            prop_data = {
                "key": key,
                "value": value,
                "section": name
            }
            
            # Check for environment variables
            env_vars = patterns['env_var'].findall(value)
            for var in env_vars:
                features["semantics"]["environment"].append({
                    "variable": var,
                    "section": name,
                    "key": key
                })
            
            # Check for references
            refs = patterns['reference'].findall(value)
            for ref in refs:
                features["structure"]["references"].append({
                    "from": f"{name}.{key}",
                    "to": ref
                })
            
            # Check for paths
            if any(ext in value for ext in ['.txt', '.ini', '.conf', '.properties']):
                features["semantics"]["paths"].append({
                    "path": value,
                    "section": name,
                    "key": key
                })
            
            section_data["properties"].append(prop_data)
            features["syntax"]["properties"].append(prop_data)
        
        return section_data
    
    try:
        lines = source_code.splitlines()
        current_section = None
        current_comments = []
        sections = {}
        section_comments = {}
        
        # First pass: collect comments and sections
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check for comments
            comment_match = patterns['comment'].match(line)
            if comment_match:
                comment_content = comment_match.group(1)
                current_comments.append({
                    "content": comment_content,
                    "line": i + 1
                })
                features["documentation"]["comments"].append({
                    "content": comment_content,
                    "line": i + 1
                })
                continue
            
            # Check for include directives
            include_match = patterns['include'].match(line)
            if include_match:
                features["syntax"]["includes"].append({
                    "path": include_match.group(1),
                    "line": i + 1
                })
                continue
            
            # Check for sections
            section_match = patterns['section'].match(line)
            if section_match:
                section_name = section_match.group(1)
                section_desc = section_match.group(2)
                
                if section_desc:
                    features["documentation"]["descriptions"].append({
                        "section": section_name,
                        "content": section_desc,
                        "line": i + 1
                    })
                
                if current_comments:
                    section_comments[section_name] = current_comments
                    current_comments = []
                
                current_section = section_name
                sections[current_section] = {}
                continue
            
            # Check for properties
            property_match = patterns['property'].match(line)
            if property_match:
                key = property_match.group(1)
                value = property_match.group(2)
                prop_comment = property_match.group(3)
                
                if current_section is None:
                    current_section = "DEFAULT"
                    sections[current_section] = {}
                
                sections[current_section][key] = value
                
                if prop_comment:
                    features["documentation"]["descriptions"].append({
                        "section": current_section,
                        "key": key,
                        "content": prop_comment,
                        "line": i + 1
                    })
                
                if current_comments:
                    features["documentation"]["descriptions"].append({
                        "section": current_section,
                        "key": key,
                        "content": "\n".join(c["content"] for c in current_comments),
                        "line": i + 1
                    })
                    current_comments = []
        
        # Process sections and build AST
        ast_children = []
        for section_name, properties in sections.items():
            section_data = process_section(
                section_name,
                properties,
                section_comments.get(section_name, []),
                next((i for i, line in enumerate(lines) 
                      if patterns['section'].match(line) 
                      and patterns['section'].match(line).group(1) == section_name), 0)
            )
            ast_children.append(section_data)
        
        # Build the AST
        ast = {
            "type": "ini_document",
            "children": ast_children,
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
            len(features["syntax"]["properties"]) +
            len(features["structure"]["references"])
        )
        
        return build_parser_output(
            source_code=source_code,
            language="ini",
            ast=ast,
            features=features,
            total_lines=len(lines),
            documentation=documentation,
            complexity=complexity
        )
        
    except Exception as e:
        log(f"Error in INI parser: {e}", level="error")
        return build_parser_output(
            source_code=source_code,
            language="ini",
            ast={"type": "error", "message": str(e)},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        ) 