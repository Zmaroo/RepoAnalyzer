"""
Custom Plain Text parser.

This parser simply splits the file into lines and returns a very simple AST,
where each line is represented as a node.
"""

from parsers.common_parser_utils import extract_features_from_ast, build_parser_output

def parse_plaintext_code(source_code: str) -> dict:
    """
    Parse a plain text file.

    Returns a dictionary with:
      - "content": the raw text,
      - "language": "plaintext",
      - "ast_data": an AST with each line as a node,
      - "ast_features": features extracted from the AST,
      - "lines_of_code": total number of lines,
      - "documentation": (empty, by default),
      - "complexity": a placeholder value.
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    for i, line in enumerate(lines):
        node = {
            "type": "line",
            "text": line,
            "line_number": i + 1
        }
        children.append(node)
    ast = {
        "type": "plaintext",
        "children": children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }
    features = extract_features_from_ast(ast)
    return build_parser_output(
        source_code=source_code,
        language="plaintext",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation="",
        complexity=1
    )