"""
Common utilities for custom parsers.
"""

from typing import Dict
import json
from tree_sitter import Node, Tree

def sanitize_ast(obj):
    """
    Recursively sanitizes the given object to ensure it can be serialized to JSON.
    
    - If the object is callable (e.g., a function), return its string representation.
    - If it's a Tree-sitter Node or Tree, return its S-expression (or a string fallback).
    - Recursively process dictionaries, lists, tuples, and sets.
    - For basic types, ensure they can be JSON serialized, otherwise return a string.
    """
    if callable(obj):
        return f"<function {getattr(obj, '__name__', str(obj))}>"
    
    if isinstance(obj, (Node, Tree)):
        try:
            return obj.sexp()
        except Exception:
            return str(obj)
    
    if isinstance(obj, dict):
        return {key: sanitize_ast(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_ast(item) for item in obj]

    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)

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
    Constructs the parsing output dictionary after sanitizing the AST and features.
    This ensures that the final output is JSON-serializable even if the raw AST or features
    contain non-serializable objects such as Tree-sitter nodes or function references.
    
    Args:
        source_code: The original source code
        language: The normalized language identifier
        ast: The AST (can be tree-sitter node or custom AST)
        features: Dictionary of extracted features
        total_lines: Total number of lines in source
        documentation: Extracted documentation
        complexity: Computed complexity value
        
    Returns:
        Dictionary containing all parsed information in a standardized format
    """
    sanitized_ast = sanitize_ast(ast)
    ast_json = json.dumps(sanitized_ast)
    sanitized_features = sanitize_ast(features)
    
    return {
        "content": source_code,
        "language": language,
        "ast_data": sanitized_ast,
        "ast_json": ast_json,
        "ast_features": sanitized_features,
        "lines_of_code": total_lines,
        "documentation": documentation,
        "complexity": complexity,
    }
