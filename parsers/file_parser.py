from __future__ import annotations  # Added to enable postponed evaluation of type annotations
import os
import json
from .language_parser import parse_code, get_ast_sexp, get_ast_json
from parsers.query_patterns import QUERY_PATTERNS, get_query_patterns
from tree_sitter_language_pack import get_language
from utils.logger import log
from typing import Optional, Dict, Any
from tree_sitter import Node, Parser
from parsers.ast_extractor import extract_ast_features
from .language_mapping import get_language_for_file
from parsers.language_mapping import normalize_language_name  # For language normalization

# Initialize the Tree-sitter parser. Make sure you have built your language library.
parser = Parser()
# Example: Uncomment and adjust the following lines if a language library is available.
# from tree_sitter_languages import get_language
# parser.set_language(get_language('python'))

def get_root_node(tree):
    """
    Returns the root node from the tree-sitter parse result.
    In some cases, 'tree' may already be a Node (without a 'root_node' attribute).
    """
    return tree.root_node if hasattr(tree, "root_node") else tree

def detect_language(file_path: str) -> Optional[str]:
    """Detects the language of a file based on its filename or extension."""
    return get_language_for_file(file_path)

def process_file(file_path: str):
    """
    Process a file by detecting its language and parsing it.
    Returns a standardized dictionary with code/documentation details.
    """
    from parsers.language_parser import parse_code
    from utils.logger import log

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()
    except Exception as e:
        log(f"Failed to read file {file_path}: {e}", level="error")
        return None

    language = detect_language(file_path)
    if language is None:
        log(f"Language could not be detected for file {file_path}", level="error")
        return None

    parsed_output = parse_code(source_code, language)
    if parsed_output is None:
        return None

    # Directly import and use get_query_patterns from the centralized module.
    from parsers.query_patterns import get_query_patterns
    patterns = get_query_patterns(language)
    parsed_output["query_patterns"] = patterns

    return parsed_output

def calculate_complexity(node: Node) -> int:
    """Calculate cyclomatic complexity (basic implementation)."""
    complexity = 1  # Base complexity
    
    # Count control flow statements
    control_patterns = [
        'if_statement',
        'while_statement',
        'for_statement',
        'case_statement',
        'catch_clause',
        '&&',
        '||'
    ]
    
    def traverse(node):
        nonlocal complexity
        if node.type in control_patterns:
            complexity += 1
        for child in node.children:
            traverse(child)
            
    traverse(node)
    return complexity

def extract_documentation(node: Node, source_bytes: bytes) -> str:
    """
    Extract documentation from an AST node.
    
    Args:
        node: The AST node to extract documentation from
        source_bytes: Original source code as bytes
        
    Returns:
        Extracted documentation string
    """
    try:
        # Get comments and docstrings
        doc_string = ""
        if hasattr(node, 'children'):
            for child in node.children:
                if child.type in ('comment', 'block_comment', 'line_comment', 'string', 'string_literal'):
                    start_byte = child.start_byte
                    end_byte = child.end_byte
                    text = source_bytes[start_byte:end_byte].decode('utf-8', errors='replace')
                    doc_string += text.strip() + "\n"
        return doc_string.strip()
    except Exception as e:
        log(f"Error extracting documentation: {e}", level="error")
        return ""

def parse_file(file_path: str):
    """
    Parses the source code from the given file using Tree-sitter and returns the root syntax node.
    
    Args:
        file_path (str): The full path to the source file.
    
    Returns:
        A tree-sitter Node representing the root of the syntax tree, or None if parsing fails.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        log(f"Error reading file {file_path}: {e}", level="error")
        return None

    try:
        tree = parser.parse(content.encode('utf-8'))
        root = get_root_node(tree)
        return root
    except Exception as e:
        log(f"Error parsing file {file_path}: {e}", level="error")
        return None

# Additional functions using the syntax tree can be added here.