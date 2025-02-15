"""
Custom OCaml parsers.

This module implements custom parsers for OCaml source files because we do not have
Tree-sitter language support for OCaml. Two kinds of source files are supported:
  - OCaml implementation files (.ml)
  - OCaml interface files (.mli)

Each parser extracts top-level declarations using regular expressions and converts the
source into a simplified custom AST with metadata (e.g. approximate byte positions,
document positions, and a top-level documentation comment if present).

NOTE:
  - This parser is intentionally a lightweight implementation meant for database ingestion
    and deep code base understanding. You can refine it over time to capture more detail.
  - Integrate this module with your main language parsing entry point so that when a file
    ends with .ml or .mli the corresponding function is called.
"""

import re
from parsers.common_parser_utils import extract_features_from_ast, build_parser_output

def compute_offset(lines, line_no, col):
    """
    Compute the byte offset for a given (line, col) pair.
    We assume that each line is terminated by a single newline character.
    """
    return sum(len(lines[i]) + 1 for i in range(line_no)) + col

# Define regex patterns for .ml files.
ML_PATTERNS = {
    "let_binding": re.compile(r'^\s*(let(?:\s+rec)?\s+[a-zA-Z0-9_\'-]+)'),
    "type_definition": re.compile(r'^\s*type\s+([a-zA-Z0-9_\'-]+)'),
    "module_declaration": re.compile(r'^\s*module\s+([A-Z][a-zA-Z0-9_\'-]*)'),
    "open_statement": re.compile(r'^\s*open\s+([A-Z][a-zA-Z0-9_.]*)'),
    "exception_declaration": re.compile(r'^\s*exception\s+([A-Z][a-zA-Z0-9_\'-]*)')
}

# Define regex patterns for .mli files.
MLI_PATTERNS = {
    "val_declaration": re.compile(r'^\s*val\s+([a-zA-Z0-9_\'-]+)'),
    "type_definition": re.compile(r'^\s*type\s+([a-zA-Z0-9_\'-]+)'),
    "module_declaration": re.compile(r'^\s*module\s+([A-Z][a-zA-Z0-9_\'-]*)')
}

def parse_ocaml_source(source_code: str, patterns: dict, language: str) -> dict:
    """
    A common helper to parse OCaml source code (.ml or .mli) using the provided regex patterns.
    
    Arguments:
      - source_code: the raw OCaml source code.
      - patterns: a dict of {node_name: regex} capturing top-level patterns.
      - language: a string; either "ocaml" for .ml files or "ocaml_interface" for .mli files.
      
    Returns a dictionary with:
      - "content": the raw source code,
      - "language": as provided,
      - "ast_data": a custom AST representing top-level nodes,
      - "ast_features": the extracted features (nodes grouped by type),
      - "lines_of_code": the total number of lines,
      - "documentation": a top-level documentation block (if the file starts with a comment),
      - "complexity": a placeholder complexity score.
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    
    # Attempt to extract a top-level documentation comment.
    documentation = ""
    if re.match(r'^\s*\(\*[\*!]', source_code):
        end_doc = source_code.find("*)")
        if end_doc != -1:
            documentation = source_code[:end_doc+2]
    
    ast_children = []
    for i, line in enumerate(lines):
        for node_type, regex in patterns.items():
            match = regex.match(line)
            if match:
                col = line.find(match.group(0))
                start_byte = compute_offset(lines, i, col)
                end_byte = compute_offset(lines, i, len(line))
                node = {
                    "type": node_type,
                    "text": line.strip(),
                    "start_point": [i, col],
                    "end_point": [i, len(line)],
                    "start_byte": start_byte,
                    "end_byte": end_byte,
                    "children": []
                }
                ast_children.append(node)
                # Stop further matching for this line.
                break

    ast = {
        "type": "ocaml_stream",
        "children": ast_children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }
    
    features = extract_features_from_ast(ast)
    return build_parser_output(
        source_code=source_code,
        language=language,
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1  # Placeholder complexity score; adjust as needed.
    )

def parse_ocaml_ml_code(source_code: str) -> dict:
    """
    Parse the source code of an OCaml implementation (.ml) file.
    
    Returns a dictionary with:
      - "content": the raw source code,
      - "language": "ocaml",
      - "ast_data": a lightweight AST of top-level declarations,
      - "ast_features": extracted nodes grouped by type,
      - "lines_of_code": total number of lines,
      - "documentation": a top-level documentation comment (if present),
      - "complexity": a placeholder complexity score.
    """
    return parse_ocaml_source(source_code, ML_PATTERNS, "ocaml")

def parse_ocaml_mli_code(source_code: str) -> dict:
    """
    Parse the source code of an OCaml interface (.mli) file.
    
    Returns a dictionary with:
      - "content": the raw source code,
      - "language": "ocaml_interface",
      - "ast_data": a lightweight AST of top-level declarations,
      - "ast_features": extracted nodes grouped by type,
      - "lines_of_code": total number of lines,
      - "documentation": a top-level documentation comment (if present),
      - "complexity": a placeholder complexity score.
    """
    return parse_ocaml_source(source_code, MLI_PATTERNS, "ocaml_interface") 