"""Shared data models for the parser system."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Union, Callable, Literal
from enum import Enum
from datetime import datetime
from pydantic import BaseModel
import re
from parsers.feature_extractor import BaseFeatureExtractor, TreeSitterFeatureExtractor, CustomFeatureExtractor

class FileType(Enum):
    """Types of files that can be processed."""
    CODE = "code"
    DOC = "doc"
    CONFIG = "config"
    DATA = "data"
    BINARY = "binary"
    UNKNOWN = "unknown"

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
class FileMetadata:
    """File metadata and configuration."""
    # Metadata
    path: str = ""
    language: str = ""
    encoding: str = "utf-8"
    size: int = 0
    last_modified: datetime = field(default_factory=datetime.now)
    hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Configuration
    binary_extensions: Set[str] = field(default_factory=lambda: {
        # Document formats
        '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg', '.webp',
        # Archives
        '.zip', '.tar', '.gz', '.rar', '.7z',
        # Binaries
        '.exe', '.dll', '.so', '.dylib',
        '.pyc', '.pyo', '.pyd',
        # Media
        '.mp3', '.mp4', '.wav', '.avi', '.mov',
        # Database
        '.db', '.sqlite', '.sqlite3'
    })
    
    ignored_dirs: Set[str] = field(default_factory=lambda: {
        '__pycache__', '.git', 'node_modules', 'venv', '.venv',
        'dist', 'build', '.idea', '.vscode', 'coverage', 'docs',
        'env', '.env', 'bin', 'obj', 'target', 'out',
        'logs', 'temp', 'tmp', 'cache', '.cache'
    })
    
    ignored_files: Set[str] = field(default_factory=lambda: {
        # Development artifacts
        '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dll', '*.dylib',
        '*.exe', '*.obj', '*.o',
        # Logs and temporary files
        '*.log', '*.tmp', '*.temp', '*.swp', '*.swo', '*.bak',
        '*.cache', '*.DS_Store',
        # Package files
        '*.egg-info', '*.egg', '*.whl',
        # IDE files
        '*.iml', '*.ipr', '*.iws', '*.project', '*.classpath',
        # Build artifacts
        '*.min.js', '*.min.css', '*.map'
    })
    
    ignored_patterns: Set[str] = field(default_factory=lambda: {
        r'.*\.git.*',  # Git-related files
        r'.*\.pytest_cache.*',  # Pytest cache
        r'.*__pycache__.*',  # Python cache
        r'.*\.coverage.*',  # Coverage reports
        r'.*\.tox.*',  # Tox test environments
    })

class ParserResult(BaseModel):
    """Result from any parser."""
    success: bool
    ast: Dict[str, Any]
    features: Dict[FeatureCategory, Dict[str, Any]] = {
        FeatureCategory.SYNTAX: {},
        FeatureCategory.SEMANTICS: {},
        FeatureCategory.DOCUMENTATION: {},
        FeatureCategory.STRUCTURE: {}
    }
    documentation: Dict[str, Any]
    complexity: Dict[str, Any]
    statistics: Dict[str, Any]

    @classmethod
    def error(cls, message: str) -> 'ParserResult':
        return cls(success=False, ast={}, features={}, documentation={}, complexity={}, statistics={})

@dataclass
class PatternDefinition:
    """Definition of a pattern with its metadata."""
    name: str
    category: FeatureCategory
    file_type: FileType
    pattern: str
    pattern_type: Literal["tree-sitter", "regex"] = "tree-sitter"
    description: str = ""
    examples: List[str] = field(default_factory=list)

class Documentation(BaseModel):
    """Documentation features aligned with pattern categories."""
    docstrings: List[Dict[str, Any]] = []     # javadoc, xmldoc
    comments: List[Dict[str, Any]] = []       # comment, todo, fixme
    annotations: List[Dict[str, Any]] = []    # note, warning
    metadata: List[Dict[str, Any]] = []       # metadata, description
    examples: List[Dict[str, Any]] = []       # example, tip, caution

class ComplexityMetrics(BaseModel):
    """Code complexity metrics."""
    cyclomatic: int = 0
    cognitive: int = 0
    halstead: Dict[str, float] = {}
    maintainability_index: float = 0.0
    node_count: int = 0
    depth: int = 0

@dataclass
class CustomParserNode:
    """Base class for all custom parser AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class YamlNode(CustomParserNode):
    """YAML AST node."""
    value: Any = None
    key: Optional[str] = None

@dataclass
class MarkdownNode(CustomParserNode):
    """Markdown AST node."""
    content: Optional[str] = None
    level: Optional[int] = None

@dataclass
class JsonNode(CustomParserNode):
    """JSON AST node."""
    value: Any = None
    key: Optional[str] = None

@dataclass
class IniNode(CustomParserNode):
    """INI AST node."""
    section: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None

@dataclass
class HtmlNode(CustomParserNode):
    """HTML AST node."""
    tag: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    text: Optional[str] = None

@dataclass
class GraphQLNode(CustomParserNode):
    """GraphQL AST node."""
    name: Optional[str] = None
    kind: Optional[str] = None  # type, interface, enum, etc.
    fields: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class EnvNode(CustomParserNode):
    """ENV file AST node."""
    name: Optional[str] = None
    value: Optional[str] = None
    value_type: Optional[str] = None

@dataclass
class EditorconfigNode(CustomParserNode):
    """EditorConfig AST node."""
    section: Optional[str] = None
    properties: List[Dict[str, str]] = field(default_factory=list)

@dataclass
class CobaltNode(CustomParserNode):
    """Cobalt AST node."""
    name: Optional[str] = None
    kind: Optional[str] = None
    docstring: Optional[str] = None

@dataclass
class AsciidocNode(CustomParserNode):
    """AsciiDoc AST node."""
    content: Optional[str] = None
    level: Optional[int] = None
    title: Optional[str] = None

@dataclass
class NimNode(CustomParserNode):
    """Nim AST node."""
    name: Optional[str] = None
    kind: Optional[str] = None
    docstring: Optional[str] = None

@dataclass
class OcamlNode(CustomParserNode):
    """OCaml AST node."""
    pass  # Uses base class fields

@dataclass
class PlaintextNode(CustomParserNode):
    """Plaintext AST node."""
    content: Optional[str] = None
    paragraph: Optional[str] = None
    section: Optional[str] = None

# Pattern categories based on feature models
PATTERN_CATEGORIES: Dict[FeatureCategory, Dict[FileType, List[str]]] = {
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
class LanguageFeatures:
    """Language features and capabilities."""
    canonical_name: str
    file_extensions: Set[str]
    parser_type: ParserType
    
    def get_feature_extractor(self) -> 'BaseFeatureExtractor':
        """Get the appropriate feature extractor for this language."""
      
        if self.parser_type == ParserType.TREE_SITTER:
            return TreeSitterFeatureExtractor(self.canonical_name)
        return CustomFeatureExtractor(self.canonical_name)

