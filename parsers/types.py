"""Common types and enums for parsers."""

from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union, Set
from dataclasses import dataclass, field
import asyncio
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.logger import log
from utils.shutdown import register_shutdown_handler

class FileType(Enum):
    """File classification types."""
    CODE = "code"
    DOC = "doc"
    CONFIG = "config"
    DATA = "data"
    MARKUP = "markup"

class PatternCategory(Enum):
    """Unified categories for code understanding and manipulation."""
    SYNTAX = "syntax"               # Basic code structures (functions, classes, etc)
    SEMANTICS = "semantics"         # Code meaning and relationships
    DOCUMENTATION = "documentation"  # Comments, docs, examples
    STRUCTURE = "structure"         # Project/file organization
    CODE_PATTERNS = "code_patterns" # Common coding patterns and practices
    LEARNING = "learning"           # Repository learning patterns
    CONTEXT = "context"            # Contextual information about code
    DEPENDENCIES = "dependencies"   # Project dependencies and imports
    BEST_PRACTICES = "best_practices" # Language-specific best practices
    COMMON_ISSUES = "common_issues"  # Frequently encountered problems
    USER_PATTERNS = "user_patterns"  # User's coding style and preferences

class PatternPurpose(Enum):
    """The purpose/intent of a pattern."""
    UNDERSTANDING = "understanding"   # For understanding code structure
    MODIFICATION = "modification"     # For making code changes
    VALIDATION = "validation"        # For validating code quality
    LEARNING = "learning"            # For learning from code
    GENERATION = "generation"        # For generating new code
    EXPLANATION = "explanation"      # For explaining code to users
    SUGGESTION = "suggestion"        # For making improvement suggestions
    DEBUGGING = "debugging"          # For finding and fixing bugs
    COMPLETION = "completion"        # For code completion suggestions
    REFACTORING = "refactoring"     # For code restructuring
    DOCUMENTATION = "documentation"  # For generating/updating docs

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

class InteractionType(Enum):
    """Types of AI-user interactions."""
    QUESTION = "question"           # User asked a question
    MODIFICATION = "modification"   # User wants to modify code
    ERROR = "error"                # User has an error
    COMPLETION = "completion"      # User wants code completion
    EXPLANATION = "explanation"    # User wants explanation
    SUGGESTION = "suggestion"      # User wants suggestions
    DOCUMENTATION = "documentation" # User wants documentation

class ConfidenceLevel(Enum):
    """Confidence levels for AI decisions."""
    HIGH = "high"         # AI is very confident (0.8-1.0)
    MEDIUM = "medium"     # AI is moderately confident (0.5-0.8)
    LOW = "low"          # AI is not very confident (0.2-0.5)
    UNCERTAIN = "uncertain" # AI is uncertain (<0.2)

class AICapability(Enum):
    """AI-specific capabilities."""
    CODE_UNDERSTANDING = "code_understanding"
    CODE_GENERATION = "code_generation"
    CODE_MODIFICATION = "code_modification"
    CODE_REVIEW = "code_review"
    DOCUMENTATION = "documentation"
    LEARNING = "learning"

class AIConfidenceMetrics(Enum):
    """Metrics for AI confidence calculation."""
    PATTERN_MATCH = "pattern_match"
    CONTEXT_RELEVANCE = "context_relevance"
    USER_HISTORY = "user_history"
    PROJECT_RELEVANCE = "project_relevance"
    LANGUAGE_SUPPORT = "language_support"

class DeepLearningCapability(Enum):
    """Deep learning capabilities."""
    PATTERN_LEARNING = "pattern_learning"
    CROSS_REPO_ANALYSIS = "cross_repo_analysis"
    PATTERN_RELATIONSHIPS = "pattern_relationships"
    PATTERN_EVOLUTION = "pattern_evolution"

class PatternRelationType(Enum):
    """Types of pattern relationships."""
    DEPENDENCY = "dependency"
    SIMILARITY = "similarity"
    CONFLICT = "conflict"
    EVOLUTION = "evolution"

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
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

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
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

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
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

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
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

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
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

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
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

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
    category: PatternCategory = PatternCategory.SYNTAX
    purpose: PatternPurpose = PatternPurpose.UNDERSTANDING

@dataclass
class QueryPattern:
    """Pattern for querying code."""
    pattern: str
    extract: Optional[Callable] = None
    description: Optional[str] = None
    examples: List[str] = field(default_factory=list)
    category: PatternCategory = PatternCategory.SYNTAX
    purpose: PatternPurpose = PatternPurpose.UNDERSTANDING
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

@dataclass
class InteractionContext:
    """Context for a single interaction."""
    interaction_type: InteractionType
    cursor_position: Optional[int] = None
    selected_text: Optional[str] = None
    current_file: Optional[str] = None
    visible_range: Optional[tuple[int, int]] = None
    user_input: Optional[str] = None
    confidence: float = 1.0

@dataclass
class UserContext:
    """Context about the user's preferences and patterns."""
    preferred_style: Dict[str, Any] = field(default_factory=dict)
    common_patterns: List[str] = field(default_factory=list)
    recent_interactions: List[Dict[str, Any]] = field(default_factory=list)
    language_preferences: Dict[str, Any] = field(default_factory=dict)
    skill_level: Dict[str, float] = field(default_factory=dict)

@dataclass
class ProjectContext:
    """Context about the project."""
    language_id: str
    file_type: FileType
    dependencies: Dict[str, Any] = field(default_factory=dict)
    project_patterns: Dict[str, Any] = field(default_factory=dict)
    style_guide: Dict[str, Any] = field(default_factory=dict)
    known_issues: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class AIContext:
    """Enhanced AI context with learning capabilities."""
    interaction: InteractionContext
    user: UserContext
    project: ProjectContext
    capabilities: Set[AICapability] = field(default_factory=set)
    confidence_metrics: Dict[AIConfidenceMetrics, float] = field(default_factory=dict)
    learned_patterns: Dict[str, Any] = field(default_factory=dict)
    success_metrics: Dict[str, float] = field(default_factory=dict)
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize AI context resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("ai context initialization"):
                    # Initialize nested resources
                    await self.interaction.initialize()
                    await self.user.initialize()
                    await self.project.initialize()
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing AI context: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up AI context resources."""
        try:
            # Clean up nested resources
            await self.interaction.cleanup()
            await self.user.cleanup()
            await self.project.cleanup()
            
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up AI context: {e}", level="error")

@dataclass
class AIProcessingResult:
    """Result of AI-assisted processing."""
    success: bool
    response: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    context_info: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    learned_patterns: List[Dict[str, Any]] = field(default_factory=list)
    ai_insights: Dict[str, Any] = field(default_factory=dict)
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize AI processing result resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("ai processing result initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing AI processing result: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up AI processing result resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up AI processing result: {e}", level="error")
