"""Common types and enums for parsers."""

from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union, Set
from dataclasses import dataclass, field
import asyncio
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.logger import log
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task

class FileType(Enum):
    """File classification types."""
    CODE = "code"
    DOC = "doc"
    CONFIG = "config"
    DATA = "data"
    MARKUP = "markup"

class FeatureCategory(Enum):
    """Feature extraction categories."""
    SYNTAX = "syntax"
    SEMANTICS = "semantics"
    DOCUMENTATION = "documentation"
    STRUCTURE = "structure"

class PatternCategory(Enum):
    """Categories for pattern matching."""
    SYNTAX = "syntax"
    SEMANTICS = "semantics"
    DOCUMENTATION = "documentation"
    STRUCTURE = "structure"
    CODE = "code"
    LEARNING = "learning"

class PatternType(Enum):
    """Types of patterns used for code analysis."""
    CODE_STRUCTURE = "code_structure"
    CODE_NAMING = "code_naming"
    ERROR_HANDLING = "error_handling"
    DOCUMENTATION_STRUCTURE = "documentation_structure"
    ARCHITECTURE = "architecture"

class ParserType(Enum):
    """Parser implementation types."""
    TREE_SITTER = "tree_sitter"
    CUSTOM = "custom"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"

@dataclass
class ParserResult:
    """Standardized parser result."""
    success: bool
    ast: Optional[Dict[str, Any]] = None
    features: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    documentation: Dict[str, Any] = field(default_factory=dict)
    complexity: Dict[str, Any] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Future] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser result resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("parser result initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing parser result: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up parser result resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up parser result: {e}", level="error")

@dataclass
class ParserConfig:
    """Parser configuration."""
    max_file_size: int = 1024 * 1024  # 1MB
    timeout_ms: int = 5000
    cache_results: bool = True
    include_comments: bool = True
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Future] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize configuration resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("parser config initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing parser config: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up configuration resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up parser config: {e}", level="error")

@dataclass
class ParsingStatistics:
    """Parsing performance statistics."""
    parse_time_ms: float = 0.0
    feature_extraction_time_ms: float = 0.0
    node_count: int = 0
    error_count: int = 0
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Future] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize statistics resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("parsing statistics initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing parsing statistics: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up statistics resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up parsing statistics: {e}", level="error")

@dataclass
class Documentation:
    """Documentation features."""
    docstrings: List[Dict[str, Any]] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    todos: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: str = ""
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Future] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize documentation resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("documentation initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing documentation: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up documentation resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up documentation: {e}", level="error")

@dataclass
class ComplexityMetrics:
    """Code complexity metrics."""
    cyclomatic: int = 0
    cognitive: int = 0
    halstead: Dict[str, float] = field(default_factory=dict)
    maintainability_index: float = 0.0
    lines_of_code: Dict[str, int] = field(default_factory=dict)
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Future] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize metrics resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("complexity metrics initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing complexity metrics: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up metrics resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up complexity metrics: {e}", level="error")

@dataclass
class ExtractedFeatures:
    """Extracted feature container."""
    features: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    documentation: Documentation = field(default_factory=Documentation)
    metrics: ComplexityMetrics = field(default_factory=ComplexityMetrics)
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Future] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize features resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("extracted features initialization"):
                    # Initialize nested resources
                    await self.documentation.initialize()
                    await self.metrics.initialize()
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing extracted features: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up features resources."""
        try:
            # Clean up nested resources
            await self.documentation.cleanup()
            await self.metrics.cleanup()
            
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up extracted features: {e}", level="error")

@dataclass
class PatternDefinition:
    """Definition of a pattern to be matched."""
    pattern: str
    extract: Optional[Callable] = None
    description: Optional[str] = None
    examples: List[str] = field(default_factory=list)
    category: Optional[str] = None

@dataclass
class QueryPattern:
    """Pattern for querying code."""
    pattern: str
    extract: Optional[Callable] = None
    description: Optional[str] = None
    examples: List[str] = field(default_factory=list)
    category: Optional[str] = None
    language_id: Optional[str] = None
    name: Optional[str] = None
    definition: Optional[PatternDefinition] = None

@dataclass
class PatternInfo:
    """Additional metadata for query patterns."""
    pattern: str
    extract: Optional[Callable] = None
    description: Optional[str] = None
    examples: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
