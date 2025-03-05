"""[1.0] Language support registry and utilities."""

from typing import Dict, Optional, Set, Tuple, List, Any
import asyncio
import os
from parsers.parser_interfaces import BaseParserInterface, ParserRegistryInterface, AIParserInterface
from parsers.models import FileClassification, LanguageFeatures, FileMetadata
from parsers.types import (
    ParserType, FileType, AICapability, AIContext, AIProcessingResult,
    InteractionType, ConfidenceLevel
)
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
from utils.error_handling import AsyncErrorBoundary, ErrorSeverity, handle_async_errors, ProcessingError
from utils.shutdown import register_shutdown_handler
from dataclasses import dataclass, field
import re
from abc import ABC, abstractmethod

@dataclass
class ParserAvailability:
    """[1.1] Information about available parsers for a language."""
    has_custom_parser: bool
    has_tree_sitter: bool
    preferred_type: ParserType
    file_type: FileType
    fallback_type: Optional[ParserType] = None
    ai_capabilities: Set[AICapability] = field(default_factory=set)

def get_parser_availability(language: str) -> ParserAvailability:
    """[1.2] Get information about available parsers for a language."""
    normalized = normalize_language_name(language)
    
    # Use the new parser info function to get comprehensive parser information
    parser_info = get_parser_info_for_language(normalized)
    
    # Import here to avoid circular imports
    from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
    
    has_custom = normalized in CUSTOM_PARSER_CLASSES
    has_tree_sitter = normalized in TREE_SITTER_LANGUAGES
    
    # Determine AI capabilities based on parser type
    ai_capabilities = {
        AICapability.CODE_UNDERSTANDING,
        AICapability.CODE_GENERATION,
        AICapability.CODE_MODIFICATION
    }
    
    # Add additional capabilities for tree-sitter parsers
    if has_tree_sitter:
        ai_capabilities.add(AICapability.CODE_REVIEW)
        ai_capabilities.add(AICapability.LEARNING)
    
    return ParserAvailability(
        has_custom_parser=has_custom,
        has_tree_sitter=has_tree_sitter,
        preferred_type=parser_info["parser_type"],
        file_type=parser_info["file_type"],
        fallback_type=parser_info.get("fallback_parser_type"),
        ai_capabilities=ai_capabilities
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

async def get_language_by_extension(file_path: str) -> Optional[LanguageFeatures]:
    """
    Get language features for a file extension or path.
    
    RETURNS: LanguageFeatures if a language is identified, else None.
    """
    basename = os.path.basename(file_path)
    
    async with AsyncErrorBoundary(f"get_language_for_path_{basename}", error_types=(Exception,)):
        # Use the language mapping module to detect language
        from parsers.language_mapping import detect_language_from_filename
        language = detect_language_from_filename(basename)
        
        if language:
            return get_language_features(language)
    
    return None

async def get_extensions_for_language(language: str) -> Set[str]:
    """Get all file extensions associated with a language."""
    async with AsyncErrorBoundary(f"get_extensions_for_{language}", error_types=(Exception,)):
        from parsers.language_mapping import get_extensions_for_language as get_exts
        return get_exts(language)
    
    return set()

class LanguageRegistry(ParserRegistryInterface):
    """[1.3] Registry for language parsers."""
    
    def __init__(self):
        self._parsers: Dict[str, BaseParserInterface] = {}
        self._fallback_parsers: Dict[str, BaseParserInterface] = {}
        self._ai_parsers: Dict[str, AIParserInterface] = {}
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """[1.3.1] Initialize language registry resources."""
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
                            task = asyncio.create_task(self._create_parser(
                                language, 
                                classification.parser_type,
                                classification.file_type
                            ))
                            self._pending_tasks.add(task)
                            try:
                                parser = await task
                                if parser:
                                    self._parsers[language] = parser
                                    # Initialize AI parser if supported
                                    if isinstance(parser, AIParserInterface):
                                        self._ai_parsers[language] = parser
                            finally:
                                self._pending_tasks.remove(task)
                    
                    self._initialized = True
                    log("Language registry initialized", level="info")
            except Exception as e:
                log(f"Error initializing language registry: {e}", level="error")
                raise

    @handle_async_errors(error_types=(Exception,))
    async def get_parser(self, classification: FileClassification) -> Optional[BaseParserInterface]:
        """[1.3.2] Get the appropriate parser for a file classification."""
        if not self._initialized:
            await self.initialize()
            
        language = classification.language_id
        
        async with AsyncErrorBoundary(f"get_parser_{language}", error_types=(Exception,)):
            # Try to get an existing parser first
            if language in self._parsers:
                return self._parsers.get(language)
                
            # Create a parser if it doesn't exist
            task = asyncio.create_task(self._create_parser(
                language, 
                classification.parser_type,
                classification.file_type
            ))
            self._pending_tasks.add(task)
            try:
                parser = await task
                if parser:
                    self._parsers[language] = parser
                    # Initialize AI parser if supported
                    if isinstance(parser, AIParserInterface):
                        self._ai_parsers[language] = parser
                    return parser
            finally:
                self._pending_tasks.remove(task)
            
            # If no parser could be created with specified type, try fallback
            parser_info = get_parser_info_for_language(language)
            fallback_type = parser_info.get("fallback_parser_type")
            
            if fallback_type not in [ParserType.UNKNOWN, None]:
                # Check if we already have a fallback parser
                fallback_key = f"{language}_{fallback_type.name}"
                if fallback_key in self._fallback_parsers:
                    return self._fallback_parsers[fallback_key]
                    
                # Try to create a fallback parser
                task = asyncio.create_task(self._create_parser(
                    language,
                    fallback_type,
                    classification.file_type
                ))
                self._pending_tasks.add(task)
                try:
                    fallback_parser = await task
                    if fallback_parser:
                        self._fallback_parsers[fallback_key] = fallback_parser
                        # Initialize AI parser if supported
                        if isinstance(fallback_parser, AIParserInterface):
                            self._ai_parsers[f"{language}_fallback"] = fallback_parser
                        log(f"Using fallback parser type {fallback_type} for {language}", level="info")
                        return fallback_parser
                finally:
                    self._pending_tasks.remove(task)
            
            # Try language alternatives as last resort
            for alt_language in get_suggested_alternatives(language):
                alt_parser_info = get_parser_info_for_language(alt_language)
                task = asyncio.create_task(self.get_parser(FileClassification(
                    file_path=classification.file_path,
                    language_id=alt_language,
                    parser_type=alt_parser_info["parser_type"],
                    file_type=alt_parser_info["file_type"]
                )))
                self._pending_tasks.add(task)
                try:
                    alt_parser = await task
                    if alt_parser:
                        log(f"Using alternative language {alt_language} parser for {language}", level="info")
                        return alt_parser
                finally:
                    self._pending_tasks.remove(task)
        
        return None

    async def get_ai_parser(self, language: str) -> Optional[AIParserInterface]:
        """[1.3.3] Get an AI-capable parser for a language."""
        if not self._initialized:
            await self.initialize()
            
        # Check if we already have an AI parser for this language
        if language in self._ai_parsers:
            return self._ai_parsers[language]
            
        # Try to get a regular parser and check if it supports AI
        parser_info = get_parser_info_for_language(language)
        classification = FileClassification(
            language_id=language,
            parser_type=parser_info["parser_type"],
            file_type=parser_info["file_type"]
        )
        
        parser = await self.get_parser(classification)
        if isinstance(parser, AIParserInterface):
            self._ai_parsers[language] = parser
            return parser
            
        return None

    async def process_with_ai(
        self,
        language: str,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """[1.3.4] Process source code with AI assistance."""
        parser = await self.get_ai_parser(language)
        if not parser:
            return AIProcessingResult(
                success=False,
                response=f"No AI-capable parser available for {language}"
            )
            
        return await parser.process_with_ai(source_code, context)

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
        """[1.3.5] Clean up language registry resources."""
        try:
            if not self._initialized:
                return
                
            # Clean up all parsers
            for parser in self._parsers.values():
                await parser.cleanup()
            self._parsers.clear()
            
            # Clean up fallback parsers
            for parser in self._fallback_parsers.values():
                await parser.cleanup()
            self._fallback_parsers.clear()
            
            # Clean up AI parsers (may overlap with other parsers)
            self._ai_parsers.clear()
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("Language registry cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up language registry: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup language registry: {e}")

# Global instance
language_registry = LanguageRegistry() 

class AIParserInterface(ABC):
    @abstractmethod
    async def process_deep_learning(
        self,
        source_code: str,
        context: AIContext,
        repositories: List[int]
    ) -> AIProcessingResult:
        """Process with deep learning capabilities."""
        pass

    @abstractmethod
    async def learn_from_repositories(
        self,
        repo_ids: List[int]
    ) -> Dict[str, Any]:
        """Learn patterns from multiple repositories."""
        pass 