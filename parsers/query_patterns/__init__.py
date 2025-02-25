"""Query pattern initialization."""

from parsers.types import QueryPattern, PatternCategory
from parsers.pattern_processor import pattern_processor

__all__ = ["pattern_processor", "QueryPattern", "PatternCategory"]

# That's it - let users import pattern_processor directly