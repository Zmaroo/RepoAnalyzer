import os
from language_parser import parse_code

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

def detect_language(file_path: str) -> str | None:
    """Detects the language of a file based on its extension."""
    _, ext = os.path.splitext(file_path)
    return EXTENSION_TO_LANGUAGE.get(ext)

def process_file(file_path: str) -> str | None:
    """Reads a file, detects its language, and returns the parsed AST (s-expression)."""
    lang = detect_language(file_path)
    if not lang:
        print(f"Skipping unsupported file: {file_path}")
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        ast = parse_code(code, lang)
        print(f"Parsed {file_path} as {lang}")
        return ast
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None