from typing import Dict, Set, Optional, Tuple
from tree_sitter_language_pack import get_language, SupportedLanguage, get_binding, get_parser
import os

# Map file extensions to tree-sitter language names.
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    # Web Technologies
    'js': 'javascript',
    'jsx': 'javascript',
    'mjs': 'javascript',
    'cjs': 'javascript',
    'ts': 'typescript',
    'tsx': 'tsx',  # Note: tsx is separate from typescript in tree-sitter
    'html': 'html',
    'htm': 'html',
    'css': 'css',
    'scss': 'scss',
    'vue': 'vue',
    'svelte': 'svelte',

    # Systems Programming
    'c': 'c',
    'h': 'c',
    'cpp': 'cpp',
    'hpp': 'cpp',
    'cc': 'cpp',
    'cxx': 'cpp',
    'cu': 'cuda',
    'cuh': 'cuda',
    'rs': 'rust',
    'go': 'go',
    'mod': 'gomod',
    'sum': 'gosum',
    'v': 'v',
    'vh': 'verilog',
    'sv': 'verilog',
    'vhd': 'vhdl',

    # JVM Languages
    'java': 'java',
    'kt': 'kotlin',
    'kts': 'kotlin',
    'scala': 'scala',
    'gradle': 'groovy',
    'groovy': 'groovy',

    # Scripting Languages
    'py': 'python',
    'pyi': 'python',
    'rb': 'ruby',
    'rake': 'ruby',
    'gemspec': 'ruby',
    'php': 'php',
    'lua': 'lua',
    'pl': 'perl',
    'pm': 'perl',
    'tcl': 'tcl',
    'r': 'r',
    'rmd': 'r',

    # Shell Scripting
    'sh': 'bash',
    'bash': 'bash',
    'fish': 'fish',

    # Functional Languages
    'hs': 'haskell',
    'lhs': 'haskell',
    'elm': 'elm',
    'ex': 'elixir',
    'exs': 'elixir',
    'heex': 'heex',
    'clj': 'clojure',
    'cljs': 'clojure',
    'cljc': 'clojure',
    'lisp': 'commonlisp',
    'cl': 'commonlisp',
    'asd': 'commonlisp',

    # Configuration & Data
    'yaml': 'yaml',
    'yml': 'yaml',
    'json': 'json',
    'jsonc': 'json',
    'toml': 'toml',
    'xml': 'xml',
    'xsl': 'xml',
    'svg': 'xml',
    'ini': 'properties',
    'properties': 'properties',

    # Build Systems
    'cmake': 'cmake',
    'make': 'make',
    'mk': 'make',
    'ninja': 'ninja',
    'bazel': 'starlark',
    'bzl': 'starlark',

    # Documentation
    'md': 'markdown',
    'markdown': 'markdown',
    'rst': 'rst',
    'tex': 'latex',

    # Other Languages
    'swift': 'swift',
    'dart': 'dart',
    'jl': 'julia',
    'zig': 'zig',
    'sql': 'sql',
    'mysql': 'sql',
    'pgsql': 'sql',
    'graphql': 'graphql',
    'proto': 'proto',
    'thrift': 'thrift',
    'glsl': 'glsl',
    'hlsl': 'hlsl',
    'wgsl': 'wgsl',
    'dockerfile': 'dockerfile',
    'Dockerfile': 'dockerfile',

    # Additional tree-sitter supported languages
    'ada': 'ada',
    'agda': 'agda',
    'astro': 'astro',
    'bicep': 'bicep',
    'cairo': 'cairo',
    'capnp': 'capnp',
    'cs': 'csharp',
    'd': 'd',
    'erl': 'erlang',
    'gleam': 'gleam',
    'hcl': 'hcl',
    'tf': 'terraform',
    'kdl': 'kdl',
    'nix': 'nix',
    'odin': 'odin',
    'pony': 'pony',
    'ps1': 'powershell',
    'psm1': 'powershell',
    'psd1': 'powershell',
    'prisma': 'prisma',
    'purs': 'purescript',
    'qml': 'qmljs',
    'ron': 'ron',
    'sol': 'solidity',
    'wat': 'wat',
    'xit': 'xml',
    'xaml': 'xml',
    'yuck': 'yuck',
    'adb': 'ada',
    'gd': 'gdscript',

    # OCaml custom support (handled by our custom OCaml parser)
    'ml': 'ocaml',
    'mli': 'ocaml_interface',

    # Add mappings for previously "unsupported" languages
    'asm': 'asm',
    'bib': 'bibtex',
    'el': 'elisp',
    'f90': 'fortran',
    'f95': 'fortran',
    'f03': 'fortran',
    'f08': 'fortran',
    'm': 'matlab',
    'nut': 'squirrel',
    'rkt': 'racket',

    # Add Bazel/Starlark related extensions
    'sky': 'starlark',

    # Add mappings for file extensions
    'hack': 'hack',
    'hx': 'haxe',
    'nim': 'nim',

    # Update existing mappings
    'editorconfig': 'editorconfig',
    'env': 'env',
    'requirements': 'requirements',
    'gitignore': 'gitignore',
    'txt': 'plaintext',  # Added mapping for plain text files
    
    # Add any missing tree-sitter supported languages
    'fish': 'fish',
    'verilog': 'verilog',
    'elm': 'elm',
    'haxe': 'haxe',
    'solidity': 'solidity',
    'tcl': 'tcl',
    'purescript': 'purescript',

    # Update EXTENSION_TO_LANGUAGE with CMake extensions
    'cmake.in': 'cmake',  # Template files

    # New entries for cobalt and pascal support.
    '.cob': 'cobalt',
    '.pas': 'pascal',
}

# Language name normalizations (for backwards compatibility)
LANGUAGE_NORMALIZATIONS = {
    "c++": "cpp",
    "cplusplus": "cpp",
    "c#": "csharp",
    "csharp": "csharp",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "golang": "go",
    "py": "python",
    "rb": "ruby",
    "commonlisp": "commonlisp",
    "lisp": "commonlisp",
    "ini": "properties",
    "conf": "properties",
    "powershell": "powershell",
    "ps1": "powershell"
}

LANGUAGE_NORMALIZATIONS.update({
    'editorconfig': 'editorconfig',
    'env': 'env',
    'requirements': 'requirements',
    'gitignore': 'gitignore',
    'fish': 'fish',
    'verilog': 'verilog', 
    'elm': 'elm',
    'hack': 'hack',
    'haxe': 'haxe',
    'solidity': 'solidity',
    'tcl': 'tcl',
    'purescript': 'purescript',
    'plaintext': 'plaintext',
    'graphql': 'graphql',
    'nim': 'nim',
    'gql': 'graphql'
})

def normalize_language_name(name: str) -> str:
    """Normalize a language name to our standard format."""
    return LANGUAGE_NORMALIZATIONS.get(name.lower().replace('-', '_'), name.lower())

def get_language_for_extension(ext: str) -> Optional[str]:
    """Get normalized language name for a file extension."""
    ext = ext.lstrip('.').lower()
    return EXTENSION_TO_LANGUAGE.get(ext)

# Move special filenames to a dedicated dictionary
SPECIAL_FILENAMES = {
    # CMake files
    'CMakeLists.txt': 'cmake',
    
    # Other special files
    'requirements.txt': 'requirements',
    '.gitignore': 'gitignore',
    '.editorconfig': 'editorconfig',
    '.env': 'env',
    'Dockerfile': 'dockerfile',  # Added mapping for Dockerfile
    
    # Bazel/Starlark files
    'BUILD': 'starlark',
    'BUILD.bazel': 'starlark',
    'WORKSPACE': 'starlark',
    'WORKSPACE.bazel': 'starlark',
    'BUCK': 'starlark',  # Add Buck build files
}

def get_language_for_file(filepath: str) -> Optional[str]:
    """
    Get language for a file based on its filename or extension.
    Prioritizes special filenames over extension-based detection.
    """
    filename = os.path.basename(filepath)
    # Check special filenames first
    if filename in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[filename]
    # Handle patterns (e.g. files starting with BUILD.)
    if filename.startswith("BUILD."):
        return "starlark"
    # Fallback: use the extension mapping
    ext = os.path.splitext(filename)[1]
    return get_language_for_extension(ext)

class LanguageSupport:
    """Centralized language support management."""
    
    @staticmethod
    def is_supported(language_name: str) -> bool:
        """Check if a language is supported by tree-sitter."""
        try:
            normalized = normalize_language_name(language_name)
            get_binding(normalized)
            get_language(normalized)
            get_parser(normalized)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_supported_languages() -> Set[str]:
        """Get set of all languages supported by tree-sitter."""
        supported = set()
        for lang in EXTENSION_TO_LANGUAGE.values():
            if LanguageSupport.is_supported(lang):
                supported.add(lang)
        return supported
    
    @staticmethod
    def has_query_patterns(language_name: str) -> bool:
        """Check if a language has query patterns defined."""
        from parsers.query_patterns import QUERY_PATTERNS
        normalized = normalize_language_name(language_name)
        return normalized in QUERY_PATTERNS
    
    @staticmethod
    def get_language_info(language_name: str) -> Tuple[bool, bool]:
        """Get support status tuple (tree_sitter_supported, has_patterns)."""
        is_supported_flag = LanguageSupport.is_supported(language_name)
        has_patterns_flag = LanguageSupport.has_query_patterns(language_name)
        return (is_supported_flag, has_patterns_flag)

# Import custom parsers from our custom parser modules.
from parsers.custom_parsers.custom_env_parser import parse_env_code
from parsers.custom_parsers.custom_plaintext_parser import parse_plaintext_code
from parsers.custom_parsers.custom_yaml_parser import parse_yaml_code
from parsers.custom_parsers.custom_markdown_parser import parse_markdown_code
from parsers.custom_parsers.custom_editorconfig_parser import parse_editorconfig_code
from parsers.custom_parsers.custom_graphql_parser import parse_graphql_code
from parsers.custom_parsers.custom_nim_parser import parse_nim_code
from parsers.custom_parsers.custom_ocaml_parser import parse_ocaml_ml_code, parse_ocaml_mli_code

# Register all custom parsers. Keys here should be normalized names.
CUSTOM_PARSER_FUNCTIONS: Dict[str, callable] = {
    "env": parse_env_code,
    "plaintext": parse_plaintext_code,
    "yaml": parse_yaml_code,
    "markdown": parse_markdown_code,
    "editorconfig": parse_editorconfig_code,
    "graphql": parse_graphql_code,
    "nim": parse_nim_code,
    "ocaml": parse_ocaml_ml_code,
    "ocaml_interface": parse_ocaml_mli_code,
}