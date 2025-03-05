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
from typing import Optional, Set, Dict, List, Tuple, Any, Union, Callable
import os
import re
import asyncio
from parsers.types import FileType, ParserType, AICapability, InteractionType, ConfidenceLevel
from parsers.models import LanguageFeatures
from utils.error_handling import AsyncErrorBoundary, handle_async_errors
from utils.shutdown import register_shutdown_handler

# Track initialization state and tasks
_initialized = False
_pending_tasks: Set[asyncio.Task] = set()

@handle_async_errors(error_types=(Exception,))
async def initialize():
    """Initialize language mapping resources."""
    global _initialized
    if not _initialized:
        try:
            async with AsyncErrorBoundary("language_mapping_initialization"):
                # Validate mappings
                task = asyncio.create_task(validate_language_mappings())
                _pending_tasks.add(task)
                try:
                    errors = await task
                    if errors:
                        for error in errors:
                            log(error, level="warning")
                finally:
                    _pending_tasks.remove(task)
                
                _initialized = True
                log("Language mapping initialized", level="info")
        except Exception as e:
            log(f"Error initializing language mapping: {e}", level="error")
            raise

@handle_async_errors(error_types=(Exception,))
async def detect_language(file_path: str, content: Optional[str] = None) -> Tuple[str, float]:
    """
    Comprehensive language detection using multiple methods with confidence score.
    
    Args:
        file_path: Path to the file
        content: Optional content for content-based detection
        
    Returns:
        Tuple of (language_id, confidence_score)
    """
    if not _initialized:
        await initialize()
        
    async with AsyncErrorBoundary("detect_language"):
        # Start with filename-based detection
        filename = os.path.basename(file_path)
        task = asyncio.create_task(detect_language_from_filename(filename))
        _pending_tasks.add(task)
        try:
            language_by_filename = await task
        finally:
            _pending_tasks.remove(task)
        
        if language_by_filename:
            return language_by_filename, 0.9  # High confidence for extension matches
        
        # Try content-based detection if content is provided
        if content:
            task = asyncio.create_task(detect_language_from_content(content))
            _pending_tasks.add(task)
            try:
                language_by_content = await task
                if language_by_content:
                    return language_by_content, 0.7  # Medium-high confidence for content matches
            finally:
                _pending_tasks.remove(task)
        
        # Try shebang detection for script files
        if content and content.startswith('#!'):
            match = SHEBANG_PATTERN.match(content)
            if match and match.group(1).lower() in SHEBANG_MAP:
                return SHEBANG_MAP[match.group(1).lower()], 0.8  # High confidence for shebang
        
        # Fall back to plaintext with low confidence
        return "plaintext", 0.1

@handle_async_errors(error_types=(Exception,))
async def get_complete_language_info(language_id: str) -> Dict[str, Any]:
    """
    Get comprehensive information about a language from all relevant mappings.
    
    Args:
        language_id: The language identifier
        
    Returns:
        Dictionary with all available information about the language
    """
    if not _initialized:
        await initialize()
        
    async with AsyncErrorBoundary("get_language_info"):
        normalized = normalize_language_name(language_id)
        
        # Get extensions for this language
        task = asyncio.create_task(get_extensions_for_language(normalized))
        _pending_tasks.add(task)
        try:
            extensions = await task
        finally:
            _pending_tasks.remove(task)
        
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

async def cleanup():
    """Clean up language mapping resources."""
    global _initialized
    try:
        # Clean up any pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*_pending_tasks, return_exceptions=True)
            _pending_tasks.clear()
        
        _initialized = False
        log("Language mapping cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up language mapping: {e}", level="error")

# Register cleanup handler
register_shutdown_handler(cleanup)

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

# [2.1] Tree-sitter supported languages
TREE_SITTER_LANGUAGES = {
    "python": {
        "extensions": {".py", ".pyi", ".pyx", ".pxd"},
        "parser_type": ParserType.TREE_SITTER,
        "file_type": FileType.CODE,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
    },
    "javascript": {
        "extensions": {".js", ".jsx", ".mjs"},
        "parser_type": ParserType.TREE_SITTER,
        "file_type": FileType.CODE,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
    },
    "typescript": {
        "extensions": {".ts", ".tsx"},
        "parser_type": ParserType.TREE_SITTER,
        "file_type": FileType.CODE,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
    }
}

# [2.2] Custom parser supported languages
CUSTOM_PARSER_LANGUAGES = {
    "plaintext": {
        "extensions": {".txt", ".text", ".log"},
        "parser_type": ParserType.CUSTOM,
        "file_type": FileType.DOC,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.DOCUMENTATION
        }
    },
    "markdown": {
        "extensions": {".md", ".markdown", ".mdown"},
        "parser_type": ParserType.CUSTOM,
        "file_type": FileType.DOC,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.DOCUMENTATION,
            AICapability.LEARNING
        }
    }
}

# [2.3] Language normalization mapping
LANGUAGE_NORMALIZATION = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "jsx": "javascript",
    "tsx": "typescript",
    "md": "markdown",
    "txt": "plaintext"
}

def normalize_language_name(language: str) -> str:
    """[2.4] Normalize a language name to its canonical form."""
    language = language.lower().strip()
    return LANGUAGE_NORMALIZATION.get(language, language)

def get_parser_type(language: str) -> ParserType:
    """[2.5] Get the preferred parser type for a language."""
    normalized = normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]["parser_type"]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]["parser_type"]
    
    return ParserType.UNKNOWN

def get_file_type(language: str) -> FileType:
    """[2.6] Get the file type for a language."""
    normalized = normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]["file_type"]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]["file_type"]
    
    return FileType.CODE

def get_ai_capabilities(language: str) -> Set[AICapability]:
    """[2.7] Get AI capabilities supported by a language."""
    normalized = normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]["ai_capabilities"]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]["ai_capabilities"]
    
    # Default capabilities for unknown languages
    return {AICapability.CODE_UNDERSTANDING}

def get_fallback_parser_type(language: str) -> Optional[ParserType]:
    """[2.8] Get the fallback parser type for a language."""
    normalized = normalize_language_name(language)
    
    # If tree-sitter is available, use custom as fallback
    if normalized in TREE_SITTER_LANGUAGES:
        return ParserType.CUSTOM
    
    # If custom is available, no fallback needed
    if normalized in CUSTOM_PARSER_LANGUAGES:
        return None
    
    return ParserType.UNKNOWN

def get_language_features(language: str) -> Dict[str, Any]:
    """[2.9] Get comprehensive language features."""
    normalized = normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]
    
    return {
        "extensions": set(),
        "parser_type": ParserType.UNKNOWN,
        "file_type": FileType.CODE,
        "ai_capabilities": {AICapability.CODE_UNDERSTANDING}
    }

def get_suggested_alternatives(language: str) -> List[str]:
    """[2.10] Get suggested alternative languages."""
    normalized = normalize_language_name(language)
    
    # Define language families
    language_families = {
        "javascript": ["typescript", "jsx"],
        "typescript": ["javascript", "tsx"],
        "python": ["nim", "cobra"],
        "markdown": ["asciidoc", "rst"],
        "plaintext": ["markdown", "rst"]
    }
    
    return language_families.get(normalized, [])

def detect_language_from_filename(filename: str) -> Optional[str]:
    """[2.11] Detect language from filename."""
    ext = os.path.splitext(filename)[1].lower()
    
    # Check tree-sitter languages
    for lang, info in TREE_SITTER_LANGUAGES.items():
        if ext in info["extensions"]:
            return lang
    
    # Check custom parser languages
    for lang, info in CUSTOM_PARSER_LANGUAGES.items():
        if ext in info["extensions"]:
            return lang
    
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

def get_extensions_for_language(language: str) -> Set[str]:
    """[2.12] Get file extensions for a language."""
    normalized = normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]["extensions"]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]["extensions"]
    
    return set()

def get_complete_language_info(language: str) -> Dict[str, Any]:
    """[2.13] Get complete language information."""
    normalized = normalize_language_name(language)
    
    base_info = {
        "canonical_name": normalized,
        "parser_type": get_parser_type(normalized),
        "file_type": get_file_type(normalized),
        "extensions": get_extensions_for_language(normalized),
        "ai_capabilities": get_ai_capabilities(normalized),
        "fallback_parser_type": get_fallback_parser_type(normalized),
        "alternatives": get_suggested_alternatives(normalized)
    }
    
    if normalized in TREE_SITTER_LANGUAGES:
        base_info.update(TREE_SITTER_LANGUAGES[normalized])
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        base_info.update(CUSTOM_PARSER_LANGUAGES[normalized])
    
    return base_info

def get_parser_info_for_language(language: str) -> Dict[str, Any]:
    """[2.14] Get parser-specific information for a language."""
    normalized = normalize_language_name(language)
    
    parser_info = {
        "parser_type": get_parser_type(normalized),
        "file_type": get_file_type(normalized),
        "ai_capabilities": get_ai_capabilities(normalized),
        "fallback_parser_type": get_fallback_parser_type(normalized)
    }
    
    if normalized in TREE_SITTER_LANGUAGES:
        parser_info.update({
            "is_tree_sitter": True,
            "tree_sitter_info": TREE_SITTER_LANGUAGES[normalized]
        })
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        parser_info.update({
            "is_custom": True,
            "custom_info": CUSTOM_PARSER_LANGUAGES[normalized]
        })
    
    return parser_info

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

# MIME type mappings for common languages
MIME_TYPES: Dict[str, str] = {
    'python': 'text/x-python',
    'javascript': 'application/javascript',
    'typescript': 'application/typescript',
    'java': 'text/x-java-source',
    'c': 'text/x-c',
    'cpp': 'text/x-c++',
    'go': 'text/x-go',
    'rust': 'text/x-rust',
    'ruby': 'text/x-ruby',
    'php': 'text/x-php',
    'html': 'text/html',
    'css': 'text/css',
    'json': 'application/json',
    'yaml': 'text/yaml',
    'xml': 'text/xml',
    'markdown': 'text/markdown',
    'shell': 'text/x-shellscript',
    'sql': 'text/x-sql'
}

# Language to file type mappings
LANGUAGE_TO_FILE_TYPE: Dict[str, FileType] = {
    'python': FileType.CODE,
    'javascript': FileType.CODE,
    'typescript': FileType.CODE,
    'java': FileType.CODE,
    'c': FileType.CODE,
    'cpp': FileType.CODE,
    'go': FileType.CODE,
    'rust': FileType.CODE,
    'ruby': FileType.CODE,
    'php': FileType.CODE,
    'html': FileType.MARKUP,
    'css': FileType.STYLE,
    'json': FileType.DATA,
    'yaml': FileType.DATA,
    'xml': FileType.MARKUP,
    'markdown': FileType.DOCUMENTATION,
    'shell': FileType.SCRIPT,
    'sql': FileType.QUERY,
    'text': FileType.TEXT,
    'binary': FileType.BINARY,
    'unknown': FileType.UNKNOWN
}

def get_pattern_capabilities(language: str) -> Dict[str, Any]:
    """Get pattern-related capabilities for a language."""
    normalized = normalize_language_name(language)
    capabilities = {
        "pattern_learning": True,
        "deep_learning": language in TREE_SITTER_LANGUAGES,
        "cross_repo_analysis": language in TREE_SITTER_LANGUAGES
    }
    return capabilities
