"""Unified parser management.

This module provides a unified interface for all parsers,
integrating with the parser system and caching infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    ParserResult, PatternValidationResult
)
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.language_config import get_language_config
from parsers.language_mapping import get_language_mapping
from parsers.language_support import get_language_support
from parsers.feature_extractor import get_feature_extractor
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary,
    handle_async_errors,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context, cached_in_request
from db.transaction import transaction_scope

@dataclass
class UnifiedParser(BaseParser):
    """Unified parser management.
    
    This class provides a unified interface for all parsers,
    integrating with the parser system for efficient parsing.
    
    Attributes:
        language_id (str): The identifier for the language
        file_type (FileType): The type of files this parser can process
        parser_type (ParserType): The type of parser implementation
        _parsers (Dict[str, BaseParser]): Map of language IDs to parser instances
    """
    
    def __init__(self, language_id: str, file_type: FileType, parser_type: ParserType):
        """Initialize unified parser.
        
        Args:
            language_id: The identifier for the language
            file_type: The type of files this parser can process
            parser_type: The type of parser implementation
        """
        super().__init__(
            language_id=language_id,
            file_type=file_type,
            parser_type=parser_type
        )
        self._parsers = {}
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize unified parser.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"unified_parser_initialization_{self.language_id}"):
                # Initialize components through async_runner
                init_task = submit_async_task(self._initialize_components())
                await asyncio.wrap_future(init_task)
                
                if not self._parsers:
                    raise ProcessingError(f"Failed to initialize parsers for {self.language_id}")
                
                await log(f"Unified parser initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing unified parser: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"unified_parser_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"unified_parser_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"parser_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize unified parser for {self.language_id}: {e}")
    
    async def _initialize_components(self) -> None:
        """Initialize parser components."""
        # Get language configuration
        config = await get_language_config(self.language_id)
        if not config:
            raise ProcessingError(f"Failed to get language configuration for {self.language_id}")
        
        # Get language mapping
        mapping = await get_language_mapping(self.language_id)
        if not mapping:
            raise ProcessingError(f"Failed to get language mapping for {self.language_id}")
        
        # Get language support
        support = await get_language_support(self.language_id)
        if not support:
            raise ProcessingError(f"Failed to get language support for {self.language_id}")
        
        # Get feature extractor
        extractor = await get_feature_extractor(self.language_id)
        if not extractor:
            raise ProcessingError(f"Failed to get feature extractor for {self.language_id}")
        
        # Get tree-sitter parser if supported
        if support.level.supports_tree_sitter:
            parser = await get_tree_sitter_parser(self.language_id)
            if parser:
                self._parsers["tree_sitter"] = parser
        
        # Store components
        self._parsers["config"] = config
        self._parsers["mapping"] = mapping
        self._parsers["support"] = support
        self._parsers["extractor"] = extractor
    
    @handle_async_errors(error_types=ProcessingError)
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code using appropriate parser.
        
        Args:
            source_code: The source code to parse
            
        Returns:
            Optional[ParserResult]: The parsing result or None if parsing failed
        """
        try:
            async with AsyncErrorBoundary(f"unified_parse_{self.language_id}"):
                # Get appropriate parser
                parser = self._get_parser_for_source(source_code)
                if not parser:
                    raise ProcessingError(f"No suitable parser found for {self.language_id}")
                
                # Parse through async_runner
                parse_task = submit_async_task(parser.parse(source_code))
                result = await asyncio.wrap_future(parse_task)
                
                if not result:
                    raise ProcessingError(f"Parsing failed for {self.language_id}")
                
                # Extract features
                extractor = self._parsers.get("extractor")
                if extractor:
                    features = await extractor.extract_features(result.ast, source_code)
                    result.features = features
                
                await log(f"Source code parsed for {self.language_id}", level="info")
                return result
                
        except Exception as e:
            await log(f"Error parsing source code: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"unified_parse_{self.language_id}",
                ProcessingError,
                context={"source_size": len(source_code)}
            )
            return None
    
    def _get_parser_for_source(self, source_code: str) -> Optional[BaseParser]:
        """Get appropriate parser for source code."""
        # Try tree-sitter first if available
        if "tree_sitter" in self._parsers:
            return self._parsers["tree_sitter"]
        
        # Fallback to custom parser if available
        if "custom" in self._parsers:
            return self._parsers["custom"]
        
        return None
    
    @handle_async_errors(error_types=ProcessingError)
    async def validate(self, source_code: str) -> PatternValidationResult:
        """Validate source code using appropriate parser.
        
        Args:
            source_code: The source code to validate
            
        Returns:
            PatternValidationResult: The validation result
        """
        try:
            async with AsyncErrorBoundary(f"unified_validate_{self.language_id}"):
                # Get appropriate parser
                parser = self._get_parser_for_source(source_code)
                if not parser:
                    return PatternValidationResult(
                        is_valid=False,
                        errors=["No suitable parser found"]
                    )
                
                # Validate through async_runner
                validate_task = submit_async_task(parser.validate(source_code))
                result = await asyncio.wrap_future(validate_task)
                
                await log(f"Source code validated for {self.language_id}", level="info")
                return result
                
        except Exception as e:
            await log(f"Error validating source code: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"unified_validate_{self.language_id}",
                ProcessingError,
                context={"source_size": len(source_code)}
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )

# Global instance cache
_parser_instances: Dict[str, UnifiedParser] = {}

async def get_unified_parser(
    language_id: str,
    file_type: FileType,
    parser_type: ParserType
) -> Optional[UnifiedParser]:
    """Get a unified parser instance.
    
    Args:
        language_id: The language to get parser for
        file_type: The type of files to parse
        parser_type: The type of parser to use
        
    Returns:
        Optional[UnifiedParser]: The parser instance or None if initialization fails
    """
    key = f"{language_id}:{file_type.value}:{parser_type.value}"
    if key not in _parser_instances:
        parser = UnifiedParser(language_id, file_type, parser_type)
        if await parser.initialize():
            _parser_instances[key] = parser
        else:
            return None
    return _parser_instances[key] 