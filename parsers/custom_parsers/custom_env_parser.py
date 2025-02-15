"""
Custom .env file parser.

This parser processes .env files by extracting key=value pairs.
Comments (lines starting with #) are skipped (or can be used as documentation).
"""

from parsers.common_parser_utils import extract_features_from_ast, build_parser_output

def parse_env_code(source_code: str) -> dict:
    """
    Parse a .env file.

    Returns a dictionary with:
      - "content": the raw source code,
      - "language": "env",
      - "ast_data": a custom AST listing all environment variables,
      - "ast_features": features from the AST,
      - "lines_of_code": total lines,
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

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            node = {
                "type": "env_var",  # tag each variable node for query patterns
                "key": key.strip(),
                "value": value.strip(),
                "text": stripped
            }
            children.append(node)
    ast = {
        "type": "env_file",
        "children": children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }
    features = extract_features_from_ast(ast)
    return build_parser_output(
        source_code=source_code,
        language="env",  # <-- Corrected language identifier!
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    )