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
    """Base interface for all parser components.
    
    This interface defines the core functionality required by all parser components,
    including initialization, cleanup, and basic parsing capabilities.
    
    Attributes:
        language_id (str): The identifier for the language
        file_type (FileType): The type of files this parser can process
        parser_type (ParserType): The type of parser implementation
        _initialized (bool): Whether the parser has been initialized
    """
    
    def __init__(self, language_id: str, file_type: FileType, parser_type: ParserType):
        """Initialize base parser interface.
        
        Args:
            language_id: The identifier for the language
            file_type: The type of files this parser can process
            parser_type: The type of parser implementation
        """
        self.language_id = language_id
        self.file_type = file_type
        self.parser_type = parser_type
        self._initialized = False
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the parser component.
        
        This method must be implemented by all parser components to perform
        their specific initialization tasks. It should:
        1. Initialize any required resources
        2. Register with necessary services
        3. Load any required configuration
        4. Set up monitoring and health checks
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def _cleanup(self) -> None:
        """Clean up parser component resources.
        
        This method must be implemented by all parser components to perform
        their specific cleanup tasks. It should:
        1. Clean up any allocated resources
        2. Unregister from services
        3. Save any necessary state
        4. Update health status
        
        Raises:
            ProcessingError: If cleanup fails
        """
        pass
    
    @abstractmethod
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code.
        
        This method must be implemented by all parser components to perform
        their specific parsing tasks.
        
        Args:
            source_code: The source code to parse
            
        Returns:
            Optional[ParserResult]: The parsing result or None if parsing failed
            
        Raises:
            ProcessingError: If parsing fails
        """
        pass
    
    @abstractmethod
    async def validate(self, source_code: str) -> PatternValidationResult:
        """Validate source code.
        
        This method must be implemented by all parser components to perform
        their specific validation tasks.
        
        Args:
            source_code: The source code to validate
            
        Returns:
            PatternValidationResult: The validation result
            
        Raises:
            ProcessingError: If validation fails
        """
        pass
    
    async def ensure_initialized(self) -> bool:
        """Ensure the parser component is initialized.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        if not self._initialized:
            return await self.initialize()
        return True

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

# Export public interfaces
__all__ = [
    'BaseParserInterface',
    'AIParserInterface'
] 