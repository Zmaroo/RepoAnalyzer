from typing import Dict, Set, Optional, Tuple
from tree_sitter_language_pack import get_language, SupportedLanguage, get_binding, get_parser
import os
from utils.cache import cache  # Import our unified cache
from parsers.custom_parsers.custom_env_parser import parse_env_code
from parsers.custom_parsers.custom_plaintext_parser import parse_plaintext_code
from parsers.custom_parsers.custom_yaml_parser import parse_yaml_code
from parsers.custom_parsers.custom_markdown_parser import parse_markdown_code
from parsers.custom_parsers.custom_editorconfig_parser import parse_editorconfig_code
from parsers.custom_parsers.custom_graphql_parser import parse_graphql_code
from parsers.custom_parsers.custom_nim_parser import parse_nim_code
from parsers.custom_parsers.custom_ocaml_parser import parse_ocaml_ml_code, parse_ocaml_mli_code
from parsers.custom_parsers.custom_cobalt_parser import parse_cobalt
from parsers.custom_parsers.custom_xml_parser import parse_xml_code  # Add XML parser import
from parsers.custom_parsers.custom_html_parser import parse_html_code
from parsers.custom_parsers.custom_ini_parser import parse_ini_code
from parsers.custom_parsers.custom_json_parser import parse_json_code
from parsers.custom_parsers.custom_rst_parser import parse_rst_code
from parsers.custom_parsers.custom_toml_parser import parse_toml_code
from parsers.custom_parsers.custom_asciidoc_parser import parse_asciidoc_code
from dataclasses import dataclass, field
from enum import Enum

# Core language configuration
LANGUAGE_ALIASES = {
    # C and C++
    "c++": "cpp",
    "cplusplus": "cpp",
    "h": "c",
    "hpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    
    # C#
    "c#": "csharp",
    "cs": "csharp",
    
    # JavaScript/TypeScript
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    
    # Python
    "py": "python",
    "pyi": "python",
    "pyc": "python",
    
    # Ruby
    "rb": "ruby",
    "rake": "ruby",
    "gemspec": "ruby",
    
    # Shell
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    
    # Web
    "htm": "html",
    "xhtml": "html",
    "yml": "yaml",
    
    # JVM Languages
    "kt": "kotlin",
    "kts": "kotlin",
    "scala": "scala",
    "gradle": "groovy",
    
    # Documentation
    "markdown": "md",
    "rst": "restructuredtext",
    "rest": "restructuredtext",
    "asciidoc": "adoc",
    
    # Config
    "ini": "properties",
    "conf": "properties",
    "cfg": "properties",
    "dockerfil": "dockerfile",
    
    # Build Systems
    "mk": "make",
    "cmake": "cmake",
    "mak": "make",
    
    # Other
    "rs": "rust",
    "go": "go",
    "php": "php",
    "pl": "perl",
    "pm": "perl",
    "lua": "lua",
    "swift": "swift",
    "m": "objective-c",
    "mm": "objective-cpp",
    "ex": "elixir",
    "exs": "elixir",
    "erl": "erlang",
    "hrl": "erlang",
    "fs": "fsharp",
    "fsx": "fsharp",
    "fsi": "fsharp",
    "dart": "dart",
    "v": "verilog",
    "sv": "systemverilog",
    "r": "r",
    "rmd": "r",
    "jl": "julia",
    "zig": "zig"
}

# Map file extensions to tree-sitter language names.
EXTENSION_TO_LANGUAGE = {
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

    # --- Added mappings for files commonly encountered in tests ---
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'html': 'html',
    'ht': 'html',

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
    'svelte': 'svelte',
    'vue': 'vue',

    # OCaml custom support (handled by our custom OCaml parser)
    'ml': 'ocaml',
    'mli': 'ocaml_interface',

    # Previously "unsupported" languages (now mapped)
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

    # Bazel/Starlark related extensions
    'sky': 'starlark',

    # Additional file extension mappings
    'hack': 'hack',
    'hx': 'haxe',
    'nim': 'nim',

    # Updated mappings and special files
    'editorconfig': 'editorconfig',
    'env': 'env',
    'requirements': 'requirements',
    'gitignore': 'gitignore',
    'txt': 'plaintext',  # Plain text files

    # CMake files
    'cmake': 'cmake',
    'CMakeLists.txt': 'cmake',  # Special case for CMake build files
    'cmake.in': 'cmake', 

    # New entries for cobalt and pascal support.
    'cob': 'cobalt',
    'pas': 'pascal',

    # New XML-related mappings
    'html': 'html',  # HTML will use the XML parser
    'htm': 'html',   # Alternative HTML extension
    'xhtml': 'html', # XHTML files
    'xsd': 'xml',    # XML Schema files
    'adoc': 'asciidoc',    # AsciiDoc files
    'asciidoc': 'asciidoc',
    'rst': 'rst',          # reStructuredText files
    'rest': 'rst',
    'conf': 'ini',         # Configuration files
    'cfg': 'ini',
    'ini': 'ini',
    'properties': 'ini'
}

# Single source for special files
SPECIAL_FILENAMES = {
    'CMakeLists.txt': 'cmake',
    'Dockerfile': 'dockerfile',
    'BUILD': 'starlark',
    'BUILD.bazel': 'starlark',
    'WORKSPACE': 'starlark',
    'WORKSPACE.bazel': 'starlark',
    'requirements.txt': 'requirements',
    '.gitignore': 'gitignore',
    '.editorconfig': 'editorconfig',
    '.env': 'env',
}

def normalize_language_name(language: str) -> str:
    """Normalize a language name using LANGUAGE_ALIASES."""
    return LANGUAGE_ALIASES.get(language.lower().replace('-', '_'), language.lower())

def get_language_for_extension(ext: str) -> Optional[str]:
    """
    Given a file extension (including the dot), return the corresponding tree-sitter language name.
    The extension is assumed to be already in lower-case. If not found, return None.
    """
    if ext.startswith("."):
        ext = ext[1:]
    ext = ext.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)

def get_language_for_file(filepath: str) -> Optional[str]:
    """Single entry point for language detection."""
    filename = os.path.basename(filepath)
    
    # 1. Check special filenames
    if filename in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[filename]
    
    # 2. Check extensions
    ext = os.path.splitext(filename)[1].lstrip('.')
    if ext:
        return get_language_for_extension(ext)
    
    # 3. Content-based detection for ambiguous files
    return guess_language_by_content(filepath) or "plaintext"

class LanguageSupport:
    """Centralized language support management."""
    
    @staticmethod
    def is_supported(language_name: str) -> bool:
        """Check if a language is supported by tree-sitter or has a custom parser."""
        try:
            normalized = normalize_language_name(language_name)
            # Check for custom parser first
            if normalized in CUSTOM_PARSER_FUNCTIONS:
                return True
            # Then check tree-sitter support
            get_binding(normalized)
            get_language(normalized)
            get_parser(normalized)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_supported_languages() -> Set[str]:
        """Get set of all supported languages (tree-sitter + custom parsers)."""
        supported = set(CUSTOM_PARSER_FUNCTIONS.keys())
        for lang in EXTENSION_TO_LANGUAGE.values():
            normalized = normalize_language_name(lang)
            if LanguageSupport.is_supported(normalized):
                supported.add(normalized)
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
    "cobalt": parse_cobalt,
    "xml": parse_xml_code,  # Add XML parser mapping
    "html": parse_html_code,      # Use HTML-specific parser
    "ini": parse_ini_code,        # Use INI-specific parser
    "json": parse_json_code,      # Use JSON-specific parser
    "rst": parse_rst_code,        # Use RST-specific parser
    "toml": parse_toml_code,      # Use TOML-specific parser
    "asciidoc": parse_asciidoc_code  # Use AsciiDoc-specific parser
}

# === Additional Utility Functions for Language Mapping ===

def get_all_normalized_languages() -> set:
    """
    Derive a set of all normalized language names from the EXTENSION_TO_LANGUAGE mapping.
    This ensures there is a central list of supported languages without duplication.
    """
    return {normalize_language_name(lang) for lang in EXTENSION_TO_LANGUAGE.values()}

def guess_language_by_content(filepath: str) -> Optional[str]:
    """
    Heuristic: Read the first 1K bytes of the file to check for specific keywords (like 
    'cmake_minimum_required' or 'project(') indicating the 'cmake' language.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(1024)
        lower_content = content.lower()
        if "cmake_minimum_required" in lower_content or "project(" in lower_content:
            return "cmake"
    except Exception:
        pass
    return None

def get_supported_extensions() -> Tuple[Set[str], Set[str]]:
    """
    Get all supported extensions, categorized as code or documentation.
    
    Returns:
        Tuple of (code_extensions, doc_extensions)
    """
    code_ext = set()
    doc_ext = set()

    for ext, lang in EXTENSION_TO_LANGUAGE.items():
        normalized_lang = normalize_language_name(lang)
        ext_with_dot = f".{ext.lower()}" if not ext.startswith('.') else ext.lower()
        
        if normalized_lang == 'markup':
            # Use MARKUP_CLASSIFICATION to determine type
            if MARKUP_CLASSIFICATION.get(ext.lower()) == 'code':
                code_ext.add(ext_with_dot)
            else:
                doc_ext.add(ext_with_dot)
        elif LanguageSupport.is_supported(normalized_lang):
            code_ext.add(ext_with_dot)
            
    return (code_ext, doc_ext)

# Move MARKUP_CLASSIFICATION here from file_config.py
MARKUP_CLASSIFICATION = {
    # Code-like markup
    'html': 'code',
    'xml': 'code',
    'dockerfile': 'code',
    'makefile': 'code',
    
    # Documentation markup
    'md': 'doc',         # Markdown
    'markdown': 'doc',
    'rst': 'doc',        # reStructuredText
    'rest': 'doc',
    'adoc': 'doc',       # AsciiDoc
    'asciidoc': 'doc',
    'txt': 'doc',        # Plain text
    'yml': 'doc',        # YAML config
    'yaml': 'doc',
    'toml': 'doc',       # TOML config
    'ini': 'doc',        # INI config
    'conf': 'doc',       # Generic config
    'cfg': 'doc',        # Config files
    'properties': 'doc', # Java properties
    'json': 'doc',       # JSON config
    'gitignore': 'doc'   # Git config
}

def is_markup_code(file_ext: str) -> bool:
    """Determine if a markup file should be treated as code."""
    ext = file_ext.lower().lstrip('.')
    return MARKUP_CLASSIFICATION.get(ext) == 'code'

def is_markup_doc(file_ext: str) -> bool:
    """Determine if a markup file should be treated as documentation."""
    ext = file_ext.lower().lstrip('.')
    return MARKUP_CLASSIFICATION.get(ext) == 'doc'

class FileType(Enum):
    CODE = "code"
    DOC = "doc"
    BINARY = "binary"

@dataclass
class DocExtractionConfig:
    """Configuration for documentation extraction from files"""
    extract_docstrings: bool = False
    extract_comments: bool = False
    extract_type_hints: bool = False
    doc_sections: Set[str] = field(default_factory=set)  # e.g., {'Parameters', 'Returns', 'Examples'}

@dataclass
class CodeBlockConfig:
    """Configuration for code block extraction and parsing"""
    parse_blocks: bool = True
    validate_syntax: bool = True
    extract_imports: bool = True
    # Use existing language mappings instead of hardcoded set
    supported_languages: Set[str] = field(default_factory=lambda: set(EXTENSION_TO_LANGUAGE.values()))

    def is_language_supported(self, language: str) -> bool:
        """Check if a language is supported, accounting for aliases"""
        normalized = normalize_language_name(language.lower())
        return normalized in self.supported_languages or normalized in LANGUAGE_ALIASES

@dataclass
class FileClassification:
    """Configuration for file type classification"""
    file_type: FileType
    parser: str
    index_as_doc: bool = False
    code_block_config: Optional[CodeBlockConfig] = None
    doc_config: Optional[DocExtractionConfig] = None

# Single source of truth for file classification
FILE_CLASSIFICATION = {
    # Code files with rich documentation
    'py': FileClassification(
        file_type=FileType.CODE,
        parser="python",
        index_as_doc=True,
        doc_config=DocExtractionConfig(
            extract_docstrings=True,
            extract_comments=True,
            extract_type_hints=True,
            doc_sections={'Parameters', 'Returns', 'Examples', 'Raises'}
        )
    ),
    
    # Code files with simpler documentation
    'js': FileClassification(
        file_type=FileType.CODE,
        parser="javascript",
        index_as_doc=True,
        doc_config=DocExtractionConfig(
            extract_docstrings=True,
            extract_comments=True
        )
    ),
    
    # Pure documentation files
    'md': FileClassification(
        file_type=FileType.DOC,
        parser="custom_markdown",  # Using our custom parser
        index_as_doc=True,
        code_block_config=CodeBlockConfig()
    ),
    
    # Markup files treated as code
    'html': FileClassification(FileType.CODE, "html", index_as_doc=False),
    'xml': FileClassification(FileType.CODE, "xml", index_as_doc=False),
    
    # Config files
    'yml': FileClassification(FileType.CODE, "yaml", index_as_doc=True),
    'toml': FileClassification(FileType.CODE, "toml", index_as_doc=True),
    'json': FileClassification(FileType.CODE, "json", index_as_doc=True),
    
    # Special files
    'dockerfile': FileClassification(FileType.CODE, "dockerfile", index_as_doc=True),
    'makefile': FileClassification(FileType.CODE, "makefile", index_as_doc=True),
    'cmake': FileClassification(FileType.CODE, "cmake", index_as_doc=True),

    # Documentation formats that may contain code blocks
    'rst': FileClassification(
        file_type=FileType.DOC,
        parser="custom_rst",
        index_as_doc=True,
        code_block_config=CodeBlockConfig()
    ),
    'adoc': FileClassification(
        file_type=FileType.DOC,
        parser="custom_asciidoc",
        index_as_doc=True,
        code_block_config=CodeBlockConfig()
    ),
    'ipynb': FileClassification(
        file_type=FileType.DOC,
        parser="custom_jupyter",
        index_as_doc=True,
        code_block_config=CodeBlockConfig(
            supported_languages={'python', 'r', 'julia'}
        )
    )
}

# Special filenames (like CMakeLists.txt) get their own mapping
SPECIAL_FILENAME_CLASSIFICATION = {
    'CMakeLists.txt': FileClassification(FileType.CODE, "cmake", index_as_doc=True),
    'Dockerfile': FileClassification(FileType.CODE, "dockerfile", index_as_doc=True),
    '.gitignore': FileClassification(FileType.DOC, "gitignore", index_as_doc=True),
}

def get_file_classification(file_path: str) -> Optional[FileClassification]:
    """Single entry point for determining file classification"""
    filename = os.path.basename(file_path)
    
    # Check special filenames first
    if filename in SPECIAL_FILENAME_CLASSIFICATION:
        return SPECIAL_FILENAME_CLASSIFICATION[filename]
        
    # Then check extensions
    ext = os.path.splitext(filename)[1].lstrip('.')
    return FILE_CLASSIFICATION.get(ext.lower())