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
    Parse an EditorConfig file.

    Returns a dictionary with:
      - "content": the raw source code,
      - "language": "editorconfig",
      - "ast_data": a custom AST with sections and properties,
      - "ast_features": features extracted from the AST,
      - "lines_of_code": the total number of lines,
      - "documentation": any leading comment as documentation (if present),
      - "complexity": a placeholder value.
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    
    # Attempt to extract a top-level documentation comment.
    documentation = ""
    if re.match(r'^\s*#', source_code):
        # Extract the documentation comment from the file
        documentation = source_code.splitlines()[0].strip()
    
    ast_children = []
    current_section = {}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            # Start a new section.
            # If there is an existing section, add it to the children.
            if current_section.get("name"):
                ast_children.append(current_section)
            section_name = stripped[1:-1].strip()
            current_section = {
                "type": "section",
                "name": section_name,
                "children": []
            }
        elif "=" in line:
            # A key-value property line.
            key, value = map(str.strip, line.split("=", 1))
            property_node = {
                "type": "property",
                "key": key,
                "value": value,
                "text": stripped
            }
            # Append the property to the current section.
            current_section.setdefault("children", []).append(property_node)
        else:
            # Could be a stray comment or free-form text.
            pass

    if current_section.get("name"):
        ast_children.append(current_section)

    # Insert the documentation node at the beginning if documentation exists.
    if documentation:
        ast_children.insert(0, {"type": "documentation", "text": documentation})
    
    ast = {
        "type": "editorconfig",
        "children": ast_children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }
    features = extract_features_from_ast(ast)
    return build_parser_output(
        source_code=source_code,
        language="editorconfig",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    )