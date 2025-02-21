"""Shared data models for the parser system."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Union
from enum import Enum
from datetime import datetime

class ParserType(Enum):
    """Types of supported parsers."""
    TREE_SITTER = "tree-sitter"
    CUSTOM = "custom"
    MARKUP = "markup"
    UNKNOWN = "unknown"

class FeatureCategory(Enum):
    """Categories for code features."""
    SYNTAX = "syntax"
    STRUCTURE = "structure"
    SEMANTICS = "semantics"
    DOCUMENTATION = "documentation"

@dataclass
class Position:
    """Source code position."""
    line: int
    column: int
    offset: int = 0

@dataclass
class SourceRange:
    """Range in source code."""
    start: Position
    end: Position
    text: str = ""

@dataclass
class ParserResult:
    """Unified parser result."""
    success: bool = True
    language: str = ""
    file_type: str = ""
    ast: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, Any]] = None
    documentation: Optional[Dict[str, Any]] = None
    complexity: Optional[Dict[str, Any]] = None
    source_code: str = ""
    total_lines: int = 0
    statistics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @classmethod
    def error(cls, message: str) -> 'ParserResult':
        return cls(success=False, error=message)

@dataclass
class ExtractedFeatures:
    """Container for extracted features."""
    syntax: Dict[str, List[Dict]] = field(default_factory=lambda: {
        'literals': [], 'operators': [], 'keywords': [], 'identifiers': []
    })
    structure: Dict[str, List[Dict]] = field(default_factory=lambda: {
        'functions': [], 'classes': [], 'modules': [], 'blocks': []
    })
    semantics: Dict[str, List[Dict]] = field(default_factory=lambda: {
        'imports': [], 'references': [], 'dependencies': [], 'types': []
    })
    documentation: Optional['Documentation'] = None
    metrics: Optional['ComplexityMetrics'] = None

@dataclass
class Documentation:
    """Unified documentation structure."""
    comments: List[Union[Dict, str]] = field(default_factory=list)
    docstrings: List[Union[Dict, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    annotations: List[Union[Dict, str]] = field(default_factory=list)
    description: Optional[str] = None
    admonitions: List[str] = field(default_factory=list)
    fields: Dict[str, str] = field(default_factory=dict)

@dataclass
class ComplexityMetrics:
    """Code complexity metrics."""
    cyclomatic: int = 0
    cognitive: int = 0
    halstead: Dict[str, float] = field(default_factory=dict)
    maintainability_index: float = 0.0
    node_count: int = 0
    depth: int = 0

@dataclass
class ParserConfig:
    """Parser configuration."""
    max_file_size: int = 1024 * 1024  # 1MB
    timeout: int = 30  # seconds
    cache_enabled: bool = True
    cache_size: int = 1000
    extract_docs: bool = True
    calculate_metrics: bool = True

@dataclass
class ParsingStatistics:
    """Parser performance statistics."""
    parse_time_ms: float = 0.0
    feature_extraction_time_ms: float = 0.0
    documentation_extraction_time_ms: float = 0.0
    complexity_calculation_time_ms: float = 0.0
    total_time_ms: float = 0.0
    total_nodes_processed: int = 0
    memory_used_kb: float = 0.0

@dataclass
class LanguageFeatures:
    """Language-specific features."""
    supports_types: bool = False
    supports_classes: bool = False
    supports_functions: bool = False
    supports_modules: bool = False
    supports_decorators: bool = False
    supports_async: bool = False
    supports_generics: bool = False
    file_extensions: Set[str] = field(default_factory=set)
    comment_styles: Set[str] = field(default_factory=set)
    string_delimiters: Set[str] = field(default_factory=set)

@dataclass
class CodeSymbol:
    """Code symbol information."""
    name: str
    symbol_type: str
    location: SourceRange
    scope: str
    documentation: Optional[str] = None
    signature: Optional[str] = None
    references: List[SourceRange] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FileInfo:
    """File information."""
    path: str
    language: str
    encoding: str = "utf-8"
    size: int = 0
    last_modified: datetime = field(default_factory=datetime.now)
    hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CacheConfig:
    """Cache configuration."""
    enabled: bool = True
    max_size: int = 1000
    ttl_seconds: int = 3600
    persist: bool = False
    persist_path: Optional[str] = None 