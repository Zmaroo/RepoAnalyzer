"""Language support registry and utilities."""

from typing import Dict, Optional, Set, Tuple, List
import os
from parsers.parser_interfaces import BaseParserInterface, ParserRegistryInterface
from parsers.models import FileClassification, LanguageFeatures, FileMetadata
from parsers.types import ParserType, FileType
from parsers.language_mapping import (
    TREE_SITTER_LANGUAGES,
    CUSTOM_PARSER_LANGUAGES,
    normalize_language_name,
    get_parser_type,
    get_file_type,
    get_fallback_parser_type,
    get_language_features,
    get_suggested_alternatives,
    get_complete_language_info,
    get_parser_info_for_language
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
    fallback_type: Optional[ParserType] = None

def get_parser_availability(language: str) -> ParserAvailability:
    """Get information about available parsers for a language."""
    normalized = normalize_language_name(language)
    
    # Use the new parser info function to get comprehensive parser information
    parser_info = get_parser_info_for_language(normalized)
    
    # Import here to avoid circular imports
    from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
    
    has_custom = normalized in CUSTOM_PARSER_CLASSES
    has_tree_sitter = normalized in TREE_SITTER_LANGUAGES
    
    return ParserAvailability(
        has_custom_parser=has_custom,
        has_tree_sitter=has_tree_sitter,
        preferred_type=parser_info["parser_type"],
        file_type=parser_info["file_type"],
        fallback_type=parser_info.get("fallback_parser_type")
    )

def determine_file_type(language: str) -> FileType:
    """Determine file type based on language."""
    # Use the get_file_type function from language_mapping
    return get_file_type(language)

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
            lines = content.splitlines()
            code_lines = len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))])
            doc_lines = len([l for l in lines if l.strip() and (l.strip().startswith(('#', '//', '/*', '*', '"""', "'''")) or l in docstring)])
            
            if doc_lines > code_lines * 0.5:
                return True, doc_type
    return False, ""

def get_language_by_extension(file_path: str) -> Optional[LanguageFeatures]:
    """
    Get language features for a file extension or path.
    
    RETURNS: LanguageFeatures if a language is identified, else None.
    """
    try:
        basename = os.path.basename(file_path)
        # Use the language mapping module to detect language
        from parsers.language_mapping import detect_language_from_filename
        language = detect_language_from_filename(basename)
        
        if language:
            return get_language_features(language)
        return None
    except Exception as e:
        log(f"Error getting language for path '{file_path}': {e}", level="error")
        return None

def get_extensions_for_language(language: str) -> Set[str]:
    """Get all file extensions associated with a language."""
    try:
        from parsers.language_mapping import get_extensions_for_language as get_exts
        return get_exts(language)
    except Exception as e:
        log(f"Error getting extensions for language '{language}': {e}", level="error")
        return set()

class LanguageRegistry(ParserRegistryInterface):
    """Registry for language parsers."""
    
    def __init__(self):
        self._parsers: Dict[str, BaseParserInterface] = {}
        self._fallback_parsers: Dict[str, BaseParserInterface] = {}

    def get_parser(self, classification: FileClassification) -> Optional[BaseParserInterface]:
        """
        Get the appropriate parser for a file classification.
        Will try the primary parser first, then fall back to alternatives if needed.
        """
        try:
            language = classification.language_id
            # Try to get an existing parser first
            if language in self._parsers:
                return self._parsers.get(language)
                
            # Create a parser if it doesn't exist
            parser = self._create_parser(language, classification.parser_type, classification.file_type)
            if parser:
                self._parsers[language] = parser
                return parser
            
            # If no parser could be created with specified type, try fallback
            # Use language_mapping to determine fallback parser type
            parser_info = get_parser_info_for_language(language)
            fallback_type = parser_info.get("fallback_parser_type")
            
            if fallback_type not in [ParserType.UNKNOWN, None]:
                # Check if we already have a fallback parser
                fallback_key = f"{language}_{fallback_type.name}"
                if fallback_key in self._fallback_parsers:
                    return self._fallback_parsers[fallback_key]
                    
                # Try to create a fallback parser
                fallback_parser = self._create_parser(language, fallback_type, classification.file_type)
                if fallback_parser:
                    self._fallback_parsers[fallback_key] = fallback_parser
                    log(f"Using fallback parser type {fallback_type} for {language}", level="info")
                    return fallback_parser
            
            # Try language alternatives as last resort
            for alt_language in get_suggested_alternatives(language):
                alt_parser_info = get_parser_info_for_language(alt_language)
                alt_parser = self.get_parser(FileClassification(
                    file_path=classification.file_path,
                    language_id=alt_language,
                    parser_type=alt_parser_info["parser_type"],
                    file_type=alt_parser_info["file_type"]
                ))
                if alt_parser:
                    log(f"Using alternative language {alt_language} parser for {language}", level="info")
                    return alt_parser
                    
            # No parser available
            return None
        except Exception as e:
            log(f"Error getting parser for {classification.language_id}: {e}", level="error")
            return None
    
    def _create_parser(self, language: str, parser_type: ParserType, file_type: FileType) -> Optional[BaseParserInterface]:
        """Create a new parser instance of the specified type."""
        try:
            # Import here to avoid circular imports
            from parsers.tree_sitter_parser import TreeSitterParser
            from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
            
            # Use the new parser info function to make decisions
            parser_info = get_parser_info_for_language(language)
            
            # Always prioritize custom parsers for languages that have them
            if parser_info.get("custom_parser_available", False):
                parser_cls = CUSTOM_PARSER_CLASSES.get(language)
                if parser_cls:
                    log(f"Using custom parser for {language} (prioritized over tree-sitter)", level="debug")
                    return parser_cls(language, file_type)
            
            # If no custom parser or not a custom parser language, follow the requested type
            if parser_type == ParserType.TREE_SITTER and parser_info.get("tree_sitter_available", False):
                return TreeSitterParser(language, file_type)
            elif parser_type == ParserType.CUSTOM and language in CUSTOM_PARSER_CLASSES:
                parser_cls = CUSTOM_PARSER_CLASSES.get(language)
                if parser_cls:
                    return parser_cls(language, file_type)
            
            return None
        except Exception as e:
            log(f"Error creating parser for {language} with type {parser_type}: {e}", level="error")
            return None

    def get_supported_languages(self) -> Dict[str, ParserType]:
        """Get all supported languages and their parser types."""
        from parsers.language_mapping import get_supported_languages as get_langs
        return get_langs()

    def cleanup(self):
        """Release all parser resources."""
        for p in self._parsers.values():
            p.cleanup()
        for p in self._fallback_parsers.values():
            p.cleanup()
        self._parsers.clear()
        self._fallback_parsers.clear()

# Global instance
language_registry = LanguageRegistry() 