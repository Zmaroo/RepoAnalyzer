"""Language support registry and utilities."""

from typing import Dict, Optional, Set, Tuple
import os
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import TreeSitterParser
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from parsers.models import (
    FileClassification,
    LanguageFeatures,
    ParserType,
    FileType,
    FileMetadata,
    language_registry
)
from parsers.language_mapping import (
    TREE_SITTER_LANGUAGES,
    EXTENSION_TO_LANGUAGE,
    CUSTOM_PARSER_LANGUAGES,
    normalize_language_name
)
from utils.logger import log
from dataclasses import dataclass
import re
from .language_mapping import normalize_language_name

@dataclass
class ParserAvailability:
    """Information about available parsers for a language."""
    has_custom_parser: bool
    has_tree_sitter: bool
    preferred_type: ParserType
    file_type: FileType

def get_parser_availability(language: str) -> ParserAvailability:
    """Get information about available parsers for a language."""
    normalized = normalize_language_name(language)
    has_custom = normalized in CUSTOM_PARSER_CLASSES
    has_tree_sitter = normalized in TREE_SITTER_LANGUAGES
    
    return ParserAvailability(
        has_custom_parser=has_custom,
        has_tree_sitter=has_tree_sitter,
        preferred_type=(
            ParserType.CUSTOM if has_custom
            else ParserType.TREE_SITTER if has_tree_sitter
            else ParserType.UNKNOWN
        ),
        file_type=determine_file_type(normalized)
    )

def determine_file_type(language: str) -> FileType:
    """Determine file type based on language."""
    if language in {'markdown', 'restructuredtext', 'asciidoc', 'html', 'xml'}:
        return FileType.DOC
    elif language in {'json', 'yaml', 'toml', 'ini', 'env', 'editorconfig'}:
        return FileType.CONFIG
    elif language in {'csv', 'tsv', 'sql'}:
        return FileType.DATA
    else:
        return FileType.CODE

def is_documentation_code(file_path: str, content: Optional[str] = None) -> Tuple[bool, str]:
    """
    Determines if a code file serves primarily as documentation by analyzing:
    1. File content (if provided)
    2. Module-level docstring size and content
    3. Code-to-documentation ratio
    4. Documentation patterns (e.g., extensive examples, usage guides)
    
    Returns:
    - (is_doc: bool, doc_type: str)
    """
    if not content:
        return False, ""
        
    # Check for large module-level docstring
    module_docstring_match = re.match(
        r'^(\'\'\'|""")[\s\S]+?\1',
        content.strip()
    )
    
    if module_docstring_match:
        docstring = module_docstring_match.group(0)
        
        # Documentation indicators in docstring
        doc_indicators = {
            'example': r'example.*usage|usage.*example',
            'api_doc': r'api reference|available methods|public interface',
            'guide': r'guide|tutorial|how to|overview',
            'schema': r'schema|structure|format|specification'
        }
        
        # Check docstring content
        doc_type = None
        for dtype, pattern in doc_indicators.items():
            if re.search(pattern, docstring.lower()):
                doc_type = dtype
                break
                
        # If significant documentation found
        if doc_type:
            # Calculate code/doc ratio
            code_lines = len([l for l in content.splitlines() 
                            if l.strip() and not l.strip().startswith(('#', '"', "'"))])
            doc_lines = len([l for l in content.splitlines() 
                           if l.strip() and (l.strip().startswith(('#', '"', "'")) or l in docstring)])
            
            # If documentation is significant portion of file
            if doc_lines > code_lines * 0.5:  # Configurable threshold
                return True, doc_type
    
    return False, ""

def get_language_by_extension(file_path: str) -> Optional[LanguageFeatures]:
    """
    Get language features for a file extension or path.
    
    The actual classification of content (code vs documentation) is handled by
    PATTERN_CATEGORIES during parsing, which extracts both code and documentation
    features from any file type. This function focuses on selecting the appropriate
    parser to extract those features.
    """
    try:
        # [1.2.1] Extension Extraction
        # USES: [os.path] splitext() -> Tuple[str, str]
        ext = os.path.splitext(file_path)[1].lstrip('.').lower()
        
        # [1.2.2] Language Lookup
        # USES: [language_mapping.py] EXTENSION_TO_LANGUAGE -> Dict[str, str]
        language = EXTENSION_TO_LANGUAGE.get(ext)
        if language:
            # [1.2.3] Name Normalization
            # USES: [language_mapping.py] LANGUAGE_ALIASES -> Dict[str, str]
            normalized = normalize_language_name(language)
            
            # [1.2.4] Parser Type Resolution
            # USES: [language_mapping.py] TREE_SITTER_LANGUAGES, CUSTOM_PARSER_LANGUAGES -> Set[str]
            parser_type = (
                ParserType.CUSTOM if normalized in CUSTOM_PARSER_CLASSES
                else ParserType.TREE_SITTER if normalized in TREE_SITTER_LANGUAGES
                else ParserType.UNKNOWN
            )
            
            # RETURNS: [models.py] LanguageFeatures
            return LanguageFeatures(
                canonical_name=normalized,
                file_extensions={ext},
                parser_type=parser_type
            )
        return None
    except Exception as e:
        log(f"Error getting language for path '{file_path}': {e}", level="error")
        return None

def get_extensions_for_language(language: str) -> Set[str]:
    """Get all file extensions associated with a language."""
    try:
        if language == "*":
            return set(EXTENSION_TO_LANGUAGE.keys())
        normalized = normalize_language_name(language)
        return {ext for ext, lang in EXTENSION_TO_LANGUAGE.items() 
                if lang == normalized}
    except Exception as e:
        log(f"Error getting extensions for language '{language}': {e}", level="error")
        return set()

class LanguageRegistry:
    """Central registry for language support."""
    
    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {}
        
    def get_parser(self, file_classification: FileClassification) -> Optional[BaseParser]:
        """Get appropriate parser for language."""
        try:
            # [2.1.1] Normalize Language
            # USES: [language_support.py] normalize_language_name() -> str
            language_id = normalize_language_name(file_classification.language_id)
            
            # [2.1.2] Check Parser Cache
            if language_id in self._parsers:
                return self._parsers[language_id]
            
            # [2.1.3] Create Parser Instance
            # USES: [tree_sitter_parser.py] TreeSitterParser
            # USES: [custom_parsers/__init__.py] CUSTOM_PARSER_CLASSES
            parser = None
            if language_id in TREE_SITTER_LANGUAGES:
                parser = TreeSitterParser(language_id, file_classification.file_type)
            elif language_id in CUSTOM_PARSER_CLASSES:
                parser_class = CUSTOM_PARSER_CLASSES[language_id]
                parser = parser_class(language_id, file_classification.file_type)
            
            # [2.1.4] Initialize and Cache
            # USES: [base_parser.py] BaseParser.initialize() -> bool
            if parser and parser.initialize():
                self._parsers[language_id] = parser
                return parser
                
            return None
            
        except Exception as e:
            log(f"Error getting parser: {e}", level="error")
            return None

    def cleanup(self):
        """Clean up all parser instances."""
        for parser in self._parsers.values():
            parser.cleanup()
        self._parsers.clear()

# Global instance
language_registry = LanguageRegistry() 