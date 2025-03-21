"""Type definitions for the parser system.

This module defines the core types used throughout the parser system, including
enums, dataclasses, and type aliases.
"""

from typing import Dict, Any, List, Optional, Union, Set, Callable
from enum import Enum, auto
from dataclasses import dataclass, field
from parsers.language_mapping import normalize_language_name
import asyncio
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.logger import log
from utils.shutdown import register_shutdown_handler
from tree_sitter_language_pack import SupportedLanguage

class FileType(str, Enum):
    """File type enumeration."""
    CODE = "code"
    BINARY = "binary"
    TEXT = "text"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"

class ParserType(str, Enum):
    """Parser type enumeration with enhanced functionality."""
    TREE_SITTER = "tree-sitter"
    CUSTOM = "custom"
    UNKNOWN = "unknown"

    @classmethod
    def from_language(cls, language_id: str) -> 'ParserType':
        """Get parser type for a language.
        
        Args:
            language_id: Language identifier
            
        Returns:
            ParserType: The appropriate parser type
        """
        normalized = normalize_language_name(language_id)
        if normalized in SupportedLanguage.__args__:
            return cls.TREE_SITTER
        elif normalized in CUSTOM_PARSER_CLASSES:
            return cls.CUSTOM
        return cls.UNKNOWN

    @property
    def supports_caching(self) -> bool:
        """Whether this parser type supports caching."""
        return self in {self.CUSTOM, self.TREE_SITTER}

    @property
    def supports_ai(self) -> bool:
        """Whether this parser type supports AI capabilities."""
        return self in {self.CUSTOM, self.TREE_SITTER}

class SupportLevel(str, Enum):
    """Language support level enumeration."""
    STABLE = "stable"
    BETA = "beta"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"
    UNSUPPORTED = "unsupported"

class FeatureCategory(str, Enum):
    """Feature category enumeration."""
    SYNTAX = "syntax"
    SEMANTICS = "semantics"
    DOCUMENTATION = "documentation"
    STRUCTURE = "structure"
    DEPENDENCIES = "dependencies"
    PATTERNS = "patterns"
    METRICS = "metrics"
    CUSTOM = "custom"

class PatternCategory(str, Enum):
    """Pattern category enumeration."""
    SYNTAX = "syntax"
    SEMANTICS = "semantics"
    DOCUMENTATION = "documentation"
    STRUCTURE = "structure"
    DEPENDENCIES = "dependencies"
    CODE_PATTERNS = "code_patterns"
    BEST_PRACTICES = "best_practices"
    COMMON_ISSUES = "common_issues"
    USER_PATTERNS = "user_patterns"

class PatternPurpose(str, Enum):
    """Pattern purpose enumeration."""
    UNDERSTANDING = "understanding"
    GENERATION = "generation"
    MODIFICATION = "modification"
    REVIEW = "review"
    LEARNING = "learning"

class AICapability(str, Enum):
    """AI capability enumeration."""
    CODE_UNDERSTANDING = "code_understanding"
    CODE_GENERATION = "code_generation"
    CODE_MODIFICATION = "code_modification"
    CODE_REVIEW = "code_review"
    DOCUMENTATION = "documentation"
    LEARNING = "learning"

class InteractionType(str, Enum):
    """Interaction type enumeration."""
    UNDERSTANDING = "understanding"
    GENERATION = "generation"
    MODIFICATION = "modification"
    REVIEW = "review"
    LEARNING = "learning"

class ConfidenceLevel(str, Enum):
    """Confidence level enumeration."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

class PatternType(str, Enum):
    """Types of patterns that can be extracted from repositories."""
    CODE_STRUCTURE = "code_structure"
    CODE_NAMING = "code_naming"
    ERROR_HANDLING = "error_handling"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    COMPONENT_DEPENDENCY = "component_dependency"

class PatternRelationType(str, Enum):
    """Types of relationships between patterns."""
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"
    USES = "uses"
    REFERENCES = "references"
    CONFLICTS_WITH = "conflicts_with"
    COMPLEMENTS = "complements"
    REPLACES = "replaces"
    UNKNOWN = "unknown"

@dataclass
class PatternDefinition:
    """Definition of a code pattern."""
    name: str
    description: str
    pattern: str
    category: PatternCategory
    purpose: PatternPurpose
    language_id: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PatternRelationship:
    """Relationship between patterns."""
    source_pattern: str
    target_pattern: str
    relationship_type: PatternRelationType
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Pattern:
    """Base class for all pattern types."""
    name: str
    pattern: str
    language_id: str
    category: PatternCategory = PatternCategory.CODE_PATTERNS
    purpose: PatternPurpose = PatternPurpose.UNDERSTANDING
    description: str = ""
    examples: List[str] = field(default_factory=list)
    confidence: float = 0.0
    is_active: bool = True
    is_system: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation_rules: List[str] = field(default_factory=list)
    relationships: List[PatternRelationship] = field(default_factory=list)

@dataclass
class QueryPattern:
    """Pattern used for querying code."""
    name: str
    pattern: str
    category: PatternCategory
    purpose: PatternPurpose
    language_id: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    extract: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    is_tree_sitter: bool = field(default=False, init=False)
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        # Determine if this is a tree-sitter pattern based on language support
        from tree_sitter_language_pack import SupportedLanguage
        from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
        
        normalized_lang = self.language_id.lower().replace("-", "_").replace(" ", "_")
        self.is_tree_sitter = normalized_lang in SupportedLanguage.__args__
        
        # Validate pattern based on type
        if self.is_tree_sitter:
            # Tree-sitter patterns should be valid queries
            try:
                from tree_sitter_language_pack import get_language
                language = get_language(normalized_lang)
                if language:
                    language.query(self.pattern)
            except Exception as e:
                raise ValueError(f"Invalid tree-sitter query for {self.language_id}: {e}")
        else:
            # Custom patterns should be valid regex
            import re
            try:
                re.compile(self.pattern)
            except Exception as e:
                raise ValueError(f"Invalid regex pattern for {self.language_id}: {e}")
    
    def matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Get matches for this pattern in source code.
        
        Args:
            source_code: Source code to match against
            
        Returns:
            List of matches with metadata
        """
        if self.is_tree_sitter:
            return self._tree_sitter_matches(source_code)
        else:
            return self._regex_matches(source_code)
    
    def _tree_sitter_matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Get matches using tree-sitter."""
        try:
            from tree_sitter_language_pack import get_parser, get_language
            
            # Get tree-sitter components
            parser = get_parser(self.language_id)
            language = get_language(self.language_id)
            
            if not parser or not language:
                raise ValueError(f"Failed to get tree-sitter components for {self.language_id}")
            
            # Parse and query
            tree = parser.parse(bytes(source_code, "utf8"))
            query = language.query(self.pattern)
            matches = query.matches(tree.root_node)
            
            # Process matches
            results = []
            for match in matches:
                match_data = {
                    "node": match.pattern_node,
                    "captures": {c.name: c.node for c in match.captures}
                }
                
                # Apply extraction function if provided
                if self.extract:
                    try:
                        extracted = self.extract(match_data)
                        if extracted:
                            match_data.update(extracted)
                    except Exception:
                        pass
                
                results.append(match_data)
            
            return results
            
        except Exception as e:
            raise ValueError(f"Error in tree-sitter matching: {e}")
    
    def _regex_matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Get matches using regex."""
        try:
            import re
            results = []
            
            # Find all matches
            for match in re.finditer(self.pattern, source_code, re.MULTILINE | re.DOTALL):
                match_data = {
                    "text": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "groups": match.groups(),
                    "named_groups": match.groupdict()
                }
                
                # Apply extraction function if provided
                if self.extract:
                    try:
                        extracted = self.extract(match_data)
                        if extracted:
                            match_data.update(extracted)
                    except Exception:
                        pass
                
                results.append(match_data)
            
            return results
            
        except Exception as e:
            raise ValueError(f"Error in regex matching: {e}")

@dataclass
class LanguageConfig:
    """Language configuration."""
    language_id: str
    name: str
    file_extensions: Set[str] = field(default_factory=set)
    file_patterns: List[str] = field(default_factory=list)
    parser_type: ParserType = ParserType.UNKNOWN
    features: Dict[str, Any] = field(default_factory=dict)
    support_level: str = "experimental"
    capabilities: Set[AICapability] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LanguageFeatures:
    """Language features."""
    syntax: Dict[str, Any] = field(default_factory=dict)
    semantics: Dict[str, Any] = field(default_factory=dict)
    documentation: Dict[str, Any] = field(default_factory=dict)
    structure: Dict[str, Any] = field(default_factory=dict)
    dependencies: Dict[str, Any] = field(default_factory=dict)
    patterns: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    custom: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LanguageSupport:
    """Language support configuration."""
    level: str = "experimental"
    supports_tree_sitter: bool = False
    supports_custom_parser: bool = False
    supports_ai: bool = False
    capabilities: Set[AICapability] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LanguageMapping:
    """Language mapping configuration."""
    language_id: str
    extensions: Set[str] = field(default_factory=set)
    patterns: List[str] = field(default_factory=list)
    shebang_patterns: List[str] = field(default_factory=list)
    filenames: Set[str] = field(default_factory=set)
    directories: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AIConfidenceMetrics:
    """Metrics for AI confidence in processing results."""
    overall_confidence: float = 0.0
    pattern_matches: Dict[str, float] = field(default_factory=dict)
    context_relevance: float = 0.0
    semantic_similarity: float = 0.0
    code_quality: float = 0.0
    documentation_quality: float = 0.0
    learning_progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Documentation:
    """Documentation features."""
    docstrings: List[Dict[str, Any]] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    todos: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    content: str = ""

@dataclass
class ComplexityMetrics:
    """Code complexity metrics."""
    lines_of_code: Dict[str, int] = field(default_factory=lambda: {
        'total': 0,
        'code': 0,
        'comment': 0,
        'blank': 0
    })
    cyclomatic: int = 1
    cognitive: int = 0
    maintainability: float = 0.0
    testability: float = 0.0
    reusability: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExtractedFeatures:
    """Extracted code features."""
    features: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    documentation: Documentation = field(default_factory=Documentation)
    metrics: ComplexityMetrics = field(default_factory=ComplexityMetrics)

@dataclass
class AIContext:
    """Context for AI processing."""
    language_id: str
    file_type: FileType
    interaction_type: InteractionType
    repository_id: Optional[int] = None
    file_path: Optional[str] = None
    commit_hash: Optional[str] = None
    branch_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AIProcessingResult:
    """Result of AI processing."""
    success: bool = False
    response: Optional[str] = None
    context_info: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    ai_insights: Dict[str, Any] = field(default_factory=dict)
    learned_patterns: List[Dict[str, Any]] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    execution_time: float = 0.0
    confidence_metrics: AIConfidenceMetrics = field(default_factory=AIConfidenceMetrics)

@dataclass
class ParserResult:
    """Result of parsing a file."""
    success: bool = False
    file_type: FileType = FileType.UNKNOWN
    parser_type: ParserType = ParserType.UNKNOWN
    language: Optional[str] = None
    features: ExtractedFeatures = field(default_factory=ExtractedFeatures)
    ast: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: ComplexityMetrics = field(default_factory=ComplexityMetrics)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PatternInfo:
    """Information about a pattern."""
    name: str
    description: str
    examples: List[str]
    category: PatternCategory
    purpose: PatternPurpose
    language_id: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PatternContext:
    """Context information for pattern matching."""
    code_structure: Dict[str, Any] = field(default_factory=dict)
    language_stats: Dict[str, Any] = field(default_factory=dict)
    project_patterns: List[Dict[str, Any]] = field(default_factory=list)
    file_location: str = ""
    dependencies: Set[str] = field(default_factory=set)
    recent_changes: List[Dict[str, Any]] = field(default_factory=list)
    scope_level: str = "global"
    allows_nesting: bool = True
    relevant_patterns: List[str] = field(default_factory=list)

@dataclass
class PatternPerformanceMetrics:
    """Performance metrics for pattern matching."""
    execution_time: float = 0.0
    memory_usage: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    error_count: int = 0
    success_rate: float = 0.0
    pattern_stats: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PatternValidationResult:
    """Result of pattern validation."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validation_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PatternMatchResult:
    """Result of pattern matching."""
    pattern_name: str
    matches: List[Dict[str, Any]]
    context: PatternContext
    relationships: List[PatternRelationship] = field(default_factory=list)
    performance: PatternPerformanceMetrics = field(default_factory=PatternPerformanceMetrics)
    validation: PatternValidationResult = field(default_factory=PatternValidationResult)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BaseFeatureExtractor:
    """Base class for feature extraction."""
    language_id: str
    features: ExtractedFeatures = field(default_factory=ExtractedFeatures)
    documentation: Documentation = field(default_factory=Documentation)
    metrics: ComplexityMetrics = field(default_factory=ComplexityMetrics)
    metadata: Dict[str, Any] = field(default_factory=dict)

    async def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features from AST.
        
        Args:
            ast: The AST to extract features from
            source_code: The original source code
            
        Returns:
            ExtractedFeatures: The extracted features
        """
        raise NotImplementedError("Subclasses must implement extract_features")

@dataclass
class ExtractedBlock:
    """Extracted code block."""
    content: str
    start_line: int
    end_line: int
    block_type: str
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class BlockType(str, Enum):
    """Types of code blocks that can be extracted."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"
    COMMENT = "comment"
    DOCSTRING = "docstring"
    DECORATOR = "decorator"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    ERROR_HANDLING = "error_handling"
    UNKNOWN = "unknown"

@dataclass
class BlockValidationResult:
    """Result of validating an extracted code block."""
    is_valid: bool = True
    block_type: BlockType = BlockType.UNKNOWN
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validation_time: float = 0.0
    syntax_valid: bool = True
    semantic_valid: bool = True
    context_valid: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

# Export public interfaces
__all__ = [
    'FileType',
    'ParserType',
    'SupportLevel',
    'FeatureCategory',
    'PatternCategory',
    'PatternPurpose',
    'AICapability',
    'InteractionType',
    'ConfidenceLevel',
    'PatternType',
    'PatternRelationType',
    'PatternDefinition',
    'Pattern',
    'QueryPattern',
    'LanguageConfig',
    'LanguageFeatures',
    'LanguageSupport',
    'LanguageMapping',
    'Documentation',
    'ComplexityMetrics',
    'ExtractedFeatures',
    'AIContext',
    'AIProcessingResult',
    'ParserResult',
    'PatternInfo',
    'PatternContext',
    'PatternRelationship',
    'PatternPerformanceMetrics',
    'PatternValidationResult',
    'PatternMatchResult',
    'BlockType',
    'BlockValidationResult',
    'ExtractedBlock',
    'BaseFeatureExtractor'
]
