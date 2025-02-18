"""
Custom EditorConfig parser.

This module implements a lightweight parser for EditorConfig files.
It extracts section headers (e.g. [*] or [*.py]) and
key-value property lines beneath each section.
"""

from parsers.common_parser_utils import extract_features_from_ast, build_parser_output
import re

def parse_editorconfig_code(source_code: str) -> dict:
    """
    Parse EditorConfig files to generate an AST aligned with PATTERN_CATEGORIES.
    
    Maps EditorConfig constructs to standard categories:
    - structure: sections (namespace)
    - syntax: section headers (class)
    - semantics: properties (variable)
    - documentation: comments (comment)
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    
    # Regex patterns for EditorConfig parsing
    section_pattern = re.compile(r'^\[(.*)\]$')
    property_pattern = re.compile(r'^([^=]+)=(.*)$')
    comment_pattern = re.compile(r'^[#;](.*)$')
    
    current_section = None
    current_section_properties = []
    
    def flush_section():
        """Process and add the current section to children."""
        nonlocal current_section, current_section_properties
        if current_section:
            # Add the section header as a class
            children.append({
                "type": "syntax",
                "category": "class",
                "name": current_section["glob"],
                "line": current_section["line"]
            })
            
            # Add the section properties as a namespace
            if current_section_properties:
                children.append({
                    "type": "structure",
                    "category": "namespace",
                    "name": current_section["glob"],
                    "children": current_section_properties,
                    "start_line": current_section["line"],
                    "end_line": current_section_properties[-1]["line"]
                })
            
            current_section = None
            current_section_properties = []

    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Check for comments
        comment_match = comment_pattern.match(line)
        if comment_match:
            children.append({
                "type": "documentation",
                "category": "comment",
                "content": comment_match.group(1).strip(),
                "line": i + 1
            })
            continue
            
        # Check for section headers
        section_match = section_pattern.match(line)
        if section_match:
            # Flush previous section
            flush_section()
            
            # Start new section
            current_section = {
                "glob": section_match.group(1).strip(),
                "line": i + 1
            }
            continue
            
        # Check for properties
        property_match = property_pattern.match(line)
        if property_match and current_section:
            key = property_match.group(1).strip()
            value = property_match.group(2).strip()
            
            current_section_properties.append({
                "type": "semantics",
                "category": "variable",
                "name": key,
                "value": value,
                "line": i + 1
            })
    
    # Flush final section
    flush_section()
    
    # Build the AST root
    ast = {
        "type": "module",
        "category": "structure",
        "children": children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }

    # Extract features based on pattern categories
    features = {
        "syntax": {
            "class": [node for node in children 
                     if node["type"] == "syntax" and node["category"] == "class"]
        },
        "structure": {
            "namespace": [node for node in children 
                         if node["type"] == "structure" and node["category"] == "namespace"]
        },
        "semantics": {
            "variable": [node for node in ast["children"] 
                        if node["type"] == "semantics" and node["category"] == "variable"]
        },
        "documentation": {
            "comment": [node for node in children 
                       if node["type"] == "documentation" and node["category"] == "comment"]
        }
    }

    # Extract documentation from comments
    documentation = "\n".join(
        node["content"] for node in children
        if node["type"] == "documentation" and node["category"] == "comment"
    )

    return build_parser_output(
        source_code=source_code,
        language="editorconfig",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    )