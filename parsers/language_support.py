"""Language support registry and utilities."""
from typing import Dict, Optional, Set, Tuple, List
import os
from parsers.parser_interfaces import BaseParserInterface, ParserRegistryInterface
from parsers.models import FileClassification, LanguageFeatures, FileMetadata
from parsers.types import ParserType, FileType
from parsers.language_mapping import TREE_SITTER_LANGUAGES, CUSTOM_PARSER_LANGUAGES, normalize_language_name, get_parser_type, get_file_type, get_fallback_parser_type, get_language_features, get_suggested_alternatives, get_complete_language_info, get_parser_info_for_language
from utils.logger import log
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary
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


@handle_errors(error_types=(Exception,))
def get_parser_availability(language: str) ->ParserAvailability:
    """Get information about available parsers for a language."""
    normalized = normalize_language_name(language)
    parser_info = get_parser_info_for_language(normalized)
    from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
    has_custom = normalized in CUSTOM_PARSER_CLASSES
    has_tree_sitter = normalized in TREE_SITTER_LANGUAGES
    return ParserAvailability(has_custom_parser=has_custom, has_tree_sitter
        =has_tree_sitter, preferred_type=parser_info['parser_type'],
        file_type=parser_info['file_type'], fallback_type=parser_info.get(
        'fallback_parser_type'))

@handle_errors(error_types=(Exception,))

def determine_file_type(language: str) ->FileType:
    """Determine file type based on language."""
    return get_file_type(language)
@handle_errors(error_types=(Exception,))


def is_documentation_code(file_path: str, content: Optional[str]=None) ->Tuple[
    bool, str]:
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
        return False, ''
    module_docstring_match = re.match('^(\\\'\\\'\\\'|""")[\\s\\S]+?\\1',
        content.strip())
    if module_docstring_match:
        docstring = module_docstring_match.group(0)
        doc_indicators = {'example': 'example.*usage|usage.*example',
            'api_doc': 'api reference|available methods|public interface',
            'guide': 'guide|tutorial|how to|overview', 'schema':
            'schema|structure|format|specification'}
        doc_type = None
        for dtype, pattern in doc_indicators.items():
            if re.search(pattern, docstring.lower()):
                doc_type = dtype
                break
        if doc_type:
            lines = content.splitlines()
            code_lines = len([l for l in lines if l.strip() and not l.strip
                ().startswith(('#', '//', '/*', '*', '"""', "'''"))])
            doc_lines = len([l for l in lines if l.strip() and (l.strip().
                startswith(('#', '//', '/*', '*', '"""', "'''")) or l in
                docstring)])
            if doc_lines > code_lines * 0.5:
                return True, doc_type
    return False, ''


def get_language_by_extension(file_path: str) ->Optional[LanguageFeatures]:
    """
    Get language features for a file extension or path.
    
    RETURNS: LanguageFeatures if a language is identified, else None.
    """
    basename = os.path.basename(file_path)
    with ErrorBoundary(f'get_language_for_path_{basename}', error_types=(
        Exception,)):
        from parsers.language_mapping import detect_language_from_filename
        language = detect_language_from_filename(basename)
        if language:
            return get_language_features(language)
    return None


def get_extensions_for_language(language: str) ->Set[str]:
    """Get all file extensions associated with a language."""
    with ErrorBoundary(f'get_extensions_for_{language}', error_types=(
        Exception,)):
        from parsers.language_mapping import get_extensions_for_language as get_exts
        return get_exts(language)
    return set()


class LanguageRegistry(ParserRegistryInterface):
    """Registry for language parsers."""

    def __init__(self):
        self._parsers: Dict[str, BaseParserInterface] = {}
        self._fallback_parsers: Dict[str, BaseParserInterface] = {}

    def get_parser(self, classification: FileClassification) ->Optional[
        BaseParserInterface]:
        """
        Get the appropriate parser for a file classification.
        Will try the primary parser first, then fall back to alternatives if needed.
        """
        language = classification.language_id
        with ErrorBoundary(f'get_parser_{language}', error_types=(Exception,)):
            if language in self._parsers:
                return self._parsers.get(language)
            parser = self._create_parser(language, classification.
                parser_type, classification.file_type)
            if parser:
                self._parsers[language] = parser
                return parser
            parser_info = get_parser_info_for_language(language)
            fallback_type = parser_info.get('fallback_parser_type')
            if fallback_type not in [ParserType.UNKNOWN, None]:
                fallback_key = f'{language}_{fallback_type.name}'
                if fallback_key in self._fallback_parsers:
                    return self._fallback_parsers[fallback_key]
                fallback_parser = self._create_parser(language,
                    fallback_type, classification.file_type)
                if fallback_parser:
                    self._fallback_parsers[fallback_key] = fallback_parser
                    log(f'Using fallback parser type {fallback_type} for {language}'
                        , level='info')
                    return fallback_parser
            for alt_language in get_suggested_alternatives(language):
                alt_parser_info = get_parser_info_for_language(alt_language)
                alt_parser = self.get_parser(FileClassification(file_path=
                    classification.file_path, language_id=alt_language,
                    parser_type=alt_parser_info['parser_type'], file_type=
                    alt_parser_info['file_type']))
                if alt_parser:
                    log(f'Using alternative language {alt_language} parser for {language}'
                        , level='info')
                    return alt_parser
        return None

    def _create_parser(self, language: str, parser_type: ParserType,
        file_type: FileType) ->Optional[BaseParserInterface]:
        """Create a new parser instance of the specified type."""
        with ErrorBoundary(f'create_parser_{language}_{parser_type.name}',
            error_types=(Exception,)):
            from parsers.tree_sitter_parser import TreeSitterParser
            from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
            parser_info = get_parser_info_for_language(language)
            if parser_info.get('custom_parser_available', False):
                parser_cls = CUSTOM_PARSER_CLASSES.get(language)
                if parser_cls:
                    log(f'Using custom parser for {language} (prioritized over tree-sitter)'
                        , level='debug')
                    return parser_cls(language, file_type)
            if parser_type == ParserType.TREE_SITTER and parser_info.get(
                'tree_sitter_available', False):
                return TreeSitterParser(language, file_type)
            elif parser_type == ParserType.CUSTOM and language in CUSTOM_PARSER_CLASSES:
                parser_cls = CUSTOM_PARSER_CLASSES.get(language)
                if parser_cls:
@handle_errors(error_types=(Exception,))
                    return parser_cls(language, file_type)
        return None

    def get_supported_languages(self) ->Dict[str, ParserType]:
@handle_errors(error_types=(Exception,))
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


language_registry = LanguageRegistry()
