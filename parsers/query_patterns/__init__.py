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
    'env': 'env',
    'erlang': 'erlang',
    'fish': 'fish',
    'fortran': 'fortran',
    'gdscript': 'gdscript',
    'gitignore': 'gitignore',
    'gleam': 'gleam',
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
    'swift': 'swift',
    'tcl': 'tcl',
    'typescript': 'typescript',
    'vue': 'vue',
    'xml': 'xml',
    'yaml': 'yaml',
    'zig': 'zig',
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

# Import new query pattern modules for cobalt and pascal.
from .cobalt import COBALT_PATTERNS
from .pascal import PASCAL_PATTERNS

def get_query_patterns(language: str):
    normalized_lang = normalize_language_name(language)
    patterns = QUERY_PATTERNS.get(normalized_lang)
    if patterns is None:
        log(f"No query patterns found for language '{normalized_lang}', returning empty dict", level="warning")
        patterns = {}
    return patterns