import os
import importlib
import pkgutil
from parsers.language_mapping import normalize_language_name
from utils.logger import log
from .ada import ADA_PATTERNS
from .asm import ASM_PATTERNS
from .bash import BASH_PATTERNS

# Mapping from module names (i.e. file names) to our normalized language keys.
MODULE_LANGUAGE_MAP = {
    'ada': 'ada',
    'asm': 'asm',
    'bash': 'bash',
    'bibtex': 'bibtex',
    'c': 'c',
    'cmake': 'cmake',
    'clojure': 'clojure',
    'cpp': 'cpp',
    'csharp': 'csharp',
    'cuda': 'cuda',
    'dart': 'dart',
    'dockerfil': 'dockerfile',  # adjust for dockerfil.py naming
    'editorconfig': 'editorconfig',
    'elisp': 'elisp',
    'elixir': 'elixir',
    'elm': 'elm',             # Added Elm mapping
    'env': 'env',
    'erlang': 'erlang',
    'fish': 'fish',
    'fortran': 'fortran',
    'gdscript': 'gdscript',
    'gitignore': 'gitignore',
    'gleam': 'gleam',
    'hack': 'hack',          # Added Hack mapping
    'haxe': 'haxe',          # Added Haxe mapping
    'json': 'json',
    'julia': 'julia',
    'kotlin': 'kotlin',
    'lua': 'lua',
    'makefile': 'makefile',
    'markdown': 'markdown',
    'matlab': 'matlab',
    'nim': 'nim',
    'ocaml': 'ocaml',
    'ocaml_interface': 'ocaml_interface',
    'perl': 'perl',
    'php': 'php',
    'plaintext': 'plaintext',
    'powershell': 'powershell',
    'proto': 'proto',
    'python': 'python',
    'r': 'r',
    'ruby': 'ruby',
    'rust': 'rust',
    'scala': 'scala',
    'solidity': 'solidity',   # Added Solidity mapping
    'swift': 'swift',
    'tcl': 'tcl',             # Added Tcl mapping
    'typescript': 'typescript',
    'verilog': 'verilog',     # Added Verilog mapping
    'vue': 'vue',
    'xml': 'xml',
    'yaml': 'yaml',
    'zig': 'zig',
    'pascal': 'pascal',       # Added Pascal mapping
    'cobalt': 'cobalt',       # Added Cobalt mapping
    'purescript': 'purescript',  # Added Purescript mapping
    'asciidoc': 'asciidoc',   # AsciiDoc parser
    'html': 'html',           # Custom HTML parser
    'ini': 'ini',             # Custom INI/Properties parser
    'json': 'json',           # Custom JSON parser
    'rst': 'rst',             # reStructuredText parser
    'toml': 'toml',           # Custom TOML parser
}

QUERY_PATTERNS = {}

# Automatically load all query pattern modules in this directory.
package_dir = os.path.dirname(__file__)
for module_info in pkgutil.iter_modules([package_dir]):
    module_name = module_info.name
    if module_name == '__init__':
        continue
    try:
        module = importlib.import_module(f"parsers.query_patterns.{module_name}")
        log(f"Successfully imported query patterns module: {module_name}", level="debug")
    except Exception as e:
        log(f"Failed to import query patterns module '{module_name}': {e}", level="error")
        continue

    # Look for attributes ending in _PATTERNS.
    for attr in dir(module):
        if attr.endswith('_PATTERNS'):
            patterns = getattr(module, attr)
            if isinstance(patterns, (dict, list)):
                # Determine the normalized language key for this module.
                key = MODULE_LANGUAGE_MAP.get(module_name.lower(), module_name.lower())
                # If patterns is a list (for example, defined as a list of strings),
                # wrap it in a dict under a default key.
                if isinstance(patterns, list):
                    # Convert a list of queries into a dictionary under a default key.
                    patterns = {"default": "\n".join(patterns)}
                if key in QUERY_PATTERNS:
                    # Merge dictionaries if the key already exists.
                    if isinstance(QUERY_PATTERNS[key], dict) and isinstance(patterns, dict):
                        QUERY_PATTERNS[key].update(patterns)
                    else:
                        QUERY_PATTERNS[key] = patterns
                else:
                    QUERY_PATTERNS[key] = patterns
                log(f"Loaded query patterns for '{key}' from attribute '{attr}'", level="debug")


# Add pattern categories for better organization
PATTERN_CATEGORIES = {
    "syntax": [
        "function", "class", "module",
        # Add markup-specific patterns
        "section", "block", "element", "directive",
        "macro", "attribute"
    ],
    "semantics": [
        "variable", "type", "expression",
        # Add markup-specific patterns
        "link", "reference", "definition", "term",
        "callout", "citation"
    ],
    "documentation": [
        "comment", "docstring",
        # Add markup-specific patterns
        "metadata", "description", "admonition",
        "annotation", "field"
    ],
    "structure": [
        "namespace", "import", "export",
        # Add markup-specific patterns
        "hierarchy", "include", "anchor", "toc"
    ]
}

def get_query_patterns(language: str):
    """Get query patterns for a language with improved error handling."""
    try:
        normalized_lang = normalize_language_name(language)
        patterns = QUERY_PATTERNS.get(normalized_lang)
        if patterns is None:
            log(f"No query patterns found for language '{normalized_lang}', returning empty dict", 
                level="warning")
            patterns = {}
        return patterns
    except Exception as e:
        log(f"Error getting query patterns for '{language}': {e}", level="error")
        return {}

def validate_pattern_category(pattern_name: str) -> str:
    """
    Validate and return the category a pattern belongs to.
    
    Args:
        pattern_name: The name of the pattern to categorize
        
    Returns:
        str: The category name, or 'unknown' if not found
    """
    for category, patterns in PATTERN_CATEGORIES.items():
        if pattern_name in patterns:
            return category
    return "unknown"

def get_patterns_by_category(language: str, category: str) -> dict:
    """Get all patterns for a language belonging to a specific category."""
    all_patterns = get_query_patterns(language)
    return {
        name: pattern for name, pattern in all_patterns.items()
        if validate_pattern_category(name) == category
    }