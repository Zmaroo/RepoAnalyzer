"""Language support registry and utilities."""

from typing import Dict, Optional, Set, Tuple
import os
from parsers.parser_interfaces import BaseParserInterface, ParserRegistryInterface
from parsers.models import FileClassification, LanguageFeatures, FileMetadata
from parsers.types import ParserType, FileType
from parsers.language_mapping import (
    TREE_SITTER_LANGUAGES,
    EXTENSION_TO_LANGUAGE,
    CUSTOM_PARSER_LANGUAGES,
    normalize_language_name
)
from utils.logger import log
from dataclasses import dataclass
import re

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
    
    # Import here to avoid circular imports
    from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
    
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
        
    module_docstring_match = re.match(
        r'^(\'\'\'|""")[\s\S]+?\1',
        content.strip()
    )
    
    if module_docstring_match:
        docstring = module_docstring_match.group(0)
        doc_indicators = {
            'example': r'example.*usage|usage.*example',
            'api_doc': r'api reference|available methods|public interface',
            'guide': r'guide|tutorial|how to|overview',
            'schema': r'schema|structure|format|specification'
        }
        
        doc_type = None
        for dtype, pattern in doc_indicators.items():
            if re.search(pattern, docstring.lower()):
                doc_type = dtype
                break
                
        if doc_type:
            code_lines = len([l for l in content.splitlines() if l.strip() and not l.strip().startswith(('#', '"', "'"))])
            doc_lines = len([l for l in content.splitlines() if l.strip() and (l.strip().startswith(('#', '"', "'")) or l in docstring)])
            
            if doc_lines > code_lines * 0.5:
                return True, doc_type
    return False, ""

def get_language_by_extension(file_path: str) -> Optional[LanguageFeatures]:
    """
    Get language features for a file extension or path.
    
    RETURNS: LanguageFeatures if a language is identified, else None.
    """
    try:
        ext = os.path.splitext(file_path)[1].lstrip('.').lower()
        language = EXTENSION_TO_LANGUAGE.get(ext)
        if language:
            normalized = normalize_language_name(language)
            parser_type = (
                ParserType.CUSTOM if normalized in CUSTOM_PARSER_LANGUAGES
                else ParserType.TREE_SITTER if normalized in TREE_SITTER_LANGUAGES
                else ParserType.UNKNOWN
            )
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
        return {ext for ext, lang in EXTENSION_TO_LANGUAGE.items() if lang == normalized}
    except Exception as e:
        log(f"Error getting extensions for language '{language}': {e}", level="error")
        return set()

class LanguageRegistry(ParserRegistryInterface):
    """Registry for language parsers."""
    
    def __init__(self):
        self._parsers: Dict[str, BaseParserInterface] = {}

    def get_parser(self, classification: FileClassification) -> Optional[BaseParserInterface]:
        try:
            language = classification.language_id
            if language not in self._parsers:
                # Import here to avoid circular imports
                from parsers.tree_sitter_parser import TreeSitterParser
                from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
                
                if classification.parser_type == ParserType.TREE_SITTER:
                    self._parsers[language] = TreeSitterParser(language, classification.file_type)
                elif classification.parser_type == ParserType.CUSTOM:
                    parser_cls = CUSTOM_PARSER_CLASSES.get(language)
                    if parser_cls:
                        self._parsers[language] = parser_cls(language, classification.file_type)
            return self._parsers.get(language)
        except Exception as e:
            log(f"Error getting parser for {classification.language_id}: {e}", level="error")
            return None

    def cleanup(self):
        for p in self._parsers.values():
            p.cleanup()
        self._parsers.clear()

# Global instance
language_registry = LanguageRegistry() 