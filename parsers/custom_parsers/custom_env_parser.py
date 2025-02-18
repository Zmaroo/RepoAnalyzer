"""
Custom .env file parser.

This parser processes .env files by extracting key=value pairs.
Comments (lines starting with #) are skipped (or can be used as documentation).
"""

from parsers.common_parser_utils import extract_features_from_ast, build_parser_output
import re

def parse_env_code(source_code: str) -> dict:
    """
    Parse environment files (.env) to generate an AST aligned with PATTERN_CATEGORIES.
    
    Maps env constructs to standard categories:
    - semantics: variable assignments (variable)
    - structure: export statements (export)
    - documentation: comments (comment), multi-line values (docstring)
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    
    # Regex patterns for env file parsing
    export_pattern = re.compile(r'^export\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')
    variable_pattern = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')
    comment_pattern = re.compile(r'^[\s]*[#;](.*)$')
    
    def process_value(value: str, line_num: int) -> tuple:
        """Process a value that might be multi-line or quoted."""
        if value.startswith('"') or value.startswith("'"):
            quote = value[0]
            if value.endswith(quote) and len(value) > 1:
                return value[1:-1], "string"
        elif value.startswith('`') and value.endswith('`'):
            # Multi-line value
            return {
                "type": "documentation",
                "category": "docstring",
                "content": value[1:-1],
                "line": line_num
            }, "multi-line"
        return value, "raw"

    current_line = 0
    while current_line < total_lines:
        line = lines[current_line].strip()
        
        # Skip empty lines
        if not line:
            current_line += 1
            continue
            
        # Check for comments
        comment_match = comment_pattern.match(line)
        if comment_match:
            children.append({
                "type": "documentation",
                "category": "comment",
                "content": comment_match.group(1).strip(),
                "line": current_line + 1
            })
            current_line += 1
            continue
            
        # Check for export statements
        export_match = export_pattern.match(line)
        if export_match:
            name, raw_value = export_match.groups()
            value, value_type = process_value(raw_value, current_line + 1)
            
            if value_type == "multi-line":
                children.append(value)  # Add multi-line docstring node
                children.append({
                    "type": "structure",
                    "category": "export",
                    "name": name,
                    "value": value["content"],
                    "line": current_line + 1
                })
            else:
                children.append({
                    "type": "structure",
                    "category": "export",
                    "name": name,
                    "value": value,
                    "line": current_line + 1
                })
            current_line += 1
            continue
            
        # Check for variable assignments
        var_match = variable_pattern.match(line)
        if var_match:
            name, raw_value = var_match.groups()
            value, value_type = process_value(raw_value, current_line + 1)
            
            if value_type == "multi-line":
                children.append(value)  # Add multi-line docstring node
                children.append({
                    "type": "semantics",
                    "category": "variable",
                    "name": name,
                    "value": value["content"],
                    "line": current_line + 1
                })
            else:
                children.append({
                    "type": "semantics",
                    "category": "variable",
                    "name": name,
                    "value": value,
                    "line": current_line + 1
                })
            
        current_line += 1
    
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
        "semantics": {
            "variable": [node for node in children 
                        if node["type"] == "semantics" and node["category"] == "variable"]
        },
        "structure": {
            "export": [node for node in children 
                      if node["type"] == "structure" and node["category"] == "export"]
        },
        "documentation": {
            "comment": [node for node in children 
                       if node["type"] == "documentation" and node["category"] == "comment"],
            "docstring": [node for node in children 
                         if node["type"] == "documentation" and node["category"] == "docstring"]
        }
    }

    # Extract documentation from comments and multi-line values
    documentation = "\n".join(
        node["content"] for node in children
        if node["type"] == "documentation"
    )

    return build_parser_output(
        source_code=source_code,
        language="env",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    )