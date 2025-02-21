"""Unified pattern processing and query system."""

from typing import Dict, Any, List, Union, Callable, Optional, Pattern
from dataclasses import dataclass, field
import re
from enum import Enum
from utils.logger import log

# Add these common patterns at the top level
COMMON_PATTERNS = {
    'comment_single': re.compile(r'//\s*(.+)$|#\s*(.+)$'),
    'comment_multi': re.compile(r'/\*.*?\*/|""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL),
    'metadata': re.compile(r'^@(\w+):\s*(.*)$'),
    'url': re.compile(r'https?://\S+|www\.\S+'),
    'email': re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w+\b'),
    'path': re.compile(r'(?:^|[\s(])(?:/[\w.-]+)+|\b[\w.-]+/[\w.-/]+')
}

class PatternCategory(Enum):
    """Categories for query patterns."""
    SYNTAX = "syntax"
    STRUCTURE = "structure"
    SEMANTICS = "semantics"
    DOCUMENTATION = "documentation"

@dataclass
class QueryPattern:
    """Pattern definition with metadata."""
    pattern: Union[str, Pattern, Callable]
    extract: Callable
    description: str = ""
    examples: List[str] = field(default_factory=list)
    category: PatternCategory = PatternCategory.SYNTAX

@dataclass
class PatternMatch:
    """Container for pattern match results."""
    text: str
    start: tuple
    end: tuple
    metadata: Dict = field(default_factory=dict)

class PatternProcessor:
    """Central pattern processing system."""
    
    def __init__(self):
        self.patterns: Dict[str, Dict[str, QueryPattern]] = {}
        self._initialize_patterns()
    
    def _initialize_patterns(self):
        """Initialize built-in patterns."""
        # Initialize with common regex patterns
        self.patterns['common'] = {
            name: QueryPattern(
                pattern=regex,
                extract=lambda m: {'text': m.group(0)},
                category=PatternCategory.DOCUMENTATION if 'comment' in name or name == 'metadata'
                        else PatternCategory.SEMANTICS
            )
            for name, regex in COMMON_PATTERNS.items()
        }
    
    def add_pattern(self, name: str, pattern: QueryPattern, category: str = 'custom'):
        """Add a new pattern to the processor."""
        if category not in self.patterns:
            self.patterns[category] = {}
        self.patterns[category][name] = pattern
    
    def process_node(self, node: Any, pattern: QueryPattern) -> List[PatternMatch]:
        """Process a node with a pattern."""
        matches = []
        
        if isinstance(node, str):
            if isinstance(pattern.pattern, (str, Pattern)):
                pattern_regex = (pattern.pattern if isinstance(pattern.pattern, Pattern)
                               else re.compile(pattern.pattern))
                
                for match in pattern_regex.finditer(node):
                    matches.append(
                        PatternMatch(
                            text=match.group(0),
                            start=(0, match.start()),
                            end=(0, match.end()),
                            metadata=pattern.extract(match)
                        )
                    )
            
            elif callable(pattern.pattern):
                if pattern.pattern(node):
                    extracted = pattern.extract(node)
                    if extracted:
                        matches.append(
                            PatternMatch(
                                text=str(node),
                                start=(0, 0),
                                end=(0, 0),
                                metadata=extracted
                            )
                        )
        
        return matches

# Global instance
pattern_processor = PatternProcessor() 