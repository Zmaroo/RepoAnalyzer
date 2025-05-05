"""Type definitions for the parser system.

This module defines the core types used throughout the parser system, including
enums, dataclasses, and type aliases.
"""

from typing import Dict, Any, List, Optional, Union, Set, Callable
from enum import Enum, auto
from dataclasses import dataclass, field
# Remove circular import
# from parsers.language_mapping import normalize_language_name, normalize_and_check_tree_sitter_support
import asyncio
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.logger import log
from utils.shutdown import register_shutdown_handler
from tree_sitter_language_pack import SupportedLanguage
import time

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
        # Normalize language name
        normalized = language_id.lower().replace(' ', '_').replace('-', '_')
        
        # Check if supported by tree-sitter
        if normalized in SupportedLanguage.__args__:
            return cls.TREE_SITTER
            
        # Lazy import to avoid circular dependency
        # Check if a custom parser is available
        try:
            from parsers.custom_parsers import get_custom_parser_classes
            if normalized in get_custom_parser_classes():
                return cls.CUSTOM
        except ImportError:
            pass
            
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
    
    # Language and format specific capabilities
    MARKUP = "markup"
    DATA_SERIALIZATION = "data_serialization"
    SCHEMA_VALIDATION = "schema_validation"
    STRUCTURED_DATA = "structured_data"
    
    # Programming paradigms
    FUNCTIONAL_PROGRAMMING = "functional_programming"
    OBJECT_ORIENTED = "object_oriented"
    CONCURRENT_PROGRAMMING = "concurrent_programming"
    
    # Technical domains
    API_DESIGN = "api_design"
    TYPE_CHECKING = "type_checking"
    TYPE_INFERENCE = "type_inference"
    TYPE_SYSTEM = "type_system"
    MEMORY_MANAGEMENT = "memory_management"
    MEMORY_SAFETY = "memory_safety"
    POINTER_ANALYSIS = "pointer_analysis"
    
    # Web and UI development
    WEB_DEVELOPMENT = "web_development"
    MOBILE_DEVELOPMENT = "mobile_development"
    RESPONSIVE_DESIGN = "responsive_design"
    UI_COMPONENTS = "ui_components"
    STYLING = "styling"
    
    # Framework specific
    REACT_INTEGRATION = "react_integration"
    NODE_INTEGRATION = "node_integration"
    FLUTTER_SUPPORT = "flutter_support"
    
    # File operations
    CONFIGURATION = "configuration"
    ENVIRONMENT_VARIABLES = "environment_variables"
    VERSION_CONTROL = "version_control"
    FILE_PATTERNS = "file_patterns"
    
    # Systems programming
    CONCURRENCY = "concurrency"
    PARALLEL_PROCESSING = "parallel_processing"
    SYSTEMS_PROGRAMMING = "systems_programming"
    PROCESS_MANAGEMENT = "process_management"
    
    # DevOps related
    CONTAINERIZATION = "containerization"
    DEPLOYMENT = "deployment"
    BUILD_SYSTEM = "build_system"
    
    # Languages and paradigms
    JSX_SUPPORT = "jsx_support"
    LISP_SUPPORT = "lisp_support"
    MACRO_SUPPORT = "macro_support"
    ASYNC_SUPPORT = "async_support"
    SHELL_SCRIPTING = "shell_scripting"
    
    # Database related
    QUERY_OPTIMIZATION = "query_optimization"
    SCHEMA_DESIGN = "schema_design"
    DATA_MANIPULATION = "data_manipulation"
    
    # Domain specific
    GPU_COMPUTING = "gpu_computing"
    PATTERN_MATCHING = "pattern_matching"
    INTERFACE_GENERATION = "interface_generation"
    DEPENDENCY_MANAGEMENT = "dependency_management"
    PACKAGE_MANAGEMENT = "package_management"
    SECURITY = "security"
    NPM_ECOSYSTEM = "npm_ecosystem"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"

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
    """Types of patterns that can be extracted from repositories.
    
    This is the canonical definition used throughout the codebase for pattern types.
    """
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
    """Pattern used for querying code.
    
    This class supports both tree-sitter and custom regex parsers with a unified
    interface. It includes features for validation, metadata, and efficient pattern matching.
    """
    name: str
    pattern: str  # Tree-sitter query pattern
    category: PatternCategory
    purpose: PatternPurpose
    language_id: str
    confidence: float = 0.8
    metadata: Dict[str, Any] = field(default_factory=dict)
    extract: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    regex_pattern: Optional[str] = None  # Pattern for custom parsers
    test_cases: Optional[List[Dict[str, Any]]] = None
    block_type: Optional[str] = None
    contains_blocks: List[str] = field(default_factory=list)
    is_nestable: bool = False
    extraction_priority: int = 0
    adaptable: bool = True
    confidence_threshold: float = 0.7
    learning_examples: List[str] = field(default_factory=list)
    
    # Internal fields
    is_tree_sitter: bool = field(default=False, init=False)
    is_regex: bool = field(default=False, init=False)
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        # Normalize language ID
        normalized_lang = self.language_id.lower().replace(' ', '_').replace('-', '_')
        self.language_id = normalized_lang

        # ---
        # IMPORTANT: If a regex_pattern is provided, this pattern should be treated as regex-only.
        # Tree-sitter validation and matching must be skipped, even if a tree-sitter pattern string is present
        # or the language is supported by tree-sitter. This prevents accidental validation errors for regex patterns.
        # ---
        if self.regex_pattern:
            self.is_regex = True
            self.is_tree_sitter = False
        else:
            self.is_tree_sitter = bool(normalized_lang in SupportedLanguage.__args__ and self.pattern)
            self.is_regex = False
        
        # Initialize metadata if not provided
        if not self.metadata:
            self.metadata = {
                "name": self.name,
                "category": self.category.value,
                "purpose": self.purpose.value,
                "language_id": self.language_id,
                "created_at": None,  # Will be set on first use
                "updated_at": None,
                "version": "1.0",
                "supports_tree_sitter": self.is_tree_sitter,
                "supports_regex": self.is_regex,
                # Add relationship metadata
                "relationships": {
                    "depends_on": [],
                    "related_to": [],
                    "conflicts_with": []
                },
                # Add metrics metadata
                "metrics": {
                    "avg_match_time": 0.0,
                    "match_count": 0,
                    "success_rate": 0.0
                },
                # Add validation results
                "validation": {
                    "is_valid": True,
                    "test_results": {},
                    "last_validated": None
                },
                # Add block extraction info
                "block_extraction": {
                    "block_type": self.block_type,
                    "contains_blocks": self.contains_blocks,
                    "is_nestable": self.is_nestable,
                    "extraction_priority": self.extraction_priority,
                    "supports_named_captures": True,
                    "capture_groups": []
                },
                # Add AI learning support
                "ai_learning": {
                    "adaptable": self.adaptable,
                    "confidence_threshold": self.confidence_threshold,
                    "learning_examples": self.learning_examples,
                    "can_be_improved": True,
                    "learning_rate": 0.1,
                    "last_improved": None
                },
                # Add export compatibility 
                "export": {
                    "formats": ["json", "yaml", "xml"],
                    "is_portable": True
                }
            }
        
        # Validate patterns
        self._validate_patterns()
        
        # Extract capture groups for metadata
        if self.is_tree_sitter or self.is_regex:
            capture_groups = self._extract_capture_groups()
            # Ensure 'block_extraction' exists in metadata
            if "block_extraction" not in self.metadata or not isinstance(self.metadata["block_extraction"], dict):
                self.metadata["block_extraction"] = {
                    "block_type": self.block_type,
                    "contains_blocks": self.contains_blocks,
                    "is_nestable": self.is_nestable,
                    "extraction_priority": self.extraction_priority,
                    "supports_named_captures": True,
                    "capture_groups": []
                }
            self.metadata["block_extraction"]["capture_groups"] = capture_groups
        
        # Run test cases if provided
        if self.test_cases:
            self._validate_with_test_cases()
    
    def _validate_patterns(self):
        """Validate tree-sitter and regex patterns."""
        # Validate tree-sitter pattern
        if self.is_tree_sitter:
            try:
                from tree_sitter_language_pack import get_language
                language = get_language(self.language_id)
                if language:
                    language.query(self.pattern)
            except Exception as e:
                raise ValueError(f"Invalid tree-sitter query for {self.language_id}: {e}")
        
        # Validate regex pattern
        if self.is_regex:
            import re
            try:
                re.compile(self.regex_pattern)
            except Exception as e:
                raise ValueError(f"Invalid regex pattern for {self.language_id}: {e}")
    
    def _extract_capture_groups(self) -> List[str]:
        """Extract capture groups from patterns.
        
        Returns:
            List of capture group names
        """
        capture_groups = []
        
        # Extract from tree-sitter pattern
        if self.is_tree_sitter:
            import re
            # Look for @name in tree-sitter pattern
            captures = re.findall(r'@([a-zA-Z_][a-zA-Z0-9_]*)', self.pattern)
            capture_groups.extend(captures)
        
        # Extract from regex pattern
        if self.is_regex:
            import re
            # Look for named capture groups (?P<name>...)
            named_captures = re.findall(r'\(\?P<([a-zA-Z_][a-zA-Z0-9_]*)>', self.regex_pattern)
            capture_groups.extend(named_captures)
        
        return list(set(capture_groups))  # Remove duplicates
    
    def _validate_with_test_cases(self):
        """Validate pattern against test cases."""
        if not self.test_cases:
            return
            
        validation_results = {"passed": 0, "failed": 0, "tests": []}
        
        for i, test_case in enumerate(self.test_cases):
            test_input = test_case.get("input", "")
            expected = test_case.get("expected", True)
            
            try:
                # Run test with both parser types if available
                results = {}
                
                if self.is_tree_sitter:
                    ts_matches = self._tree_sitter_matches(test_input)
                    results["tree_sitter"] = ts_matches
                
                if self.is_regex:
                    regex_matches = self._regex_matches(test_input)
                    results["regex"] = regex_matches
                
                # Determine if test passed
                passed = False
                
                if expected is True:
                    # Test passes if any parser type returns matches
                    passed = any(bool(matches) for matches in results.values())
                elif expected is False:
                    # Test passes if no parser type returns matches
                    passed = all(not bool(matches) for matches in results.values())
                elif isinstance(expected, dict):
                    # Test passes if any match contains all expected key-value pairs
                    passed = any(
                        all(match.get(k) == v for k, v in expected.items())
                        for matches in results.values()
                        for match in matches
                    )
                elif isinstance(expected, list) and len(expected) > 0:
                    # Test passes if number of matches matches expected count
                    passed = any(len(matches) == len(expected) for matches in results.values())
                
                # Record test result
                validation_results["tests"].append({
                    "test_id": i,
                    "input": test_input,
                    "expected": expected,
                    "results": results,
                    "passed": passed
                })
                
                if passed:
                    validation_results["passed"] += 1
                else:
                    validation_results["failed"] += 1
                
            except Exception as e:
                # Record test error
                validation_results["tests"].append({
                    "test_id": i,
                    "input": test_input,
                    "expected": expected,
                    "error": str(e),
                    "passed": False
                })
                validation_results["failed"] += 1
        
        # Update validation metadata
        # Ensure 'validation' is a dict before assignment
        if not isinstance(self.metadata.get("validation"), dict):
            from dataclasses import asdict
            val = self.metadata.get("validation")
            if hasattr(val, "__dataclass_fields__"):
                self.metadata["validation"] = asdict(val)
            else:
                self.metadata["validation"] = {}
        self.metadata["validation"]["test_results"] = validation_results
        self.metadata["validation"]["is_valid"] = validation_results["failed"] == 0
        self.metadata["validation"]["last_validated"] = time.time()
    
    async def matches(self, source_code: str, context: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Get matches for this pattern in source code.
        
        Args:
            source_code: Source code to match against
            context: Optional context information
            
        Returns:
            List of matches with metadata
        """
        start_time = time.time()
        
        if not source_code:
            return []
        
        # Determine parser type from context if provided
        parser_type = None
        if context and hasattr(context, 'parser_type'):
            parser_type = context.parser_type
        
        results = []
        
        # Use specified parser type or try both
        if parser_type == ParserType.TREE_SITTER and self.is_tree_sitter:
            results = self._tree_sitter_matches(source_code)
        elif parser_type == ParserType.CUSTOM and self.is_regex:
            results = self._regex_matches(source_code)
        else:
            # Try tree-sitter first, then regex
            if self.is_tree_sitter:
                results = self._tree_sitter_matches(source_code)
            
            # If no results and regex is available, try regex
            if not results and self.is_regex:
                results = self._regex_matches(source_code)
        
        # Update metrics
        execution_time = time.time() - start_time
        if "metrics" in self.metadata:
            metrics = self.metadata["metrics"]
            metrics["match_count"] = metrics.get("match_count", 0) + 1
            metrics["avg_match_time"] = (
                (metrics.get("avg_match_time", 0) * (metrics.get("match_count", 1) - 1) + execution_time) / 
                metrics.get("match_count", 1)
            )
            metrics["success_rate"] = (
                (metrics.get("success_rate", 0) * (metrics.get("match_count", 1) - 1) + (1 if results else 0)) / 
                metrics.get("match_count", 1)
            )
        
        # Update metadata timestamps
        if not self.metadata.get("created_at"):
            self.metadata["created_at"] = time.time()
        self.metadata["updated_at"] = time.time()
        
        return results
    
    def _tree_sitter_matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Get matches using tree-sitter.
        
        Args:
            source_code: Source code to match against
            
        Returns:
            List of matches with metadata
        """
        if not self.is_tree_sitter:
            return []
            
        try:
            from tree_sitter_language_pack import get_parser, get_language
            
            # Get tree-sitter components
            parser = get_parser(self.language_id)
            language = get_language(self.language_id)
            
            if not parser or not language:
                return []
            
            # Parse and query
            bytes_source = bytes(source_code, "utf8")
            tree = parser.parse(bytes_source)
            query = language.query(self.pattern)
            matches = query.matches(tree.root_node)
            
            # Process matches
            results = []
            for match in matches:
                match_data = {
                    "node": match.pattern_node,
                    "captures": {c.name: c.node for c in match.captures},
                    "pattern_name": self.name,
                    "parser_type": "tree-sitter",
                    "match_start": match.captures[0].node.start_byte if match.captures else 0,
                    "match_end": match.captures[0].node.end_byte if match.captures else 0,
                    "source_code": source_code
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
            # Log error but don't crash
            import logging
            logging.warning(f"Error in tree-sitter matching for {self.name}: {e}")
            return []
    
    def _regex_matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Get matches using regex.
        
        Args:
            source_code: Source code to match against
            
        Returns:
            List of matches with metadata
        """
        if not self.is_regex:
            return []
            
        try:
            import re
            results = []
            
            # Find all matches
            for match in re.finditer(self.regex_pattern, source_code, re.MULTILINE | re.DOTALL):
                line_number = source_code[:match.start()].count('\n') + 1
                
                match_data = {
                    "match": match,
                    "text": match.group(0),
                    "groups": match.groups(),
                    "named_groups": match.groupdict(),
                    "start": match.start(),
                    "end": match.end(),
                    "line": line_number,
                    "pattern_name": self.name,
                    "parser_type": "regex",
                    "source_code": source_code
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
            # Log error but don't crash
            import logging
            logging.warning(f"Error in regex matching for {self.name}: {e}")
            return []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pattern to dictionary.
        
        Returns:
            Dictionary representation of pattern
        """
        return {
            "name": self.name,
            "pattern": self.pattern,
            "regex_pattern": self.regex_pattern,
            "category": self.category.value,
            "purpose": self.purpose.value,
            "language_id": self.language_id,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "block_type": self.block_type,
            "contains_blocks": self.contains_blocks,
            "is_nestable": self.is_nestable,
            "extraction_priority": self.extraction_priority,
            "adaptable": self.adaptable,
            "confidence_threshold": self.confidence_threshold,
            "learning_examples": self.learning_examples,
            "test_cases": self.test_cases
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueryPattern':
        """Create pattern from dictionary.
        
        Args:
            data: Dictionary representation of pattern
            
        Returns:
            New QueryPattern instance
        """
        # Convert string enum values to enum instances
        category = PatternCategory(data.get("category", "unknown"))
        purpose = PatternPurpose(data.get("purpose", "unknown"))
        
        # Create pattern instance
        return cls(
            name=data.get("name", ""),
            pattern=data.get("pattern", ""),
            regex_pattern=data.get("regex_pattern"),
            category=category,
            purpose=purpose,
            language_id=data.get("language_id", "*"),
            confidence=data.get("confidence", 0.8),
            metadata=data.get("metadata", {}),
            block_type=data.get("block_type"),
            contains_blocks=data.get("contains_blocks", []),
            is_nestable=data.get("is_nestable", False),
            extraction_priority=data.get("extraction_priority", 0),
            adaptable=data.get("adaptable", True),
            confidence_threshold=data.get("confidence_threshold", 0.7),
            learning_examples=data.get("learning_examples", []),
            test_cases=data.get("test_cases", [])
        )

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
    'ExtractedBlock'
]
