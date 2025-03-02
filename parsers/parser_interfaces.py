"""Parser interfaces and abstract base classes.

This module defines the interfaces and base classes used by the parser system.
Extracted to avoid circular imports between base_parser.py and language_support.py.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union, Type, Callable
from dataclasses import dataclass, field
import re

from .types import FileType, FeatureCategory, ParserType, ParserResult, ParserConfig, ParsingStatistics

@dataclass
class BaseParserInterface(ABC):
    """Abstract base class for all parsers.
    
    Implementations:
    - TreeSitterParser: For languages with tree-sitter support
    - Language-specific parsers (NimParser, PlaintextParser, etc.): For custom parsing
    """
    
    language_id: str
    file_type: FileType
    parser_type: ParserType = ParserType.UNKNOWN  # Default value; subclasses must override
    _initialized: bool = False
    config: ParserConfig = field(default_factory=lambda: ParserConfig())
    stats: ParsingStatistics = field(default_factory=lambda: ParsingStatistics())
    feature_extractor: Any = None  # Will hold an instance of a feature extractor
    
    @abstractmethod
@handle_errors(error_types=(Exception,))
    def initialize(self) -> bool:
        """Initialize parser resources."""
        pass
    
    @abstractmethod
    def _parse_source(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Parse source code into AST."""
        pass
    
@handle_errors(error_types=(Exception,))
    @abstractmethod
    def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code and return structured results."""
        pass
@handle_errors(error_types=(Exception,))
    
    @abstractmethod
    def cleanup(self):
        """Clean up parser resources."""
        pass

@dataclass
class ParserRegistryInterface(ABC):
@handle_errors(error_types=(Exception,))
    """Abstract interface for language registry."""
    
    @abstractmethod
    def get_parser(self, classification: Any) -> Optional[BaseParserInterface]:
@handle_errors(error_types=(Exception,))
        """Get a parser for the given file classification."""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up all parsers."""
        pass 