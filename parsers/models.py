"""Data models for the parser system.

This module defines the core data models used throughout the parser system,
including file classification, query results, and pattern matching.
"""

from typing import Dict, Any, List, Optional, Union, Set, TypedDict, Tuple
from dataclasses import dataclass, field
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
)

class BaseNodeDict(TypedDict):
    """Base type for AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List['BaseNodeDict']
    metadata: Dict[str, Any]

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

class CobaltNodeDict(BaseNodeDict):
    """AST node type for Cobalt files."""
    pass

class EditorconfigNodeDict(BaseNodeDict):
    """AST node type for EditorConfig files."""
    pass

class EnvNodeDict(BaseNodeDict):
    """AST node type for ENV files."""
    pass

class IniNodeDict(BaseNodeDict):
    """AST node type for INI files."""
    pass

class PlaintextNodeDict(BaseNodeDict):
    """AST node type for plaintext files."""
    pass

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
    'PATTERN_CATEGORIES',
    'BaseNodeDict',
    'AsciidocNodeDict',
    'CobaltNodeDict',
    'EditorconfigNodeDict',
    'EnvNodeDict',
    'IniNodeDict',
    'PlaintextNodeDict'
]

