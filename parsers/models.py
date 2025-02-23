"""Parser models and data structures."""

from typing import Dict, Any, List, Optional, Set, Union, Callable
from dataclasses import dataclass, field
from parsers.types import FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics
from enum import Enum
from parsers.base_parser import BaseParser

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
    file_type: FileType
    language_id: str
    parser_type: ParserType

@dataclass
class LanguageFeatures:
    """Language support information."""
    canonical_name: str
    file_extensions: Set[str]
    parser_type: ParserType

@dataclass
class PatternMatch:
    """Pattern match result."""
    text: str
    start: Union[int, tuple]
    end: Union[int, tuple]
    metadata: Dict[str, Any] = field(default_factory=dict)

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
    name: str
    definition: PatternDefinition
    language_id: Optional[str] = None

@dataclass
class QueryResult:
    """Query execution result."""
    pattern_name: str
    node: Any
    captures: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FeatureExtractor:
    """Base class for feature extractors."""
    language_id: str
    parser_type: ParserType
    patterns: Dict[str, Any] = field(default_factory=dict)
    initialized: bool = False

    def initialize(self) -> bool:
        """Initialize extractor resources."""
        self.initialized = True
        return True

    def cleanup(self):
        """Clean up extractor resources."""
        self.initialized = False

# Pattern category mappings
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
    }
}

@dataclass
class BaseNode:
    """Base class for all parser nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

@dataclass
class AsciidocNode(BaseNode):
    """Node for AsciiDoc parser."""
    sections: List[Any] = field(default_factory=list)
    blocks: List[Any] = field(default_factory=list)

@dataclass
class CobaltNode(BaseNode):
    """Node for Cobalt parser."""
    name: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None

@dataclass
class EditorconfigNode(BaseNode):
    """Node for EditorConfig parser."""
    properties: List[Any] = field(default_factory=list)
    sections: List[Any] = field(default_factory=list)

@dataclass
class EnvNode(BaseNode):
    """Node for .env parser."""
    name: Optional[str] = None
    value: Optional[str] = None
    value_type: Optional[str] = None

@dataclass
class GraphQLNode(BaseNode):
    """Node for GraphQL parser."""
    name: Optional[str] = None
    fields: List[Dict[str, Any]] = field(default_factory=list)
    directives: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class HtmlNode(BaseNode):
    """Node for HTML parser."""
    tag: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    text: Optional[str] = None

@dataclass
class IniNode(BaseNode):
    """Node for INI parser."""
    section: Optional[str] = None
    properties: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class JsonNode(BaseNode):
    """Node for JSON parser."""
    value: Any = None
    path: Optional[str] = None

@dataclass
class MarkdownNode(BaseNode):
    """Node for Markdown parser."""
    content: Optional[str] = None
    level: Optional[int] = None
    indent: Optional[int] = None

@dataclass
class NimNode(BaseNode):
    """Node for Nim parser."""
    name: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None

@dataclass
class OcamlNode(BaseNode):
    """Node for OCaml parser."""
    name: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None

@dataclass
class PlaintextNode(BaseNode):
    """Node for plaintext parser."""
    content: Optional[str] = None

@dataclass
class RstNode(BaseNode):
    """Node for reStructuredText parser."""
    title: Optional[str] = None
    level: Optional[int] = None
    content: List[str] = field(default_factory=list)

@dataclass
class TomlNode(BaseNode):
    """Node for TOML parser."""
    value: Any = None
    path: Optional[str] = None

@dataclass
class XmlNode(BaseNode):
    """Node for XML parser."""
    tag: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    text: Optional[str] = None

@dataclass
class YamlNode(BaseNode):
    """Node for YAML parser."""
    value: Any = None
    path: Optional[str] = None

@dataclass
class LanguageRegistry:
    """Registry for language parsers."""
    _parsers: Dict[str, BaseParser] = field(default_factory=dict)
    _initialized: bool = False

    def get_parser(self, language_id: str) -> Optional[BaseParser]:
        """Get parser for language."""
        return self._parsers.get(language_id)

    def register_parser(self, parser: BaseParser):
        """Register a parser."""
        self._parsers[parser.language_id] = parser

    def cleanup(self):
        """Clean up all parser instances."""
        for parser in self._parsers.values():
            parser.cleanup()
        self._parsers.clear()

# Global instance
language_registry = LanguageRegistry()

@dataclass
class ProcessedPattern:
    """Processed pattern result."""
    pattern_name: str
    matches: List[PatternMatch] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

