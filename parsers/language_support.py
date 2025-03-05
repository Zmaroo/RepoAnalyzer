"""Language support registry and utilities."""

from typing import Dict, Optional, Set, Tuple, List
import asyncio
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
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary, ErrorSeverity, handle_async_errors
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
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
    basename = os.path.basename(file_path)
    
    with ErrorBoundary(f"get_language_for_path_{basename}", error_types=(Exception,)):
        # Use the language mapping module to detect language
        from parsers.language_mapping import detect_language_from_filename
        language = detect_language_from_filename(basename)
        
        if language:
            return get_language_features(language)
    
    return None

def get_extensions_for_language(language: str) -> Set[str]:
    """Get all file extensions associated with a language."""
    with ErrorBoundary(f"get_extensions_for_{language}", error_types=(Exception,)):
        from parsers.language_mapping import get_extensions_for_language as get_exts
        return get_exts(language)
    
    return set()

class LanguageRegistry(ParserRegistryInterface):
    """Registry for language parsers."""
    
    def __init__(self):
        self._parsers: Dict[str, BaseParserInterface] = {}
        self._fallback_parsers: Dict[str, BaseParserInterface] = {}
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """Initialize language registry resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("language registry initialization"):
                    # Initialize parsers for commonly used languages
                    common_languages = {"python", "javascript", "typescript", "java", "cpp"}
                    for language in common_languages:
                        if language in TREE_SITTER_LANGUAGES or language in CUSTOM_PARSER_LANGUAGES:
                            parser_info = get_parser_info_for_language(language)
                            classification = FileClassification(
                                language_id=language,
                                parser_type=parser_info["parser_type"],
                                file_type=parser_info["file_type"]
                            )
                            future = submit_async_task(self._create_parser(
                                language, 
                                classification.parser_type,
                                classification.file_type
                            ))
                            self._pending_tasks.add(future)
                            try:
                                parser = await asyncio.wrap_future(future)
                                if parser:
                                    self._parsers[language] = parser
                            finally:
                                self._pending_tasks.remove(future)
                    
                    self._initialized = True
                    log("Language registry initialized", level="info")
            except Exception as e:
                log(f"Error initializing language registry: {e}", level="error")
                raise

    @handle_async_errors(error_types=(Exception,))
    async def get_parser(self, classification: FileClassification) -> Optional[BaseParserInterface]:
        """
        Get the appropriate parser for a file classification.
        Will try the primary parser first, then fall back to alternatives if needed.
        """
        if not self._initialized:
            await self.initialize()
            
        language = classification.language_id
        
        async with AsyncErrorBoundary(f"get_parser_{language}", error_types=(Exception,)):
            # Try to get an existing parser first
            if language in self._parsers:
                return self._parsers.get(language)
                
            # Create a parser if it doesn't exist
            future = submit_async_task(self._create_parser(
                language, 
                classification.parser_type,
                classification.file_type
            ))
            self._pending_tasks.add(future)
            try:
                parser = await asyncio.wrap_future(future)
                if parser:
                    self._parsers[language] = parser
                    return parser
            finally:
                self._pending_tasks.remove(future)
            
            # If no parser could be created with specified type, try fallback
            parser_info = get_parser_info_for_language(language)
            fallback_type = parser_info.get("fallback_parser_type")
            
            if fallback_type not in [ParserType.UNKNOWN, None]:
                # Check if we already have a fallback parser
                fallback_key = f"{language}_{fallback_type.name}"
                if fallback_key in self._fallback_parsers:
                    return self._fallback_parsers[fallback_key]
                    
                # Try to create a fallback parser
                future = submit_async_task(self._create_parser(
                    language,
                    fallback_type,
                    classification.file_type
                ))
                self._pending_tasks.add(future)
                try:
                    fallback_parser = await asyncio.wrap_future(future)
                    if fallback_parser:
                        self._fallback_parsers[fallback_key] = fallback_parser
                        log(f"Using fallback parser type {fallback_type} for {language}", level="info")
                        return fallback_parser
                finally:
                    self._pending_tasks.remove(future)
            
            # Try language alternatives as last resort
            for alt_language in get_suggested_alternatives(language):
                alt_parser_info = get_parser_info_for_language(alt_language)
                future = submit_async_task(self.get_parser(FileClassification(
                    file_path=classification.file_path,
                    language_id=alt_language,
                    parser_type=alt_parser_info["parser_type"],
                    file_type=alt_parser_info["file_type"]
                )))
                self._pending_tasks.add(future)
                try:
                    alt_parser = await asyncio.wrap_future(future)
                    if alt_parser:
                        log(f"Using alternative language {alt_language} parser for {language}", level="info")
                        return alt_parser
                finally:
                    self._pending_tasks.remove(future)
        
        # No parser available
        return None
    
    async def _create_parser(self, language: str, parser_type: ParserType, file_type: FileType) -> Optional[BaseParserInterface]:
        """Create a new parser instance of the specified type."""
        async with AsyncErrorBoundary(f"create_parser_{language}_{parser_type.name}", error_types=(Exception,)):
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
                    parser = parser_cls(language, file_type)
                    await parser.initialize()
                    return parser
            
            # If no custom parser or not a custom parser language, follow the requested type
            if parser_type == ParserType.TREE_SITTER and parser_info.get("tree_sitter_available", False):
                parser = TreeSitterParser(language, file_type)
                await parser.initialize()
                return parser
            elif parser_type == ParserType.CUSTOM and language in CUSTOM_PARSER_CLASSES:
                parser_cls = CUSTOM_PARSER_CLASSES.get(language)
                if parser_cls:
                    parser = parser_cls(language, file_type)
                    await parser.initialize()
                    return parser
        
        return None

    def get_supported_languages(self) -> Dict[str, ParserType]:
        """Get all supported languages and their parser types."""
        from parsers.language_mapping import get_supported_languages as get_langs
        return get_langs()

    async def cleanup(self):
        """Clean up all parser resources."""
        try:
            # Clean up all parsers
            cleanup_tasks = []
            
            # Clean up primary parsers
            for parser in self._parsers.values():
                future = submit_async_task(parser.cleanup())
                cleanup_tasks.append(future)
            
            # Clean up fallback parsers
            for parser in self._fallback_parsers.values():
                future = submit_async_task(parser.cleanup())
                cleanup_tasks.append(future)
            
            # Wait for all cleanup tasks
            await asyncio.gather(*[asyncio.wrap_future(f) for f in cleanup_tasks], return_exceptions=True)
            
            # Clean up any remaining pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clear parser dictionaries
            self._parsers.clear()
            self._fallback_parsers.clear()
            
            self._initialized = False
            log("Language registry cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up language registry: {e}", level="error")

# Global instance
language_registry = LanguageRegistry() 