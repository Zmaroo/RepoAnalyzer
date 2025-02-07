import os
import json
from .language_parser import parse_code, get_ast_sexp
from parsers.query_patterns import query_patterns  # our mapping of language -> query patterns
from tree_sitter_language_pack import get_language
from utils.logger import log
from typing import Optional

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

def detect_language(file_path: str) -> Optional[str]:
    """Detects the language of a file based on its extension."""
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    return EXTENSION_TO_LANGUAGE.get(ext)

def process_file(file_path: str) -> Optional[str]:
    """
    Processes a source file as follows:
      - Reads the file (both as bytes and as a UTF-8 string).
      - Detects the language using the file extension.
      - Parses the code into an AST.
      - If a query pattern (e.g. "function_details") exists for that language,
        extracts only the desired AST features using the query.
      - Otherwise, falls back to storing the full s-expression.
      - Returns the result (JSON when using query extraction).
      
    If Tree-sitter's language pack does not support the language (even if we have
    a query pattern for it), we catch the error/log a warning and fallback.
    """
    try:
        # Read file content as bytes (needed for accurate byte offsets)
        with open(file_path, "rb") as f:
            source_bytes = f.read()
        # Also decode to UTF-8 for parsing
        source_code = source_bytes.decode("utf-8", errors="replace")
        
        language_name = detect_language(file_path)
        if not language_name:
            log(f"Unsupported file extension for: {file_path}", level="debug")
            return None

        root_node = parse_code(source_code, language_name)
        if not root_node:
            log(f"Parsing failed for file: {file_path}", level="error")
            return None

        # Look up the query patterns for the detected language.
        normalized_lang = language_name.lower()
        patterns = query_patterns.get(normalized_lang)
        result = None

        if patterns and "function_details" in patterns:
            try:
                language_object = get_language(language_name)
            except Exception as e:
                log(f"Tree-sitter does not support language '{language_name}' even though a pattern exists. Error: {e}", level="warning")
                language_object = None

            if language_object:
                from parsers.ast_extractor import extract_ast_features
                features = extract_ast_features(root_node, language_object, patterns["function_details"], source_bytes)
                result = json.dumps(features)
            else:
                # Fallback to storing the full tree representation.
                result = get_ast_sexp(root_node)
        else:
            # Fallback: store the full s-expression.
            result = get_ast_sexp(root_node)
        
        log(f"Processed file {file_path} as {language_name}", level="info")
        return result

    except Exception as e:
        log(f"Error processing {file_path}: {e}", level="error")
        return None