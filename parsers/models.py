"""Parser models and data structures."""

from typing import Dict, Any, List, Optional, Set, Union, Callable, TypedDict, NotRequired
from dataclasses import dataclass, field
import asyncio
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, ParserType,
    Documentation, ComplexityMetrics, PatternDefinition, QueryPattern, PatternType,
    AICapability, AIConfidenceMetrics, AIContext, AIProcessingResult
)
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.logger import log
from utils.shutdown import register_shutdown_handler

@dataclass
class FileMetadata:
    """File metadata information."""
    path: str
    size: int
    last_modified: float
    encoding: str = "utf-8"

@dataclass
class FileClassification:
    """File classification result."""
    file_type: FileType = FileType.CODE
    language_id: str = "unknown"
    parser_type: ParserType = ParserType.CUSTOM
    file_path: Optional[str] = None
    is_binary: bool = False

@dataclass
class LanguageFeatures:
    """Language support information."""
    canonical_name: str
    file_extensions: Set[str]
    parser_type: ParserType
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize language features."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary(f"{self.canonical_name} features initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    log(f"{self.canonical_name} features initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing {self.canonical_name} features: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up language features resources."""
        try:
            if self._pending_tasks:
                log(f"Cleaning up {len(self._pending_tasks)} pending {self.canonical_name} feature tasks", level="info")
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
            log(f"{self.canonical_name} features cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up {self.canonical_name} features: {e}", level="error")

@dataclass
class PatternMatch:
    """Pattern match result."""
    text: str
    start: Union[int, tuple]
    end: Union[int, tuple]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class QueryResult:
    """Query execution result."""
    pattern_name: str
    node: Any
    captures: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

# AST Node TypedDict definitions
class BaseNodeDict(TypedDict):
    """Base type for all parser nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]
    metadata: Dict[str, Any]
    error: NotRequired[Optional[str]]

class AsciidocNodeDict(BaseNodeDict):
    """Node for AsciiDoc parser."""
    sections: List[Any]
    blocks: List[Any]

class CobaltNodeDict(BaseNodeDict):
    """Node for Cobalt parser."""
    name: NotRequired[Optional[str]]
    parameters: List[Dict[str, Any]]
    return_type: NotRequired[Optional[str]]

class EditorconfigNodeDict(BaseNodeDict):
    """Node for EditorConfig parser."""
    properties: List[Any]
    sections: List[Any]

class EnvNodeDict(BaseNodeDict):
    """Node for .env parser."""
    name: NotRequired[Optional[str]]
    value: NotRequired[Optional[str]]
    value_type: NotRequired[Optional[str]]

class GraphQLNodeDict(BaseNodeDict):
    """Node for GraphQL parser."""
    name: NotRequired[Optional[str]]
    fields: List[Dict[str, Any]]
    directives: List[Dict[str, Any]]

class HtmlNodeDict(BaseNodeDict):
    """Node for HTML parser."""
    tag: NotRequired[Optional[str]]
    attributes: Dict[str, str]
    text: NotRequired[Optional[str]]

class IniNodeDict(BaseNodeDict):
    """Node for INI parser."""
    section: NotRequired[Optional[str]]
    properties: List[Dict[str, Any]]

class JsonNodeDict(BaseNodeDict):
    """Node for JSON parser."""
    value: Any
    path: NotRequired[Optional[str]]

class MarkdownNodeDict(BaseNodeDict):
    """Node for Markdown parser."""
    content: NotRequired[Optional[str]]
    level: NotRequired[Optional[int]]
    indent: NotRequired[Optional[int]]

class NimNodeDict(BaseNodeDict):
    """Node for Nim parser."""
    name: NotRequired[Optional[str]]
    parameters: List[Dict[str, Any]]
    return_type: NotRequired[Optional[str]]

class OcamlNodeDict(BaseNodeDict):
    """Node for OCaml parser."""
    name: NotRequired[Optional[str]]
    parameters: List[Dict[str, Any]]
    return_type: NotRequired[Optional[str]]

class PlaintextNodeDict(BaseNodeDict):
    """Node for plaintext parser."""
    content: NotRequired[Optional[str]]

class RstNodeDict(BaseNodeDict):
    """Node for reStructuredText parser."""
    title: NotRequired[Optional[str]]
    level: NotRequired[Optional[int]]
    content: List[str]

class TomlNodeDict(BaseNodeDict):
    """Node for TOML parser."""
    value: Any
    path: NotRequired[Optional[str]]

class XmlNodeDict(BaseNodeDict):
    """Node for XML parser."""
    tag: NotRequired[Optional[str]]
    attributes: Dict[str, str]
    text: NotRequired[Optional[str]]

class YamlNodeDict(BaseNodeDict):
    """Node for YAML parser."""
    value: Any
    path: NotRequired[Optional[str]]

@dataclass
class ProcessedPattern:
    """Processed pattern result (i.e. results from pattern processing)."""
    pattern_name: str
    matches: List[PatternMatch] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize pattern resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary(f"{self.pattern_name} pattern initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing {self.pattern_name} pattern: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up pattern resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up {self.pattern_name} pattern: {e}", level="error")

# Pattern categories organized by purpose and file type
PATTERN_CATEGORIES = {
    PatternCategory.SYNTAX: {
        FileType.CODE: {
            PatternPurpose.UNDERSTANDING: [
                "function", "class", "method", "constructor",
                "interface", "type_alias", "enum", "decorator",
                "struct", "union", "typedef"
            ],
            PatternPurpose.MODIFICATION: [
                "function_body", "class_body", "method_body",
                "block_statement", "expression_statement"
            ],
            PatternPurpose.VALIDATION: [
                "syntax_error", "type_error", "naming_convention",
                "style_violation"
            ],
            PatternPurpose.EXPLANATION: [
                "code_structure", "syntax_explanation",
                "language_feature", "code_organization"
            ]
        },
        FileType.DOC: {
            PatternPurpose.UNDERSTANDING: [
                "section", "block", "element", "directive",
                "macro", "attribute", "heading", "list", "table"
            ]
        }
    },
    
    PatternCategory.SEMANTICS: {
        FileType.CODE: {
            PatternPurpose.UNDERSTANDING: [
                "type", "variable", "parameter", "return_type",
                "expression", "operator", "generic", "template"
            ],
            PatternPurpose.VALIDATION: [
                "type_assertion", "type_predicate", "type_query",
                "union_type", "intersection_type", "tuple_type"
            ],
            PatternPurpose.EXPLANATION: [
                "type_system", "variable_scope", "data_flow",
                "control_flow", "type_inference"
            ]
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        FileType.CODE: {
            PatternPurpose.UNDERSTANDING: [
                "docstring", "comment", "todo", "fixme",
                "note", "warning"
            ],
            PatternPurpose.VALIDATION: [
                "missing_docstring", "incomplete_docs",
                "outdated_docs"
            ],
            PatternPurpose.GENERATION: [
                "api_docs", "function_docs", "class_docs",
                "module_docs", "usage_examples"
            ]
        },
        FileType.DOC: {
            PatternPurpose.UNDERSTANDING: [
                "metadata", "description", "example",
                "api_doc", "tutorial", "guide"
            ]
        }
    },
    
    PatternCategory.STRUCTURE: {
        FileType.CODE: {
            PatternPurpose.UNDERSTANDING: [
                "import", "export", "module", "namespace",
                "package", "dependency"
            ],
            PatternPurpose.VALIDATION: [
                "circular_dependency", "unused_import",
                "missing_dependency"
            ],
            PatternPurpose.EXPLANATION: [
                "project_structure", "module_organization",
                "dependency_graph", "import_system"
            ]
        },
        FileType.CONFIG: {
            PatternPurpose.UNDERSTANDING: [
                "config_section", "env_var", "build_target",
                "dependency_def"
            ]
        }
    },
    
    PatternCategory.CODE_PATTERNS: {
        FileType.CODE: {
            PatternPurpose.UNDERSTANDING: [
                "error_handling", "async_pattern", "callback_pattern",
                "design_pattern", "algorithm_pattern"
            ],
            PatternPurpose.MODIFICATION: [
                "refactoring_pattern", "optimization_pattern",
                "cleanup_pattern"
            ],
            PatternPurpose.GENERATION: [
                "boilerplate", "test_pattern", "crud_pattern",
                "api_pattern"
            ],
            PatternPurpose.SUGGESTION: [
                "design_improvement", "performance_optimization",
                "code_quality", "best_practice"
            ]
        }
    },
    
    PatternCategory.LEARNING: {
        FileType.CODE: {
            PatternPurpose.LEARNING: [
                "common_solution", "best_practice", "anti_pattern",
                "performance_pattern", "security_pattern"
            ],
            PatternPurpose.EXPLANATION: [
                "concept_explanation", "pattern_usage",
                "code_example", "common_pitfall"
            ]
        },
        FileType.DOC: {
            PatternPurpose.LEARNING: [
                "documentation_style", "example_pattern",
                "tutorial_pattern", "explanation_pattern"
            ]
        }
    },
    
    PatternCategory.CONTEXT: {
        FileType.CODE: {
            PatternPurpose.UNDERSTANDING: [
                "project_context", "file_context", "function_context",
                "variable_context", "scope_context"
            ],
            PatternPurpose.EXPLANATION: [
                "context_explanation", "scope_explanation",
                "dependency_context", "usage_context"
            ]
        }
    },
    
    PatternCategory.USER_PATTERNS: {
        FileType.CODE: {
            PatternPurpose.UNDERSTANDING: [
                "coding_style", "naming_pattern", "formatting_pattern",
                "documentation_style", "error_handling_style"
            ],
            PatternPurpose.LEARNING: [
                "user_preference", "common_usage", "frequent_pattern",
                "style_consistency"
            ]
        }
    }
}

@dataclass
class AIPatternResult:
    """Result of AI pattern processing."""
    pattern_name: str
    matches: List[PatternMatch] = field(default_factory=list)
    confidence: float = 1.0
    capabilities: Set[AICapability] = field(default_factory=set)
    context: Optional[AIContext] = None
    insights: Dict[str, Any] = field(default_factory=dict)
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Task] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize AI pattern result resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("ai pattern result initialization"):
                    if self.context:
                        await self.context.initialize()
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing AI pattern result: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up AI pattern result resources."""
        try:
            if self.context:
                await self.context.cleanup()
            
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up AI pattern result: {e}", level="error")

@dataclass
class DeepLearningResult:
    """Result of deep learning analysis."""
    common_patterns: List[Dict[str, Any]]
    pattern_relationships: List[Dict[str, Any]]
    cross_repo_insights: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    confidence: float = 1.0

@dataclass
class PatternRelationship:
    """Relationship between patterns."""
    source_pattern: str
    target_pattern: str
    relationship_type: str
    strength: float
    metadata: Dict[str, Any] = field(default_factory=dict)

