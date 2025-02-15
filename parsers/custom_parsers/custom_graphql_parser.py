"""
Custom GraphQL parser.

This parser uses regexes to capture common GraphQL definitions such as type, interface,
enum, or schema definitions from a GraphQL file.
"""

from parsers.common_parser_utils import extract_features_from_ast, build_parser_output
import re

def parse_graphql_code(source_code: str) -> dict:
    """
    Parse a GraphQL file.

    Returns a dictionary with:
      - "content": the raw source code,
      - "language": "graphql",
      - "ast_data": an AST where each definition becomes a node,
      - "ast_features": features extracted from the AST,
      - "lines_of_code": total number of lines,
      - "documentation": any leading comment,
      - "complexity": a placeholder value.
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    documentation = ""
    # If the file begins with a comment, treat that as documentation.
    if lines and (lines[0].startswith("#") or lines[0].startswith(";")):
        documentation = lines[0].strip()

    definition_regex = re.compile(r'^\s*(type|interface|enum|schema)\s+([A-Za-z0-9_]+)')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if not documentation:
                documentation = stripped
            continue
        match = definition_regex.match(line)
        if match:
            def_type = match.group(1)
            def_name = match.group(2)
            node = {
                "type": "definition",
                "definition_type": def_type,
                "name": def_name,
                "text": stripped
            }
            children.append(node)
    ast = {
        "type": "graphql",
        "children": children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }
    features = extract_features_from_ast(ast)
    return build_parser_output(
        source_code=source_code,
        language="graphql",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    )