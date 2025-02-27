"""
File classification and language detection module.

This module provides tools for classifying files based on their content and extension,
determining the appropriate parser type, and extracting language information.
"""

import os
import re
from typing import Dict, Optional, Tuple, List, Set

from parsers.models import FileClassification
from parsers.types import ParserType
from parsers.language_mapping import (
    TREE_SITTER_LANGUAGES,
    CUSTOM_PARSER_LANGUAGES,
    normalize_language_name,
    is_supported_language,
    EXTENSION_TO_LANGUAGE
)
from utils.logger import log

# File extension to language mapping
EXTENSION_MAP = {
    # Programming languages
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.java': 'java',
    '.c': 'c',
    '.cpp': 'cpp',
    '.h': 'cpp',
    '.hpp': 'cpp',
    '.cs': 'csharp',
    '.go': 'go',
    '.rb': 'ruby',
    '.php': 'php',
    '.rs': 'rust',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.scala': 'scala',
    '.m': 'objc',
    '.mm': 'objc',
    '.lua': 'lua',
    '.r': 'r',
    '.pl': 'perl',
    '.sh': 'shell',
    '.bash': 'shell',
    '.zsh': 'shell',
    '.ps1': 'powershell',
    '.elm': 'elm',
    '.exs': 'elixir',
    '.ex': 'elixir',
    '.erl': 'erlang',
    '.hrl': 'erlang',
    '.dart': 'dart',
    '.jl': 'julia',
    '.groovy': 'groovy',
    '.hs': 'haskell',
    '.ml': 'ocaml',
    '.mli': 'ocaml_interface',
    '.nim': 'nim',
    '.zig': 'zig',
    
    # Web formats
    '.html': 'html',
    '.htm': 'html',
    '.css': 'css',
    '.scss': 'css',
    '.sass': 'css',
    '.less': 'css',
    '.xml': 'xml',
    '.svg': 'xml',
    '.json': 'json',
    '.graphql': 'graphql',
    '.gql': 'graphql',
    '.vue': 'vue',
    '.svelte': 'svelte',
    
    # Config formats
    '.yml': 'yaml',
    '.yaml': 'yaml',
    '.toml': 'toml',
    '.ini': 'ini',
    '.cfg': 'ini',
    '.conf': 'ini',
    '.env': 'env',
    '.editorconfig': 'editorconfig',
    
    # Documentation formats
    '.md': 'markdown',
    '.markdown': 'markdown',
    '.rst': 'rst',
    '.adoc': 'asciidoc',
    '.asciidoc': 'asciidoc',
    '.txt': 'plaintext',
    
    # Other formats
    '.sql': 'sql',
    '.proto': 'proto',
    '.cmake': 'cmake',
    '.makefile': 'make',
    '.mk': 'make',
    '.Makefile': 'make',
    '.dockerfile': 'dockerfil',
    '.Dockerfile': 'dockerfil',
    '.tex': 'latex',
    '.bib': 'bibtex',
    '.asm': 'asm',
    '.s': 'asm',
    '.clj': 'clojure',
    '.cob': 'cobalt',
}

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

def classify_file(file_path: str, content: Optional[str] = None) -> FileClassification:
    """
    Classify a file based on its path and optionally its content.
    
    Args:
        file_path: Path to the file
        content: Optional file content for more accurate classification
        
    Returns:
        FileClassification object with parser type and language information
    """
    # Get base filename and extension
    basename = os.path.basename(file_path)
    _, ext = os.path.splitext(basename)
    
    # Check if this is a special filename
    if basename in FILENAME_MAP:
        language_id = FILENAME_MAP[basename]
    # Otherwise use extension mapping
    elif ext in EXTENSION_MAP:
        language_id = EXTENSION_MAP[ext]
    else:
        # Try to infer from filename
        language_id = _infer_language_from_filename(basename)
    
    # If we have content and no language yet, try content-based detection
    if content and (not language_id or language_id == 'plaintext'):
        detected_lang = _detect_language_from_content(content)
        if detected_lang:
            language_id = detected_lang
    
    # If still no language, default to plaintext
    if not language_id:
        language_id = 'plaintext'
    
    # Normalize language name
    language_id = normalize_language_name(language_id)
    
    # Determine parser type
    parser_type = _get_parser_type(language_id)
    
    # Create classification
    classification = FileClassification(
        file_path=file_path,
        language_id=language_id,
        parser_type=parser_type,
        is_binary=_is_likely_binary(file_path, content),
    )
    
    return classification

def _get_parser_type(language_id: str) -> ParserType:
    """
    Determine the parser type for a given language.
    
    Args:
        language_id: The language identifier
        
    Returns:
        ParserType enum value (TREE_SITTER or CUSTOM)
    """
    if language_id in TREE_SITTER_LANGUAGES:
        return ParserType.TREE_SITTER
    elif language_id in CUSTOM_PARSER_LANGUAGES:
        return ParserType.CUSTOM
    else:
        # Default to custom parser for unknown languages
        return ParserType.CUSTOM

def _infer_language_from_filename(filename: str) -> Optional[str]:
    """
    Try to infer language from filename patterns.
    
    Args:
        filename: The filename to analyze
        
    Returns:
        Language identifier or None if not detected
    """
    # Common patterns
    if filename.endswith('.config.js'):
        return 'javascript'
    elif filename.endswith('.config.ts'):
        return 'typescript'
    elif filename.startswith('docker-compose') and filename.endswith('.yml'):
        return 'yaml'
    elif filename == 'package.json':
        return 'json'
    elif filename == 'tsconfig.json':
        return 'json'
    
    return None

def _detect_language_from_content(content: str) -> Optional[str]:
    """
    Try to detect language from file content.
    
    Args:
        content: File content
        
    Returns:
        Language identifier or None if not detected
    """
    # Check for shebang at the beginning
    if content and content.startswith('#!'):
        match = SHEBANG_PATTERN.match(content)
        if match:
            interpreter = match.group(1).lower()
            if interpreter in SHEBANG_MAP:
                return SHEBANG_MAP[interpreter]
    
    # Check for common file markers
    if content and content.strip():
        first_line = content.split('\n', 1)[0]
        if first_line.startswith('<?xml'):
            return 'xml'
        elif first_line.startswith('<?php'):
            return 'php'
        elif '<html' in content.lower()[:1000]:
            return 'html'
    
    return None

def _is_likely_binary(file_path: str, content: Optional[str] = None) -> bool:
    """
    Determine if a file is likely binary.
    
    Args:
        file_path: Path to the file
        content: Optional file content
        
    Returns:
        True if likely binary, False otherwise
    """
    # Check extension first
    _, ext = os.path.splitext(file_path)
    binary_extensions = {
        '.bin', '.exe', '.dll', '.so', '.dylib', '.obj', '.o', '.class',
        '.jar', '.war', '.ear', '.zip', '.tar', '.gz', '.7z', '.rar',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.webp',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.db', '.sqlite', '.pyc', '.pyd', '.pyo'
    }
    
    if ext.lower() in binary_extensions:
        return True
    
    # If content provided, check for null bytes
    if content:
        # Check sample of content for null bytes
        sample = content[:4096] if len(content) > 4096 else content
        if '\0' in sample:
            return True
    
    return False

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
    return EXTENSION_MAP 