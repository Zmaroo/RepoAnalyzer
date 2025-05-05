"""Parser interface definitions.

This module defines the base interfaces for all parser components,
ensuring consistent initialization, cleanup, and lifecycle management.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    ParserResult, PatternValidationResult
)
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary,
    handle_async_errors,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks

class BaseParserInterface(ABC):
    """Base interface for all parsers.
    
    This class defines the interface that all parsers must implement,
    providing a consistent API for all parser implementations.
    
    Attributes:
        language_id (str): The identifier for the language this parser handles
        file_type (FileType): The type of files this parser can process
        parser_type (ParserType): The type of parser implementation
    """
    
    def __init__(self, language_id: str, file_type: FileType, parser_type: ParserType):
        """Initialize parser interface.
        
        Args:
            language_id: The identifier for the language this parser handles
            file_type: The type of files this parser can process
            parser_type: The type of parser implementation
        """
        self.language_id = language_id
        self.file_type = file_type
        self.parser_type = parser_type
        self._initialized = False
        
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the parser.
        
        Implementations should perform all necessary setup and initialization.
        
        Returns:
            bool: True if initialization was successful
        """
        pass
        
    @abstractmethod
    async def _cleanup(self) -> None:
        """Clean up resources used by the parser.
        
        Implementations should release all resources and perform any
        necessary cleanup operations.
        """
        pass
        
    @abstractmethod
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code.
        
        Args:
            source_code: The source code to parse
            
        Returns:
            Optional[ParserResult]: The parsing result or None if parsing failed
        """
        pass
        
    @abstractmethod
    async def validate(self, source_code: str) -> PatternValidationResult:
        """Validate source code.
        
        Args:
            source_code: The source code to validate
            
        Returns:
            PatternValidationResult: The validation result
        """
        pass
    
    async def parse_file_content(self, file_content: str, file_path: Optional[str] = None) -> ParserResult:
        """Parse file content.
        
        This method provides a standardized way to parse file content across parsers.
        By default, this method delegates to parse(), but implementations can override
        for file-specific optimizations.
        
        Args:
            file_content: Content to parse
            file_path: Optional file path for context
            
        Returns:
            ParserResult: Result of parsing
        """
        result = await self.parse(file_content)
        if result is None:
            result = ParserResult(
                success=False,
                file_type=self.file_type,
                parser_type=self.parser_type,
                language=self.language_id,
                errors=["Parsing failed"]
            )
        return result
    
    async def parse_incremental(self, file_content: str, old_tree=None, file_path: Optional[str] = None) -> ParserResult:
        """Parse file content with incremental parsing support.
        
        This method supports incremental parsing for parsers that implement it.
        By default, this delegates to parse_file_content which in turn delegates to parse().
        Tree-sitter parsers should override this to use tree-sitter's incremental parsing.
        
        Args:
            file_content: Content to parse
            old_tree: Optional previous tree for incremental parsing
            file_path: Optional file path for context
            
        Returns:
            ParserResult: Result of parsing
        """
        # Default implementation just calls regular parsing
        return await self.parse_file_content(file_content, file_path)
        
    async def ensure_initialized(self) -> bool:
        """Ensure the parser is initialized.
        
        If the parser is not already initialized, this method will
        initialize it. If it is already initialized, this method
        will do nothing.
        
        Returns:
            bool: True if the parser is initialized
        """
        if not self._initialized:
            self._initialized = await self.initialize()
        return self._initialized

class AIParserInterface(ABC):
    """Interface for AI-capable parser components.
    
    This interface defines AI-specific capabilities, including AI processing
    and learning capabilities.
    
    Attributes:
        ai_capabilities (Set[AICapability]): Set of supported AI capabilities
    """
    
    def __init__(
        self,
        language_id: str,
        file_type: FileType,
        capabilities: Set[AICapability]
    ):
        """Initialize AI parser interface.
        
        Args:
            language_id: The identifier for the language
            file_type: The type of files this parser can process
            capabilities: Set of supported AI capabilities
        """
        self.language_id = language_id
        self.file_type = file_type
        self.ai_capabilities = capabilities
    
    @abstractmethod
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process source code with AI assistance.
        
        This method must be implemented by all AI-capable parser components
        to perform their specific AI processing tasks.
        
        Args:
            source_code: The source code to process
            context: The AI processing context
            
        Returns:
            PatternValidationResult: The processing result
            
        Raises:
            ProcessingError: If processing fails
        """
        pass
    
    @abstractmethod
    async def learn_from_code(
        self,
        source_code: str,
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Learn patterns from source code.
        
        This method must be implemented by all AI-capable parser components
        to perform their specific learning tasks.
        
        Args:
            source_code: The source code to learn from
            context: The AI learning context
            
        Returns:
            List[Dict[str, Any]]: The learned patterns
            
        Raises:
            ProcessingError: If learning fails
        """
        pass

class PatternProcessorInterface(ABC):
    """Interface for pattern processing components.
    
    This interface defines the core capabilities required for pattern processing,
    including pattern execution, testing, and validation.
    
    Attributes:
        language_id (str): The identifier for the language
    """
    
    def __init__(self, language_id: str):
        """Initialize pattern processor interface.
        
        Args:
            language_id: The identifier for the language
        """
        self.language_id = language_id
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the pattern processor.
        
        Implementations should perform all necessary setup and initialization.
        
        Returns:
            bool: True if initialization was successful
        """
        pass
    
    @abstractmethod
    async def process_pattern(
        self,
        pattern_name: str,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a pattern against content.
        
        Args:
            pattern_name: The name of the pattern to process
            content: The content to process against
            context: Optional processing context
            
        Returns:
            Dict[str, Any]: The processing result
            
        Raises:
            ProcessingError: If processing fails
        """
        pass
    
    @abstractmethod
    async def test_pattern(
        self,
        pattern_name: str,
        content: str,
        is_tree_sitter: bool = False
    ) -> Dict[str, Any]:
        """Test a pattern against content.
        
        This method allows testing a pattern against content,
        providing detailed results including matches and diagnostics.
        
        Args:
            pattern_name: The name of the pattern to test
            content: The content to test against
            is_tree_sitter: Whether to use tree-sitter for matching
            
        Returns:
            Dict[str, Any]: Test results including matches, performance metrics, and validation
            
        Raises:
            ProcessingError: If testing fails
        """
        pass
    
    @abstractmethod
    async def validate_pattern_syntax(
        self,
        pattern_name: str
    ) -> Dict[str, Any]:
        """Validate the syntax of a pattern.
        
        Args:
            pattern_name: The name of the pattern to validate
            
        Returns:
            Dict[str, Any]: Validation results
            
        Raises:
            ProcessingError: If validation fails
        """
        pass
    
    @abstractmethod
    async def export_patterns(
        self,
        format_type: str = "dict",
        pattern_type: str = "all"
    ) -> Union[Dict[str, Any], str]:
        """Export patterns in the requested format.
        
        Args:
            format_type: Format to export ("dict", "json", or "yaml")
            pattern_type: Type of patterns to export ("all", "tree_sitter", or "regex")
            
        Returns:
            Union[Dict[str, Any], str]: Exported patterns
            
        Raises:
            ProcessingError: If export fails
        """
        pass
    
    async def ensure_initialized(self) -> bool:
        """Ensure the pattern processor is initialized.
        
        Returns:
            bool: True if the pattern processor is initialized
        """
        if not self._initialized:
            self._initialized = await self.initialize()
        return self._initialized

class ExtractorInterface(ABC):
    """Interface for feature and block extraction components.
    
    This interface defines the core capabilities required for extracting
    features and code blocks from parsed code.
    
    Attributes:
        language_id (str): The identifier for the language
    """
    
    def __init__(self, language_id: str):
        """Initialize extractor interface.
        
        Args:
            language_id: The identifier for the language
        """
        self.language_id = language_id
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the extractor.
        
        Implementations should perform all necessary setup and initialization.
        
        Returns:
            bool: True if initialization was successful
        """
        pass
    
    @abstractmethod
    async def extract(
        self,
        ast: Dict[str, Any],
        source_code: str,
        parser_type: ParserType
    ) -> Dict[str, Any]:
        """Extract information from AST and source code.
        
        This is the core extraction method that all extractors must implement.
        
        Args:
            ast: The Abstract Syntax Tree to extract from
            source_code: The original source code
            parser_type: The type of parser that produced the AST
            
        Returns:
            Dict[str, Any]: The extracted information
            
        Raises:
            ProcessingError: If extraction fails
        """
        pass
    
    async def ensure_initialized(self) -> bool:
        """Ensure the extractor is initialized.
        
        Returns:
            bool: True if the extractor is initialized
        """
        if not self._initialized:
            self._initialized = await self.initialize()
        return self._initialized


# Export public interfaces
__all__ = [
    'BaseParserInterface',
    'AIParserInterface',
    'PatternProcessorInterface',
    'ExtractorInterface'
] 