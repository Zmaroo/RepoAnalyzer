"""Unified language detection and support."""

from typing import Dict, Optional, Set
from dataclasses import dataclass
from parsers.language_mapping import get_language_by_extension
from parsers.tree_sitter_parser import TreeSitterParser
from utils.logger import log
from utils.error_handling import (
    handle_errors,
    ProcessingError,
    ErrorBoundary
)

@dataclass
class LanguageInfo:
    """Language information container."""
    canonical_name: str
    parser_type: str
    is_supported: bool
    extensions: Set[str]
    features: Dict[str, bool]

class LanguageRegistry:
    """Central registry for language support."""
    
    def __init__(self):
        self._parsers: Dict[str, object] = {}
        self._language_info: Dict[str, LanguageInfo] = {}
        self._initialize_registry()
    
    @handle_errors(error_types=ProcessingError)
    def _initialize_registry(self):
        """Initialize the language registry."""
        with ErrorBoundary("language registry initialization"):
            # Initialize tree-sitter parser
            ts_parser = TreeSitterParser()
            supported_languages = ts_parser.get_supported_languages()
            
            for lang in supported_languages:
                extensions = get_language_by_extension(lang)
                
                self._language_info[lang] = LanguageInfo(
                    canonical_name=lang,
                    parser_type='tree-sitter',
                    is_supported=True,
                    extensions=extensions,
                    features={
                        'ast': True,
                        'syntax_highlighting': True,
                        'symbol_detection': True
                    }
                )
                
                self._parsers[f'tree-sitter:{lang}'] = ts_parser
    
    @handle_errors(error_types=ProcessingError)
    def get_language_info(self, file_path: str) -> LanguageInfo:
        """Get language information for a file."""
        with ErrorBoundary("language detection"):
            ext = file_path.split('.')[-1] if '.' in file_path else ''
            
            # Find matching language
            for lang_info in self._language_info.values():
                if ext in lang_info.extensions:
                    return lang_info
            
            # Return unsupported language info
            return LanguageInfo(
                canonical_name='unknown',
                parser_type='none',
                is_supported=False,
                extensions=set(),
                features={}
            )
    
    @handle_errors(error_types=ProcessingError)
    def get_parser(self, language_info: LanguageInfo) -> Optional[object]:
        """Get appropriate parser for a language."""
        with ErrorBoundary("parser retrieval"):
            parser_key = f'{language_info.parser_type}:{language_info.canonical_name}'
            return self._parsers.get(parser_key)
    
    @handle_errors(error_types=ProcessingError)
    def is_supported(self, file_path: str) -> bool:
        """Check if a file's language is supported."""
        return self.get_language_info(file_path).is_supported

# Global instance
language_registry = LanguageRegistry() 