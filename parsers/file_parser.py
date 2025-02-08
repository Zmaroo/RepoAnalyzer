from __future__ import annotations  # Added to enable postponed evaluation of type annotations
import os
import json
from .language_parser import parse_code, get_ast_sexp, get_ast_json
from parsers.query_patterns import query_patterns  # our mapping of language -> query patterns
from tree_sitter_language_pack import get_language
from utils.logger import log
from typing import Optional, Dict, Any
from tree_sitter import Node, Parser
from parsers.ast_extractor import extract_ast_features

# Mapping file extensions to Tree-sitter language names
EXTENSION_TO_LANGUAGE = {
    # Web Technologies
    'js': 'javascript',
    'jsx': 'javascript',
    'mjs': 'javascript',
    'cjs': 'javascript',
    'es': 'javascript',
    'es6': 'javascript',
    'iife.js': 'javascript',
    'bundle.js': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'mts': 'typescript',
    'cts': 'typescript',
    'html': 'html',
    'htm': 'html',
    'css': 'css',
    'scss': 'scss',
    'sass': 'scss',
    'less': 'css',
    'vue': 'vue',
    'svelte': 'svelte',
    
    # Systems Programming
    'c': 'c',
    'h': 'c',
    'cpp': 'cpp',
    'hpp': 'cpp',
    'cc': 'cpp',
    'cxx': 'cpp',
    'hxx': 'cpp',
    'h++': 'cpp',
    'cu': 'cuda',
    'cuh': 'cuda',
    'rs': 'rust',
    'go': 'go',
    'mod': 'gomod',
    'sum': 'gosum',
    'v': 'verilog',
    'sv': 'verilog',
    'vh': 'verilog',
    'vhd': 'vhdl',
    'vhdl': 'vhdl',
    
    # JVM Languages
    'java': 'java',
    'kt': 'kotlin',
    'kts': 'kotlin',
    'scala': 'scala',
    'sc': 'scala',
    'groovy': 'groovy',
    'gradle': 'groovy',
    
    # Scripting Languages
    'py': 'python',
    'pyi': 'python',
    'pyc': 'python',
    'pyd': 'python',
    'pyw': 'python',
    'rb': 'ruby',
    'rbw': 'ruby',
    'rake': 'ruby',
    'gemspec': 'ruby',
    'php': 'php',
    'php4': 'php',
    'php5': 'php',
    'php7': 'php',
    'php8': 'php',
    'phps': 'php',
    'lua': 'lua',
    'pl': 'perl',
    'pm': 'perl',
    't': 'perl',
    
    # Shell Scripting
    'sh': 'bash',
    'bash': 'bash',
    'zsh': 'bash',
    'fish': 'fish',
    'ksh': 'bash',
    'csh': 'bash',
    'tcsh': 'bash',
    
    # Functional Languages
    'hs': 'haskell',
    'lhs': 'haskell',
    'ml': 'ocaml',
    'mli': 'ocaml',
    'ex': 'elixir',
    'exs': 'elixir',
    'heex': 'heex',
    'clj': 'clojure',
    'cljs': 'clojure',
    'cljc': 'clojure',
    'edn': 'clojure',
    
    # Configuration & Data
    'yaml': 'yaml',
    'yml': 'yaml',
    'json': 'json',
    'jsonc': 'json',
    'toml': 'toml',
    'xml': 'xml',
    'xsl': 'xml',
    'xslt': 'xml',
    'svg': 'xml',
    'xaml': 'xml',
    'ini': 'ini',
    'cfg': 'ini',
    'conf': 'ini',
    
    # Build Systems
    'cmake': 'cmake',
    'make': 'make',
    'mk': 'make',
    'ninja': 'ninja',
    'bazel': 'starlark',
    'bzl': 'starlark',
    'BUILD': 'starlark',
    'WORKSPACE': 'starlark',
    
    # Documentation
    'md': 'markdown',
    'markdown': 'markdown',
    'rst': 'rst',
    'tex': 'latex',
    'latex': 'latex',
    'adoc': 'asciidoc',
    'asciidoc': 'asciidoc',
    
    # Other Languages
    'swift': 'swift',
    'dart': 'dart',
    'r': 'r',
    'rmd': 'r',
    'jl': 'julia',
    'zig': 'zig',
    
    # Query Languages
    'sql': 'sql',
    'mysql': 'sql',
    'pgsql': 'sql',
    'graphql': 'graphql',
    'gql': 'graphql',
    
    # Additional Languages
    'proto': 'protobuf',
    'thrift': 'thrift',
    'wasm': 'wasm',
    'wat': 'wat',
    'glsl': 'glsl',
    'hlsl': 'hlsl',
    'wgsl': 'wgsl',
    'dockerfile': 'dockerfile',
    'Dockerfile': 'dockerfile',
    'nginx.conf': 'nginx',
    'rules': 'udev',
    'hypr': 'hyprlang',
    'kdl': 'kdl',
    'ron': 'ron',
    'commonlisp': 'commonlisp',
    'elixir': 'elixir'
}

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
    """Detects the language of a file based on its extension."""
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    return EXTENSION_TO_LANGUAGE.get(ext)

def process_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Enhanced file processing with metadata extraction."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        language = EXTENSION_TO_LANGUAGE.get(ext)
        
        if not language:
            return None
            
        tree = parse_code(content, language)
        if not tree:
            return None
            
        # Use the unified root node retrieval to ensure consistency
        root_node = get_root_node(tree)
        ast_data = get_ast_json(root_node)
        
        # Calculate basic metrics
        lines_of_code = len(content.splitlines())
        
        # Extract documentation (basic implementation)
        documentation = extract_documentation(root_node, content.encode('utf-8'))
        
        return {
            'content': content,
            'language': language,
            'ast_data': ast_data,
            'lines_of_code': lines_of_code,
            'documentation': documentation,
            'complexity': calculate_complexity(root_node)
        }
        
    except Exception as e:
        log(f"Error processing file {file_path}: {e}", level="error")
        return None

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