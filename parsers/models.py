"""Data models for the parser system.

This module defines the core data models used throughout the parser system,
including file classification, query results, and pattern matching.
"""

from typing import Dict, Any, List, Optional, Union, Set, TypedDict, Tuple, ForwardRef
from dataclasses import dataclass, field
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
)
import time
import re
import logging

log = logging.getLogger(__name__)

@dataclass
class PatternRelationship:
    """Represents a relationship between patterns."""
    source_id: str
    target_id: str
    type: PatternRelationType
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Check if the relationship is valid."""
        return bool(self.source_id and self.target_id and self.type)

    def __hash__(self) -> int:
        """Hash based on source, target, and type."""
        return hash((self.source_id, self.target_id, self.type))

class BaseNodeDict(TypedDict):
    """Base type for AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List['BaseNodeDict']
    metadata: Dict[str, Any]
    category: PatternCategory
    pattern_type: PatternType
    relationships: List[PatternRelationship]

class AsciidocNodeDict(BaseNodeDict):
    """AST node type for AsciiDoc files."""
    sections: List[Dict[str, Any]] = field(default_factory=list)
    blocks: List[Dict[str, Any]] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: str = ""
    level: Optional[int] = None
    title: Optional[str] = None
    is_section: bool = False
    is_block: bool = False
    is_list: bool = False
    list_type: Optional[str] = None
    list_level: int = 0
    parent_section: Optional[str] = None
    feature_category: FeatureCategory = field(default=FeatureCategory.DOCUMENTATION)

class CobaltNodeDict(BaseNodeDict):
    """AST node type for Cobalt files.
    
    Represents nodes in the Cobalt programming language AST, including
    functions, classes, namespaces, and type definitions.
    """
    name: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None
    parent_class: Optional[str] = None
    namespace: Optional[str] = None
    type_parameters: List[str] = field(default_factory=list)
    is_function: bool = False
    is_class: bool = False
    is_namespace: bool = False
    is_type_def: bool = False
    is_enum: bool = False
    visibility: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    doc_comments: List[str] = field(default_factory=list)
    feature_category: FeatureCategory = field(default=FeatureCategory.SYNTAX)
    pattern_relationships: List[PatternRelationship] = field(default_factory=list)

class EditorconfigNodeDict(BaseNodeDict):
    """AST node type for EditorConfig files.
    
    Represents nodes in EditorConfig files, including sections,
    properties, and glob patterns.
    """
    glob_pattern: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    is_root: bool = False
    is_section: bool = False
    is_property: bool = False
    comments: List[str] = field(default_factory=list)
    indent_style: Optional[str] = None
    indent_size: Optional[int] = None
    charset: Optional[str] = None
    end_of_line: Optional[str] = None
    feature_category: FeatureCategory = field(default=FeatureCategory.STRUCTURE)
    pattern_relationships: List[PatternRelationship] = field(default_factory=list)

class EnvNodeDict(BaseNodeDict):
    """AST node type for ENV files.
    
    Represents nodes in environment configuration files,
    including variable definitions and exports.
    """
    key: Optional[str] = None
    value: Optional[str] = None
    is_export: bool = False
    is_comment: bool = False
    is_multiline: bool = False
    is_reference: bool = False
    referenced_vars: List[str] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)
    line_continuation: bool = False
    quotes: Optional[str] = None
    feature_category: FeatureCategory = field(default=FeatureCategory.STRUCTURE)
    pattern_relationships: List[PatternRelationship] = field(default_factory=list)

class IniNodeDict(BaseNodeDict):
    """AST node type for INI files.
    
    Represents nodes in INI configuration files, including
    sections, properties, and includes.
    """
    section_name: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)
    includes: List[str] = field(default_factory=list)
    is_section: bool = False
    is_property: bool = False
    is_include: bool = False
    is_comment: bool = False
    comments: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    feature_category: FeatureCategory = field(default=FeatureCategory.STRUCTURE)
    pattern_relationships: List[PatternRelationship] = field(default_factory=list)

class PlaintextNodeDict(BaseNodeDict):
    """AST node type for plaintext files.
    
    Represents nodes in plaintext files, including sections,
    paragraphs, lists, and code blocks.
    """
    content: str = ""
    heading_level: Optional[int] = None
    list_type: Optional[str] = None
    list_level: int = 0
    is_heading: bool = False
    is_paragraph: bool = False
    is_list_item: bool = False
    is_code_block: bool = False
    code_language: Optional[str] = None
    metadata_tags: Dict[str, str] = field(default_factory=dict)
    links: List[Dict[str, str]] = field(default_factory=list)
    references: List[Dict[str, str]] = field(default_factory=list)
    feature_category: FeatureCategory = field(default=FeatureCategory.DOCUMENTATION)
    pattern_relationships: List[PatternRelationship] = field(default_factory=list)

@dataclass
class FileClassification:
    """File classification result."""
    file_path: str
    file_type: FileType
    language_id: str
    parser_type: ParserType
    confidence: float = 1.0

@dataclass
class QueryResult:
    """Result of a pattern query."""
    pattern_name: str
    matches: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PatternMatch:
    """Represents a pattern match in source code."""
    pattern_name: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    matched_text: str
    category: PatternCategory
    purpose: PatternPurpose
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def location(self) -> Tuple[int, int, int, int]:
        """Get the location tuple (start_line, start_col, end_line, end_col)."""
        return (self.start_line, self.start_col, self.end_line, self.end_col)
    
    @property
    def is_valid(self) -> bool:
        """Check if the match location is valid."""
        return (
            self.start_line >= 0 and
            self.end_line >= self.start_line and
            self.start_col >= 0 and
            self.end_col >= self.start_col
        )

@dataclass
class Pattern:
    """Represents a code or documentation pattern."""
    name: str
    content: str
    pattern_type: PatternType
    category: PatternCategory
    purpose: PatternPurpose
    language_id: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    _compiled_pattern: Optional[Any] = field(default=None, init=False)

    def __post_init__(self):
        """Post-initialization setup."""
        self.metadata.setdefault('created_at', time.time())
        self.metadata.setdefault('last_used', time.time())
        self.metadata.setdefault('use_count', 0)
        self.metadata.setdefault('success_rate', 1.0)

    @property
    def compiled_pattern(self) -> Any:
        """Get or compile the pattern."""
        if not self._compiled_pattern:
            try:
                if self.pattern_type == PatternType.TREE_SITTER:
                    language = get_language(self.language_id)
                    self._compiled_pattern = language.query(self.content) if language else None
                else:
                    self._compiled_pattern = re.compile(self.content)
            except Exception as e:
                log.error(f"Failed to compile pattern {self.name}: {e}")
                self._compiled_pattern = None
        return self._compiled_pattern

    async def match(self, content: str, context: AIContext) -> List[PatternMatch]:
        """Match this pattern against content with improved error handling and metrics."""
        matches = []
        start_time = time.time()
        
        try:
            if not self.compiled_pattern:
                raise ValueError(f"Pattern {self.name} failed to compile")

            self.metadata['use_count'] += 1
            self.metadata['last_used'] = start_time

            if self.pattern_type == PatternType.TREE_SITTER:
                matches = await self._tree_sitter_match(content)
            else:
                matches = await self._regex_match(content)

            # Update success metrics
            match_count = len(matches)
            self.metadata['success_rate'] = (
                self.metadata['success_rate'] * 0.9 + 
                (1.0 if match_count > 0 else 0.0) * 0.1
            )

        except Exception as e:
            log.error(f"Error matching pattern {self.name}: {e}")
            self.metadata['success_rate'] *= 0.9  # Decrease success rate on error

        finally:
            self.metadata['last_duration'] = time.time() - start_time
            
        return matches

    async def _tree_sitter_match(self, content: str) -> List[PatternMatch]:
        """Match using tree-sitter."""
        matches = []
        parser = get_parser(self.language_id)
        if parser and self.compiled_pattern:
            tree = parser.parse(bytes(content, "utf8"))
            for match in self.compiled_pattern.matches(tree.root_node):
                matches.append(self._create_match(match))
        return matches

    async def _regex_match(self, content: str) -> List[PatternMatch]:
        """Match using regex."""
        matches = []
        if self.compiled_pattern:
            for match in self.compiled_pattern.finditer(content):
                matches.append(self._create_match(match))
        return matches

    def _create_match(self, match: Any) -> PatternMatch:
        """Create a PatternMatch from a raw match."""
        return PatternMatch(
            pattern_name=self.name,
            start_line=getattr(match, 'start_point', (0, 0))[0],
            end_line=getattr(match, 'end_point', (0, 0))[0],
            start_col=getattr(match, 'start_point', (0, 0))[1],
            end_col=getattr(match, 'end_point', (0, 0))[1],
            matched_text=str(match.group(0) if hasattr(match, 'group') else match),
            category=self.category,
            purpose=self.purpose,
            confidence=self.confidence * self.metadata['success_rate']
        )

@dataclass
class ProcessedPattern:
    """Represents a processed pattern result."""
    pattern_name: str
    category: Optional[PatternCategory] = None
    purpose: Optional[PatternPurpose] = None
    matches: List[PatternMatch] = field(default_factory=list)
    content: Optional[str] = None
    confidence: float = 0.0
    relationships: List[PatternRelationship] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Check if the pattern is valid."""
        return bool(self.pattern_name and not self.error)

    @property
    def has_matches(self) -> bool:
        """Check if the pattern has any matches."""
        return bool(self.matches)

# Pattern categories for different languages
PATTERN_CATEGORIES = {
    # Python patterns
    'python': {
        PatternCategory.SYNTAX: {
            'function': ['def', 'async def'],
            'class': ['class'],
            'import': ['import', 'from'],
            'control': ['if', 'for', 'while', 'try', 'with'],
            'decorator': ['@']
        },
        PatternCategory.SEMANTICS: {
            'type_hint': [': ', '-> '],
            'variable': ['=', '+=', '-=', '*=', '/='],
            'constant': ['[A-Z][A-Z0-9_]*'],
            'builtin': ['print', 'len', 'range', 'str', 'int', 'float']
        },
        PatternCategory.DOCUMENTATION: {
            'docstring': ['"""', "'''"],
            'comment': ['#'],
            'todo': ['# TODO', '# FIXME'],
            'note': ['# NOTE', '# WARNING']
        }
    },
    # JavaScript/TypeScript patterns
    'javascript': {
        PatternCategory.SYNTAX: {
            'function': ['function', '=>', 'async'],
            'class': ['class'],
            'import': ['import', 'require'],
            'control': ['if', 'for', 'while', 'try'],
            'decorator': ['@']
        },
        PatternCategory.SEMANTICS: {
            'type': [': ', 'interface', 'type'],
            'variable': ['let', 'const', 'var'],
            'constant': ['[A-Z][A-Z0-9_]*'],
            'builtin': ['console', 'Math', 'Array', 'Object']
        },
        PatternCategory.DOCUMENTATION: {
            'docstring': ['/**', '*/'],
            'comment': ['//', '/*'],
            'todo': ['// TODO', '// FIXME'],
            'note': ['// NOTE', '// WARNING']
        }
    },
    # Java patterns
    'java': {
        PatternCategory.SYNTAX: {
            'function': ['public', 'private', 'protected', 'void'],
            'class': ['class', 'interface', 'enum'],
            'import': ['import'],
            'control': ['if', 'for', 'while', 'try'],
            'decorator': ['@']
        },
        PatternCategory.SEMANTICS: {
            'type': ['<', '>', 'extends', 'implements'],
            'variable': ['=', '+=', '-=', '*=', '/='],
            'constant': ['[A-Z][A-Z0-9_]*'],
            'builtin': ['System', 'String', 'Integer', 'Boolean']
        },
        PatternCategory.DOCUMENTATION: {
            'docstring': ['/**', '*/'],
            'comment': ['//', '/*'],
            'todo': ['// TODO', '// FIXME'],
            'note': ['// NOTE', '// WARNING']
        }
    },
    # C++ patterns
    'cpp': {
        PatternCategory.SYNTAX: {
            'function': ['void', 'int', 'double', 'float'],
            'class': ['class', 'struct', 'enum'],
            'import': ['#include'],
            'control': ['if', 'for', 'while', 'try'],
            'template': ['template']
        },
        PatternCategory.SEMANTICS: {
            'type': ['<', '>', '::', 'typename'],
            'variable': ['=', '+=', '-=', '*=', '/='],
            'constant': ['[A-Z][A-Z0-9_]*'],
            'builtin': ['std', 'cout', 'cin', 'vector']
        },
        PatternCategory.DOCUMENTATION: {
            'docstring': ['/**', '*/'],
            'comment': ['//', '/*'],
            'todo': ['// TODO', '// FIXME'],
            'note': ['// NOTE', '// WARNING']
        }
    },
    # Go patterns
    'go': {
        PatternCategory.SYNTAX: {
            'function': ['func'],
            'struct': ['type', 'struct'],
            'import': ['import'],
            'control': ['if', 'for', 'switch', 'select'],
            'interface': ['interface']
        },
        PatternCategory.SEMANTICS: {
            'type': ['chan', 'map', 'interface{}'],
            'variable': [':=', '=', '+=', '-=', '*=', '/='],
            'constant': ['[A-Z][A-Z0-9_]*'],
            'builtin': ['make', 'len', 'cap', 'append']
        },
        PatternCategory.DOCUMENTATION: {
            'docstring': ['//'],
            'comment': ['//'],
            'todo': ['// TODO', '// FIXME'],
            'note': ['// NOTE', '// WARNING']
        }
    },
    # Rust patterns
    'rust': {
        PatternCategory.SYNTAX: {
            'function': ['fn'],
            'struct': ['struct', 'enum'],
            'import': ['use'],
            'control': ['if', 'for', 'while', 'match'],
            'trait': ['trait', 'impl']
        },
        PatternCategory.SEMANTICS: {
            'type': ['<', '>', '::', '&'],
            'variable': ['let', 'mut'],
            'constant': ['[A-Z][A-Z0-9_]*'],
            'builtin': ['Option', 'Result', 'Vec', 'String']
        },
        PatternCategory.DOCUMENTATION: {
            'docstring': ['///'],
            'comment': ['//', '/*'],
            'todo': ['// TODO', '// FIXME'],
            'note': ['// NOTE', '// WARNING']
        }
    }
}

# Export public interfaces
__all__ = [
    'FileClassification',
    'QueryResult',
    'PatternMatch',
    'ProcessedPattern',
    'PatternRelationship',
    'Pattern',
    'PATTERN_CATEGORIES',
    'BaseNodeDict',
    'AsciidocNodeDict',
    'CobaltNodeDict',
    'EditorconfigNodeDict',
    'EnvNodeDict',
    'IniNodeDict',
    'PlaintextNodeDict'
]

