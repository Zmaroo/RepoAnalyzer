"""Language mapping definitions and language detection utilities.

This module provides a comprehensive set of language mapping utilities, including:
1. Extensions to language mappings
2. Language aliases and normalization
3. Parser type determination
4. Language detection from content
5. Fallback mechanisms

All language detection logic should be centralized in this module.
"""
from utils.logger import log
from typing import Optional, Set, Dict, List, Tuple, Any
import os
import re
from parsers.types import FileType, ParserType
from parsers.models import LanguageFeatures

# Language support mappings
# --------------------------
# The following data structures work together to provide language support:
#
# 1. LANGUAGE_ALIASES - Maps alternate names to canonical language names
#    Used by: normalize_language_name()
#
# 2. EXTENSION_TO_LANGUAGE - Maps file extensions to canonical language names
#    Used by: detect_language_from_filename(), get_language_by_extension()
#
# 3. TREE_SITTER_LANGUAGES & CUSTOM_PARSER_LANGUAGES - Define available parser implementations
#    Used by: get_parser_type(), language_registry.get_parser()
#
# 4. LANGUAGE_TO_FILE_TYPE - Maps languages to their file type classification
#    Used by: get_file_type(), file classification
#
# 5. FILENAME_MAP - Maps specific filenames to language IDs
#    Used by: detect_language_from_filename()
#
# Validation is performed to ensure no language appears in both TREE_SITTER_LANGUAGES
# and CUSTOM_PARSER_LANGUAGES, as this would create ambiguity in parser selection.

# Language aliases map for normalization
LANGUAGE_ALIASES = {
    "c++": "cpp",
    "cplusplus": "cpp",
    "h": "c",
    "hpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "c#": "csharp",
    "cs": "csharp",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "py": "python",
    "pyi": "python",
    "pyc": "python",
    "rb": "ruby",
    "rake": "ruby",
    "gemspec": "ruby",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "shell": "bash",
    "htm": "html",
    "xhtml": "html",
    "yml": "yaml",
    "kt": "kotlin",
    "kts": "kotlin",
    "scala": "scala",
    "gradle": "groovy",
    "markdown": "md",
    "rst": "restructuredtext",
    "rest": "restructuredtext",
    "asciidoc": "adoc",
    "ini": "properties",
    "conf": "properties",
    "cfg": "properties",
    "dockerfil": "dockerfile",
    "dockerfile": "dockerfile",
    "docker": "dockerfile",
    "mk": "make",
    "cmake": "cmake",
    "mak": "make",
    "el": "elisp",
    "emacs": "elisp",
    "emacslisp": "elisp",
    "ex": "elixir",
    "ml": "ocaml",
    "mli": "ocaml_interface",
}

# Core extension to language mapping (without period prefix)
EXTENSION_TO_LANGUAGE = {
    'py': 'python',
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'cpp': 'cpp',
    'hpp': 'cpp',
    'cc': 'cpp',
    'cxx': 'cpp',
    'c': 'c',
    'h': 'c',
    'rb': 'ruby',
    'php': 'php',
    'pl': 'perl',
    'sh': 'bash',
    'bash': 'bash',
    'zsh': 'bash',
    'java': 'java',
    'kt': 'kotlin',
    'kts': 'kotlin',
    'scala': 'scala',
    'sc': 'scala',
    'sbt': 'scala',
    'groovy': 'groovy',
    'md': 'markdown',
    'markdown': 'markdown',
    'rst': 'restructuredtext',
    'adoc': 'asciidoc',
    'asciidoc': 'asciidoc',
    'tex': 'latex',
    'json': 'json',
    'yaml': 'yaml',
    'yml': 'yaml',
    'toml': 'toml',
    'ini': 'ini',
    'conf': 'ini',
    'cfg': 'ini',
    'dockerfile': 'dockerfile',
    'makefile': 'make',
    'cmake': 'cmake',
    'swift': 'swift',
    'lua': 'lua',
    'r': 'r',
    'el': 'elisp',
    'ex': 'elixir',
    'exs': 'elixir',
    'heex': 'elixir',
    'leex': 'elixir',
    'lisp': 'commonlisp',
    'cl': 'commonlisp',
    'lsp': 'commonlisp',
    'cs': 'csharp',
    'cu': 'cuda',
    'cuh': 'cuda',
    'dart': 'dart',
    'dockerfil': 'dockerfile',
    'rake': 'ruby',
    'gemspec': 'ruby',
    'rs': 'rust',
    'rlib': 'rust',
    'sql': 'sql',
    'mysql': 'sql',
    'psql': 'sql',
    'swiftinterface': 'swift',
    'd.ts': 'typescript',
    'mjs': 'javascript',
    'cjs': 'javascript',
    'v': 'verilog',
    'vh': 'verilog',
    'sv': 'systemverilog',
    'svh': 'systemverilog',
    'vhd': 'vhdl',
    'vhdl': 'vhdl',
    'vho': 'vhdl',
    'vue': 'vue',
    'zig': 'zig',
    'elm': 'elm',
    'erl': 'erlang',
    'hrl': 'erlang',
    'fish': 'fish',
    'f90': 'fortran',
    'f95': 'fortran',
    'f03': 'fortran',
    'f08': 'fortran',
    'gd': 'gdscript',
    'gleam': 'gleam',
    'go': 'go',
    'hack': 'hack',
    'hh': 'hack',
    'hx': 'haxe',
    'hxml': 'haxe',
    'tf': 'hcl',
    'hcl': 'hcl',
    'tex': 'latex',
    'sty': 'latex',
    'cls': 'latex',
    'mk': 'make',
    'mak': 'make',
    'make': 'make',
    'm': 'matlab',
    'mat': 'matlab',
    'nix': 'nix',
    'mm': 'objc',
    'pas': 'pascal',
    'pp': 'pascal',
    'pm': 'perl',
    't': 'perl',
    'php4': 'php',
    'php5': 'php',
    'php7': 'php',
    'phps': 'php',
    'ps1': 'powershell',
    'psm1': 'powershell',
    'psd1': 'powershell',
    'prisma': 'prisma',
    'proto': 'proto',
    'purs': 'purescript',
    'qml': 'qmljs',
    'qmldir': 'qmldir',
    'rkt': 'racket',
    'txt': 'plaintext',
    'nut': 'squirrel',
    'star': 'starlark',
    'bzl': 'starlark',
    'svelte': 'svelte',
    'tcl': 'tcl',
    'tk': 'tcl',
    'sol': 'solidity',
    'ml': 'ocaml',
    'mli': 'ocaml_interface',
    'html': 'html',
    'htm': 'html',
    'css': 'css',
    'scss': 'css',
    'sass': 'css',
    'less': 'css',
    'xml': 'xml',
    'svg': 'xml',
    'graphql': 'graphql',
    'gql': 'graphql',
    'env': 'env',
    'editorconfig': 'editorconfig',
    'asm': 'asm',
    's': 'asm',
    'clj': 'clojure',
    'cob': 'cobalt',
    'jl': 'julia',
    'hs': 'haskell',
    'nim': 'nim',
    'bib': 'bibtex',
}

# Full extension map (with period prefix)
FULL_EXTENSION_MAP = {f'.{ext}': lang for ext, lang in EXTENSION_TO_LANGUAGE.items()}

# Files that should be recognized by filename rather than extension
FILENAME_MAP = {
    'makefile': 'make',
    'Makefile': 'make',
    'dockerfile': 'dockerfil',
    'Dockerfile': 'dockerfil',
    '.gitignore': 'gitignore',
    '.gitattributes': 'gitignore',
    'requirements.txt': 'requirements',
    'CMakeLists.txt': 'cmake',
    'package.json': 'json',
    'tsconfig.json': 'json',
    'composer.json': 'json',
    '.babelrc': 'json',
    '.npmrc': 'ini',
    '.eslintrc': 'json',
    'Gemfile': 'ruby',
    'Rakefile': 'ruby',
}

# Shebang pattern to detect language from script header
SHEBANG_PATTERN = re.compile(r'^#!\s*(?:/usr/bin/env\s+)?([a-zA-Z0-9_]+)')

# Shebang to language mapping
SHEBANG_MAP = {
    'python': 'python',
    'python2': 'python',
    'python3': 'python',
    'node': 'javascript',
    'nodejs': 'javascript',
    'bash': 'shell',
    'sh': 'shell',
    'zsh': 'shell',
    'ruby': 'ruby',
    'perl': 'perl',
    'php': 'php',
    'pwsh': 'powershell',
    'r': 'r',
}

# Lists of languages by parser type
TREE_SITTER_LANGUAGES = {
    'bash', 'c', 'cpp', 'css', 'dockerfile', 'go', 'java', 'javascript',
    'kotlin', 'lua', 'make', 'php', 'python', 'ruby', 'rust',
    'scala', 'swift', 'tsx', 'typescript', 'zig',
    'cmake', 'cuda', 'dart', 'elisp', 'elixir', 'elm', 'erlang', 'fish',
    'fortran', 'gdscript', 'gleam', 'groovy', 'hack', 'haxe', 'hcl',
    'latex', 'matlab', 'nix', 'objc', 'pascal', 'perl', 'powershell',
    'prisma', 'proto', 'purescript', 'qmljs', 'racket', 'sql', 'svelte',
    'tcl', 'verilog', 'vhdl', 'vue'
}

CUSTOM_PARSER_LANGUAGES = {
    'env',
    'plaintext',
    'yaml',
    'markdown',
    'editorconfig',
    'graphql',
    'nim',
    'ocaml',
    'ocaml_interface',
    'cobalt',
    'xml',
    'html',
    'ini',
    'json',
    'restructuredtext',
    'toml',
    'asciidoc'
}

# Log languages that have both custom and tree-sitter parsers
overlapping_languages = TREE_SITTER_LANGUAGES.intersection(CUSTOM_PARSER_LANGUAGES)
if overlapping_languages:
    overlap_list = ", ".join(sorted(overlapping_languages))
    error_message = f"Languages found in both TREE_SITTER_LANGUAGES and CUSTOM_PARSER_LANGUAGES: {overlap_list}"
    log(error_message, level="error")
    # In development, you might want to raise an exception here
    # raise ValueError(error_message)

# MIME type mappings
MIME_TYPES = {
    "python": {"text/x-python", "application/x-python-code"},
    "javascript": {"text/javascript", "application/javascript"},
    "typescript": {"text/typescript", "application/typescript"},
    "json": {"application/json"},
    "yaml": {"text/yaml", "application/x-yaml"},
    "markdown": {"text/markdown"},
    "html": {"text/html"},
    "css": {"text/css"},
    "xml": {"text/xml", "application/xml"},
    "php": {"text/php", "application/php"},
    "ruby": {"text/ruby", "application/ruby"},
    "go": {"text/go", "application/go"},
    "rust": {"text/rust", "application/rust"},
}

# Binary file extensions
BINARY_EXTENSIONS = {
    '.bin', '.exe', '.dll', '.so', '.dylib', '.obj', '.o', '.class',
    '.jar', '.war', '.ear', '.zip', '.tar', '.gz', '.7z', '.rar',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.webp',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.db', '.sqlite', '.pyc', '.pyd', '.pyo'
}

# Language to file type mapping
LANGUAGE_TO_FILE_TYPE = {
    # Documentation languages
    'markdown': FileType.DOC,
    'restructuredtext': FileType.DOC,
    'asciidoc': FileType.DOC,
    'html': FileType.DOC,
    'xml': FileType.DOC,
    'plaintext': FileType.DOC,
    
    # Configuration languages
    'json': FileType.CONFIG,
    'yaml': FileType.CONFIG,
    'toml': FileType.CONFIG,
    'ini': FileType.CONFIG,
    'env': FileType.CONFIG,
    'editorconfig': FileType.CONFIG,
    'gitignore': FileType.CONFIG,
    'properties': FileType.CONFIG,
    
    # Data languages
    'csv': FileType.DATA,
    'tsv': FileType.DATA,
    'sql': FileType.DATA,
    
    # All others default to code
}

def normalize_language_name(language: str) -> str:
    """
    Normalize a language name using LANGUAGE_ALIASES.
    
    Args:
        language: The language name to normalize
        
    Returns:
        Normalized language name
    """
    if not language:
        return "unknown"
    try:
        normalized = language.lower().strip()
        return LANGUAGE_ALIASES.get(normalized, normalized)
    except Exception as e:
        log(f"Error normalizing language name '{language}': {e}", level="error")
        return "unknown"

def is_supported_language(language_id: str) -> bool:
    """
    Check if language is supported by any parser.
    
    Args:
        language_id: The language identifier to check
        
    Returns:
        True if supported, False otherwise
    """
    normalized = normalize_language_name(language_id)
    return normalized in TREE_SITTER_LANGUAGES or normalized in CUSTOM_PARSER_LANGUAGES

def get_parser_type(language_id: str) -> ParserType:
    """
    Determine the parser type for a given language.
    
    Args:
        language_id: The language identifier
        
    Returns:
        ParserType enum value
    """
    normalized = normalize_language_name(language_id)
    
    # Prioritize custom parsers over tree-sitter parsers
    if normalized in CUSTOM_PARSER_LANGUAGES:
        return ParserType.CUSTOM
    elif normalized in TREE_SITTER_LANGUAGES:
        return ParserType.TREE_SITTER
    
    # Default case
    return ParserType.UNKNOWN

def get_fallback_parser_type(language_id: str) -> ParserType:
    """
    Get a fallback parser type for languages where the primary parser
    might not be available.
    
    Args:
        language_id: The language identifier
        
    Returns:
        Fallback ParserType enum value
    """
    normalized = normalize_language_name(language_id)
    # Languages with potential fallbacks (Tree-sitter to Custom)
    if normalized in {'markdown', 'json', 'yaml', 'toml', 'html', 'xml'} and normalized in TREE_SITTER_LANGUAGES:
        return ParserType.CUSTOM
    # Languages with potential fallbacks (Custom to Tree-sitter)  
    elif normalized in {'markdown', 'json', 'yaml', 'toml', 'html', 'xml'} and normalized in CUSTOM_PARSER_LANGUAGES:
        return ParserType.TREE_SITTER
    else:
        return ParserType.UNKNOWN

def get_file_type(language_id: str) -> FileType:
    """
    Determine the file type for a given language.
    
    Args:
        language_id: The language identifier
        
    Returns:
        FileType enum value
    """
    normalized = normalize_language_name(language_id)
    return LANGUAGE_TO_FILE_TYPE.get(normalized, FileType.CODE)

def is_binary_extension(ext: str) -> bool:
    """
    Check if a file extension is typically associated with binary files.
    
    Args:
        ext: The file extension (with or without leading period)
        
    Returns:
        True if binary, False otherwise
    """
    if not ext.startswith('.'):
        ext = f'.{ext}'
    return ext.lower() in BINARY_EXTENSIONS

def detect_language_from_filename(filename: str) -> Optional[str]:
    """
    Detect language based on filename patterns.
    
    Args:
        filename: The filename to analyze
        
    Returns:
        Language identifier or None if not detected
    """
    # Check exact filename match first
    if filename in FILENAME_MAP:
        return FILENAME_MAP[filename]
    
    # Extract extension (with leading period)
    _, ext = os.path.splitext(filename)
    if ext and ext in FULL_EXTENSION_MAP:
        return FULL_EXTENSION_MAP[ext]
    
    # Check special patterns
    if filename.endswith('.config.js'):
        return 'javascript'
    elif filename.endswith('.config.ts'):
        return 'typescript'
    elif filename.startswith('docker-compose') and filename.endswith('.yml'):
        return 'yaml'
    
    # Convert to lowercase for remaining checks
    filename_lower = filename.lower()
    
    # Check for common config files
    if (filename_lower.endswith('rc') or 
        filename_lower.startswith('.') or 
        'config' in filename_lower):
        
        if filename_lower.endswith('.json'):
            return 'json'
        elif filename_lower.endswith('.yaml') or filename_lower.endswith('.yml'):
            return 'yaml'
        elif filename_lower.endswith('.toml'):
            return 'toml'
        elif filename_lower.endswith('.ini'):
            return 'ini'
    
    return None

def detect_language_from_content(content: str) -> Optional[str]:
    """
    Detect language based on file content analysis.
    
    Args:
        content: The file content to analyze
        
    Returns:
        Language identifier or None if not detected
    """
    if not content or not content.strip():
        return None
    
    # Check for shebang
    if content.startswith('#!'):
        match = SHEBANG_PATTERN.match(content)
        if match:
            interpreter = match.group(1).lower()
            if interpreter in SHEBANG_MAP:
                return SHEBANG_MAP[interpreter]
    
    # Check for XML declaration
    first_line = content.split('\n', 1)[0].strip()
    if first_line.startswith('<?xml'):
        return 'xml'
    
    # Check for PHP opening tag
    if first_line.startswith('<?php'):
        return 'php'
    
    # Sample beginning of file for analysis
    sample = content[:1000].lower()
    
    # Check for HTML
    if ('<html' in sample or 
        '<!doctype html' in sample or 
        '<head' in sample or 
        '<body' in sample):
        return 'html'
    
    # Check for markdown indicators
    if (sample.startswith('# ') or 
        '\n## ' in sample or 
        '\n### ' in sample or 
        sample.startswith('---\ntitle:')):
        return 'markdown'
    
    # Check for JSON structure
    if sample.strip().startswith('{') and (
        '"name":' in sample or 
        '"version":' in sample or
        '"dependencies":' in sample):
        return 'json'
    
    # Check for YAML structure
    if sample.startswith('---') and ':' in sample:
        return 'yaml'
    
    # Check for Python indicators
    if ('import ' in sample or 
        'from ' in sample and ' import ' in sample or
        'def ' in sample and '(' in sample or
        'class ' in sample and '(' in sample):
        return 'python'
    
    # Check for JavaScript indicators
    if ('function ' in sample or 
        'const ' in sample or 
        'let ' in sample or
        'import ' in sample and ' from ' in sample or
        'export ' in sample or
        'module.exports ' in sample):
        return 'javascript'
    
    return None

def get_language_features(language_id: str) -> LanguageFeatures:
    """
    Get the complete set of features for a specific language.
    
    Args:
        language_id: The language identifier
        
    Returns:
        LanguageFeatures object with language capabilities
    """
    normalized = normalize_language_name(language_id)
    
    # Get extensions for this language
    extensions = {ext for ext, lang in EXTENSION_TO_LANGUAGE.items() 
                 if lang == normalized}
    
    # Get parser type
    parser_type = get_parser_type(normalized)
    
    # Get mime types if available
    mime_types = MIME_TYPES.get(normalized, set())
    
    return LanguageFeatures(
        canonical_name=normalized,
        file_extensions=extensions,
        parser_type=parser_type,
        mime_types=mime_types
    )

def get_supported_languages() -> Dict[str, ParserType]:
    """
    Get a dictionary of all supported languages and their parser types.
    
    Returns:
        Dictionary with language IDs as keys and parser types as values
    """
    languages = {}
    
    # Add tree-sitter languages
    for lang in TREE_SITTER_LANGUAGES:
        languages[lang] = ParserType.TREE_SITTER
    
    # Add custom parser languages
    for lang in CUSTOM_PARSER_LANGUAGES:
        languages[lang] = ParserType.CUSTOM
    
    return languages

def get_supported_extensions() -> Dict[str, str]:
    """
    Get a dictionary of all supported file extensions and their corresponding languages.
    
    Returns:
        Dictionary with extensions as keys and language IDs as values
    """
    return EXTENSION_TO_LANGUAGE

def get_extensions_for_language(language_id: str) -> Set[str]:
    """
    Get all file extensions associated with a language.
    
    Args:
        language_id: The language to get extensions for
        
    Returns:
        Set of extensions without leading period
    """
    normalized = normalize_language_name(language_id)
    return {ext for ext, lang in EXTENSION_TO_LANGUAGE.items() 
           if lang == normalized}

def get_suggested_alternatives(language_id: str) -> List[str]:
    """
    Get suggested alternative languages if the requested one isn't available.
    Useful for fallback mechanisms.
    
    Args:
        language_id: The language to find alternatives for
        
    Returns:
        List of alternative language IDs
    """
    normalized = normalize_language_name(language_id)
    
    # Some common fallback patterns
    fallbacks = {
        'typescript': ['javascript'],
        'tsx': ['jsx', 'typescript', 'javascript'],
        'jsx': ['javascript'],
        'python': ['plaintext'],
        'c++': ['c'],
        'c#': ['c'],
        'html': ['xml', 'plaintext'],
        'xml': ['html', 'plaintext'],
        'yaml': ['plaintext'],
        'json': ['plaintext'],
        'markdown': ['plaintext'],
    }
    
    return fallbacks.get(normalized, ['plaintext'])

# NEW FUNCTIONS BELOW

def validate_language_mappings() -> List[str]:
    """
    Validate the consistency of all language mappings and return any inconsistencies found.
    
    Returns:
        List of validation error messages
    """
    errors = []
    
    # Check for languages in TREE_SITTER_LANGUAGES or CUSTOM_PARSER_LANGUAGES but not in EXTENSION_TO_LANGUAGE
    ts_missing = [lang for lang in TREE_SITTER_LANGUAGES 
                 if lang not in EXTENSION_TO_LANGUAGE.values() and lang not in LANGUAGE_ALIASES.values()]
    if ts_missing:
        errors.append(f"Languages in TREE_SITTER_LANGUAGES without extension mappings: {', '.join(ts_missing)}")
    
    custom_missing = [lang for lang in CUSTOM_PARSER_LANGUAGES 
                     if lang not in EXTENSION_TO_LANGUAGE.values() and lang not in LANGUAGE_ALIASES.values()]
    if custom_missing:
        errors.append(f"Languages in CUSTOM_PARSER_LANGUAGES without extension mappings: {', '.join(custom_missing)}")
    
    # Check for languages with conflicting file type mappings
    for lang, file_type in LANGUAGE_TO_FILE_TYPE.items():
        if lang in TREE_SITTER_LANGUAGES or lang in CUSTOM_PARSER_LANGUAGES:
            # Good, language is supported
            pass
        else:
            errors.append(f"Language '{lang}' has file type mapping but no parser support")
    
    return errors

def get_complete_language_info(language_id: str) -> Dict[str, Any]:
    """
    Get comprehensive information about a language from all relevant mappings.
    
    Args:
        language_id: The language identifier
        
    Returns:
        Dictionary with all available information about the language
    """
    normalized = normalize_language_name(language_id)
    
    # Get extensions for this language
    extensions = get_extensions_for_language(normalized)
    
    # Get parser type information
    parser_type = get_parser_type(normalized)
    fallback_type = get_fallback_parser_type(normalized)
    
    # Get file type
    file_type = get_file_type(normalized)
    
    # Get aliases
    aliases = [alias for alias, norm in LANGUAGE_ALIASES.items() if norm == normalized]
    
    # Get MIME types
    mime_types = MIME_TYPES.get(normalized, set())
    
    return {
        "canonical_name": normalized,
        "extensions": extensions,
        "parser_type": parser_type,
        "fallback_parser_type": fallback_type,
        "file_type": file_type,
        "aliases": aliases,
        "mime_types": mime_types,
        "is_tree_sitter_supported": normalized in TREE_SITTER_LANGUAGES,
        "is_custom_parser_supported": normalized in CUSTOM_PARSER_LANGUAGES
    }

def detect_language(file_path: str, content: Optional[str] = None) -> Tuple[str, float]:
    """
    Comprehensive language detection using multiple methods with confidence score.
    
    Args:
        file_path: Path to the file
        content: Optional content for content-based detection
        
    Returns:
        Tuple of (language_id, confidence_score)
    """
    # Start with filename-based detection
    filename = os.path.basename(file_path)
    language_by_filename = detect_language_from_filename(filename)
    
    if language_by_filename:
        return language_by_filename, 0.9  # High confidence for extension matches
    
    # Try content-based detection if content is provided
    if content:
        language_by_content = detect_language_from_content(content)
        if language_by_content:
            return language_by_content, 0.7  # Medium-high confidence for content matches
    
    # Try shebang detection for script files
    if content and content.startswith('#!'):
        match = SHEBANG_PATTERN.match(content)
        if match and match.group(1).lower() in SHEBANG_MAP:
            return SHEBANG_MAP[match.group(1).lower()], 0.8  # High confidence for shebang
    
    # Fall back to plaintext with low confidence
    return "plaintext", 0.1

def get_parser_info_for_language(language_id: str) -> Dict[str, Any]:
    """
    Get parser-specific information for a language.
    
    Args:
        language_id: The language identifier
        
    Returns:
        Dictionary with parser information for the language
    """
    normalized = normalize_language_name(language_id)
    parser_type = get_parser_type(normalized)
    fallback = get_fallback_parser_type(normalized)
    
    info = {
        "language_id": normalized,
        "parser_type": parser_type,
        "fallback_parser_type": fallback,
        "file_type": get_file_type(normalized)
    }
    
    # Add tree-sitter specific info if applicable
    if normalized in TREE_SITTER_LANGUAGES:
        info["tree_sitter_available"] = True
    
    # Add custom parser info if applicable
    if normalized in CUSTOM_PARSER_LANGUAGES:
        info["custom_parser_available"] = True
    
    return info
