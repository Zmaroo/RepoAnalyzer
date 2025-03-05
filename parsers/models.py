"""Parser models and data structures."""

from typing import Dict, Any, List, Optional, Set, Union, Callable, TypedDict, NotRequired
from dataclasses import dataclass, field
import asyncio
from parsers.types import FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics, PatternCategory, PatternDefinition, QueryPattern, PatternType
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

PATTERN_CATEGORIES = {
    FeatureCategory.SYNTAX: {
        FileType.CODE: [
            "interface", "type_alias", "enum", "decorator",
            "function", "class", "method", "constructor",
            "struct", "union", "typedef"
        ],
        FileType.DOC: [
            "section", "block", "element", "directive",
            "macro", "attribute", "heading", "list", "table"
        ]
    },
    FeatureCategory.SEMANTICS: {
        FileType.CODE: [
            "type_assertion", "type_predicate", "type_query",
            "union_type", "intersection_type", "tuple_type",
            "variable", "type", "expression", "parameter",
            "return_type", "generic", "template", "operator"
        ],
        FileType.DOC: [
            "link", "reference", "definition", "term",
            "callout", "citation", "footnote", "glossary"
        ]
    },
    FeatureCategory.DOCUMENTATION: {
        FileType.CODE: [
            "comment", "docstring", "javadoc", "xmldoc",
            "todo", "fixme", "note", "warning"
        ],
        FileType.DOC: [
            "metadata", "description", "admonition",
            "annotation", "field", "example", "tip", "caution"
        ]
    },
    FeatureCategory.STRUCTURE: {
        FileType.CODE: [
            "namespace", "import", "export", "package",
            "using", "include", "require", "module_import"
        ],
        FileType.DOC: [
            "hierarchy", "include", "anchor", "toc",
            "cross_reference", "bibliography", "appendix"
        ]
    },
    PatternCategory.CODE: {
        FileType.CODE: [
            "code_structure", "code_naming", "error_handling",
            "function_pattern", "class_pattern", "variable_pattern",
            "import_pattern", "algorithm_pattern", "api_usage"
        ],
        FileType.DOC: [
            "documentation_structure", "api_documentation", 
            "example_usage", "best_practice", "tutorial_pattern"
        ],
        FileType.CONFIG: [
            "configuration_pattern", "environment_setup", 
            "dependency_management", "build_pattern"
        ]
    }
}

