"""
Custom Nim parser.

This parser applies simple regex patterns to extract key elements from Nim source files,
for example, procedure (proc) and type definitions.
"""

from parsers.common_parser_utils import extract_features_from_ast, build_parser_output

import re

def parse_nim_code(source_code: str) -> dict:
    """
    Parse a Nim file.

    Returns a dictionary with:
      - "content": the raw source code,
      - "language": "nim",
      - "ast_data": an AST with nodes for 'proc' and 'type' definitions,
      - "ast_features": features extracted from the AST,
      - "lines_of_code": number of lines,
      - "documentation": any leading comment,
      - "complexity": a placeholder value.
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    documentation = ""
    if lines and (lines[0].startswith("#") or lines[0].startswith(";")):
        documentation = lines[0].strip()

    proc_regex = re.compile(r'^\s*proc\s+([A-Za-z0-9_]+)')
    type_regex = re.compile(r'^\s*type\s+([A-Za-z0-9_]+)')
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        proc_match = proc_regex.match(line)
        if proc_match:
            proc_name = proc_match.group(1)
            node = {
                "type": "proc",
                "name": proc_name,
                "text": stripped
            }
            children.append(node)
            continue
        type_match = type_regex.match(line)
        if type_match:
            type_name = type_match.group(1)
            node = {
                "type": "type",
                "name": type_name,
                "text": stripped
            }
            children.append(node)
            continue
        # Additional parsing logic as needed.
    ast = {
        "type": "nim",
        "children": children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }
    features = extract_features_from_ast(ast)
    return build_parser_output(
        source_code=source_code,
        language="nim",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    )