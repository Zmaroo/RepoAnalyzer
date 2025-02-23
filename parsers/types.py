"""Common types and enums for parsers."""

from enum import Enum
from typing import Dict, Any, List, Optional

class FileType(Enum):
    """File classification types."""
    CODE = "code"
    DOC = "doc"
    CONFIG = "config"
    UNKNOWN = "unknown"

class FeatureCategory(Enum):
    """Feature extraction categories."""
    SYNTAX = "syntax"
    SEMANTICS = "semantics"
    DOCUMENTATION = "documentation"
    STRUCTURE = "structure"

class ParserType(Enum):
    """Parser implementation types."""
    TREE_SITTER = "tree_sitter"
    CUSTOM = "custom"
    HYBRID = "hybrid" 