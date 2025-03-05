"""Parser interfaces and abstract base classes.

This module defines the interfaces and base classes used by the parser system.
Extracted to avoid circular imports between base_parser.py and language_support.py.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union, Type, Callable, Set
from dataclasses import dataclass, field
import re
import asyncio

from .types import FileType, FeatureCategory, ParserType, ParserResult, ParserConfig, ParsingStatistics
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.logger import log
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task

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
    _pending_tasks: Set[asyncio.Future] = field(default_factory=set)
    
    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)
    
    @abstractmethod
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary(f"{self.language_id} parser initialization"):
                    # Subclasses should implement their initialization logic here
                    self._initialized = True
                    log(f"{self.language_id} parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing {self.language_id} parser: {e}", level="error")
                raise
        return True
    
    @abstractmethod
    @handle_async_errors(error_types=(Exception,))
    async def _parse_source(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Parse source code into AST."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"{self.language_id} parsing"):
            try:
                # Subclasses should implement their parsing logic here
                future = submit_async_task(self._parse_content, source_code)
                self._pending_tasks.add(future)
                try:
                    return await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
            except Exception as e:
                log(f"Error parsing {self.language_id} content: {e}", level="error")
                raise
    
    @abstractmethod
    def _parse_content(self, source_code: str) -> Dict[str, Any]:
        """Internal synchronous parsing method to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _parse_content")
    
    @abstractmethod
    @handle_async_errors(error_types=(Exception,))
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code and return structured results."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"{self.language_id} parsing"):
            try:
                # Parse the source
                ast = await self._parse_source(source_code)
                if not ast:
                    return None
                
                # Extract features asynchronously
                future = submit_async_task(self._extract_features, ast, source_code)
                self._pending_tasks.add(future)
                try:
                    features = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                return ParserResult(
                    success=True,
                    ast=ast,
                    features=features,
                    documentation=features.get(FeatureCategory.DOCUMENTATION.value, {}),
                    complexity=features.get(FeatureCategory.SYNTAX.value, {}).get("metrics", {}),
                    statistics=self.stats
                )
            except Exception as e:
                log(f"Error in {self.language_id} parser: {e}", level="error")
                return None
    
    @abstractmethod
    def _extract_features(self, ast: Dict[str, Any], source_code: str) -> Dict[str, Dict[str, Any]]:
        """Internal synchronous feature extraction method to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _extract_features")
    
    @abstractmethod
    async def cleanup(self):
        """Clean up parser resources."""
        try:
            # Clean up any pending tasks
            if self._pending_tasks:
                log(f"Cleaning up {len(self._pending_tasks)} pending {self.language_id} parser tasks", level="info")
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log(f"{self.language_id} parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up {self.language_id} parser: {e}", level="error")

@dataclass
class ParserRegistryInterface(ABC):
    """Abstract interface for language registry."""
    
    @abstractmethod
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """Initialize registry resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("parser registry initialization"):
                    # Subclasses should implement their initialization logic here
                    self._initialized = True
                    log("Parser registry initialized", level="info")
            except Exception as e:
                log(f"Error initializing parser registry: {e}", level="error")
                raise
    
    @abstractmethod
    @handle_async_errors(error_types=(Exception,))
    async def get_parser(self, classification: Any) -> Optional[BaseParserInterface]:
        """Get a parser for the given file classification."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("get parser"):
            try:
                # Subclasses should implement their parser retrieval logic here
                pass
            except Exception as e:
                log(f"Error getting parser: {e}", level="error")
                raise
    
    @abstractmethod
    async def cleanup(self):
        """Clean up all parsers."""
        try:
            # Clean up any pending tasks
            if self._pending_tasks:
                log(f"Cleaning up {len(self._pending_tasks)} pending registry tasks", level="info")
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("Parser registry cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up parser registry: {e}", level="error") 