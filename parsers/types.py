"""Common types and enums for parsers."""

from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field

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

@dataclass
class ParserConfig:
    """Parser configuration."""
    max_file_size: int = 1024 * 1024  # 1MB
    timeout_ms: int = 5000
    cache_results: bool = True
    include_comments: bool = True

@dataclass
class ParsingStatistics:
    """Parsing performance statistics."""
    parse_time_ms: float = 0.0
    feature_extraction_time_ms: float = 0.0
    node_count: int = 0
    error_count: int = 0

@dataclass
class Documentation:
    """Documentation features."""
    docstrings: List[Dict[str, Any]] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    todos: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: str = ""

@dataclass
class ComplexityMetrics:
    """Code complexity metrics."""
    cyclomatic: int = 0
    cognitive: int = 0
    halstead: Dict[str, float] = field(default_factory=dict)
    maintainability_index: float = 0.0
    lines_of_code: Dict[str, int] = field(default_factory=dict)

@dataclass
class ExtractedFeatures:
    """Extracted feature container."""
    features: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    documentation: Documentation = field(default_factory=Documentation)
    metrics: ComplexityMetrics = field(default_factory=ComplexityMetrics)

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
