"""
Common utilities for custom parsers.
"""

from typing import Dict
import json
from tree_sitter import Node, Tree

def sanitize_ast(ast):
    """
    Recursively sanitizes the given AST object to ensure it can be serialized to JSON.
    If the object is a Tree-sitter Node or Tree, return its S-expression representation.
    """
    if isinstance(ast, (Node, Tree)):
        try:
            # Use the S-expression for the tree or node (if available)
            return ast.sexp()
        except Exception as e:
            # Fall back to converting the object to its string representation
            return str(ast)
    elif isinstance(ast, dict):
        return {key: sanitize_ast(value) for key, value in ast.items()}
    elif isinstance(ast, list):
        return [sanitize_ast(item) for item in ast]
    else:
        # If the object is already a basic type, try dumping it to check
        try:
            json.dumps(ast)
            return ast
        except Exception:
            return str(ast)

def extract_features_from_ast(ast):
    """
    Extract additional features from the AST.
    This is a placeholder that currently returns an empty dictionary.
    Depending on your architecture, you may wish to count node types, depth,
    or other features.
    """
    # For now, simply return an empty dict.
    return {}

def build_parser_output(source_code: str,
                        language: str,
                        ast: any,
                        features: dict,
                        total_lines: int,
                        documentation: str,
                        complexity: int) -> dict:
    """
    Constructs the parsing output dictionary after sanitizing the AST.
    This ensures that the final output is JSON-serializable even if the raw AST
    contains Tree-sitter node objects.
    """
    sanitized_ast = sanitize_ast(ast)
    return {
        "content": source_code,
        "language": language,
        "ast": sanitized_ast,
        "features": features,
        "lines_of_code": total_lines,
        "documentation": documentation,
        "complexity": complexity,
    }
