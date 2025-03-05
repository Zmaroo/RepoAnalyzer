"""Parser interfaces and abstract base classes.

This module defines the interfaces and base classes used by the parser system.
Extracted to avoid circular imports between base_parser.py and language_support.py.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union, Type, Callable, Set
from dataclasses import dataclass, field
import re
import asyncio

from .types import (
    FileType, FeatureCategory, ParserType, ParserResult, ParserConfig, ParsingStatistics,
    AICapability, AIContext, AIProcessingResult
)
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity, ProcessingError
from utils.logger import log
from utils.shutdown import register_shutdown_handler

@dataclass
class AIParserInterface(ABC):
    """Interface for AI-enabled parsers."""
    
    language_id: str
    file_type: FileType
    capabilities: Set[AICapability] = field(default_factory=set)
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)
    
    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)
    
    @abstractmethod
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize AI parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary(f"{self.language_id} AI parser initialization"):
                    # Subclasses should implement their initialization logic here
                    self._initialized = True
                    log(f"{self.language_id} AI parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing {self.language_id} AI parser: {e}", level="error")
                raise
        return True
    
    @abstractmethod
    @handle_async_errors(error_types=(Exception,))
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"{self.language_id} AI processing"):
            try:
                # Subclasses should implement their AI processing logic here
                pass
            except Exception as e:
                log(f"Error in {self.language_id} AI processing: {e}", level="error")
                raise
    
    @abstractmethod
    async def cleanup(self):
        """Clean up AI parser resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
            log(f"{self.language_id} AI parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up {self.language_id} AI parser: {e}", level="error")

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
    ai_capabilities: Set[AICapability] = field(default_factory=set)
    _initialized: bool = False
    config: ParserConfig = field(default_factory=lambda: ParserConfig())
    stats: ParsingStatistics = field(default_factory=lambda: ParsingStatistics())
    feature_extractor: Any = None  # Will hold an instance of a feature extractor
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)
    
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
                    # Initialize AI capabilities if supported
                    if AICapability.CODE_UNDERSTANDING in self.ai_capabilities:
                        await self._initialize_ai_understanding()
                    if AICapability.CODE_GENERATION in self.ai_capabilities:
                        await self._initialize_ai_generation()
                    if AICapability.CODE_MODIFICATION in self.ai_capabilities:
                        await self._initialize_ai_modification()
                    
                    self._initialized = True
                    log(f"{self.language_id} parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing {self.language_id} parser: {e}", level="error")
                raise
        return True
    
    async def _initialize_ai_understanding(self):
        """Initialize AI code understanding capabilities."""
        pass
    
    async def _initialize_ai_generation(self):
        """Initialize AI code generation capabilities."""
        pass
    
    async def _initialize_ai_modification(self):
        """Initialize AI code modification capabilities."""
        pass
    
    @abstractmethod
    @handle_async_errors(error_types=(Exception,))
    async def _parse_source(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Parse source code into AST."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"{self.language_id} parsing"):
            try:
                # Subclasses should implement their parsing logic here
                task = asyncio.create_task(self._parse_content(source_code))
                self._pending_tasks.add(task)
                try:
                    return await task
                finally:
                    self._pending_tasks.remove(task)
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
                task = asyncio.create_task(self._extract_features(ast, source_code))
                self._pending_tasks.add(task)
                try:
                    features = await task
                finally:
                    self._pending_tasks.remove(task)
                
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
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("Parser registry not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'ParserRegistryInterface':
        """Async factory method to create and initialize a ParserRegistryInterface instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("parser registry initialization"):
                # Initialize required components
                from parsers.language_support import language_registry
                from parsers.tree_sitter_parser import TreeSitterParser
                from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
                
                # Initialize tree-sitter parsers for supported languages
                supported_languages = ['python', 'javascript', 'typescript', 'java', 'cpp']
                for lang in supported_languages:
                    try:
                        parser = await TreeSitterParser.create(lang, FileType.SOURCE)
                        instance._pending_tasks.add(asyncio.create_task(parser.initialize()))
                    except Exception as e:
                        await log(f"Warning: Failed to initialize tree-sitter parser for {lang}: {e}", level="warning")
                
                # Initialize custom parsers
                for lang, parser_cls in CUSTOM_PARSER_CLASSES.items():
                    try:
                        parser = await parser_cls.create(lang, FileType.SOURCE)
                        instance._pending_tasks.add(asyncio.create_task(parser.initialize()))
                    except Exception as e:
                        await log(f"Warning: Failed to initialize custom parser for {lang}: {e}", level="warning")
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("parser_registry")
                
                instance._initialized = True
                await log("Parser registry initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing parser registry: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize parser registry: {e}")
    
    @abstractmethod
    @handle_async_errors(error_types=(Exception,))
    async def get_parser(self, classification: Any) -> Optional[BaseParserInterface]:
        """Get a parser for the given file classification."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("get parser"):
            try:
                # Subclasses should implement their parser retrieval logic here
                pass
            except Exception as e:
                await log(f"Error getting parser: {e}", level="error")
                raise
    
    async def cleanup(self):
        """Clean up all parsers."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("parser_registry")
            
            self._initialized = False
            await log("Parser registry cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up parser registry: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup parser registry: {e}") 