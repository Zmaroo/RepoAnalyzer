"""Unified pattern processing and query system."""

from typing import Dict, Any, List, Union, Callable, Optional
from dataclasses import dataclass, field
from parsers.language_mapping import TREE_SITTER_LANGUAGES, CUSTOM_PARSER_LANGUAGES, normalize_language_name
import re
from parsers.types import ParserType
from parsers.models import PatternDefinition, PatternMatch, FileClassification
from utils.logger import log
import os
import pkgutil
import importlib
from parsers.language_mapping import is_supported_language

# Add these common patterns at the top level
COMMON_PATTERNS = {
    'comment_single': re.compile(r'//\s*(.+)$|#\s*(.+)$'),
    'comment_multi': re.compile(r'/\*.*?\*/|""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL),
    'metadata': re.compile(r'^@(\w+):\s*(.*)$'),
    'url': re.compile(r'https?://\S+|www\.\S+'),
    'email': re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w+\b'),
    'path': re.compile(r'(?:^|[\s(])(?:/[\w.-]+)+|\b[\w.-]+/[\w.-/]+')
}

@dataclass
class CompiledPattern:
    """Holds compiled versions (tree-sitter and regex) of a pattern."""
    tree_sitter: Optional[str] = None
    regex: Optional[Union[str, re.Pattern]] = None
    extract: Optional[Callable] = None
    definition: Optional[PatternDefinition] = None

def compile_patterns(pattern_defs: Dict[str, Any]) -> Dict[str, Any]:
    """Compile regex patterns from a pattern definitions dictionary."""
    compiled = {}
    for category, patterns in pattern_defs.items():
        for name, pattern_obj in patterns.items():
            try:
                compiled[name] = re.compile(pattern_obj.pattern, re.DOTALL)
            except Exception as e:
                print(f"Error compiling pattern {name}: {e}")
    return compiled

class PatternProcessor:
    """Central pattern processing system."""
    
    def __init__(self):
        self._patterns = self._load_all_patterns()
        self._tree_sitter_patterns = {}
        self._regex_patterns = {}
    
    def _load_all_patterns(self) -> dict:
        """Load all patterns from query_patterns directory."""
        patterns = {}
        package_dir = os.path.dirname(__file__)
        pattern_dir = os.path.join(package_dir, "query_patterns")
        
        for module_info in pkgutil.iter_modules([pattern_dir]):
            module_name = module_info.name
            if module_name == '__init__':
                continue
                
            try:
                module = importlib.import_module(f"parsers.query_patterns.{module_name}")
                key = normalize_language_name(module_name.lower())
                
                if is_supported_language(key):
                    # Load patterns based on parser type
                    if key in TREE_SITTER_LANGUAGES:
                        self._load_tree_sitter_patterns(module, key)
                    elif key in CUSTOM_PARSER_LANGUAGES:
                        self._load_custom_patterns(module, key)
                    
            except Exception as e:
                log(f"Failed to load patterns for {module_name}: {e}", level="error")
                
        return patterns
        
    def _load_tree_sitter_patterns(self, module: Any, language: str):
        """Load tree-sitter specific patterns."""
        for attr in dir(module):
            if attr.endswith('_PATTERNS'):
                patterns = getattr(module, attr)
                if isinstance(patterns, dict):
                    self._tree_sitter_patterns[language] = patterns
                    
    def _load_custom_patterns(self, module: Any, language: str):
        """Load custom parser patterns."""
        for attr in dir(module):
            if attr.endswith('_PATTERNS'):
                patterns = getattr(module, attr)
                if isinstance(patterns, dict):
                    self._regex_patterns[language] = patterns

    def get_patterns_for_file(self, classification: FileClassification) -> dict:
        """Get patterns based on parser type and language."""
        patterns = (self._tree_sitter_patterns if classification.parser_type == ParserType.TREE_SITTER 
                   else self._regex_patterns)
        return patterns.get(classification.language_id, {})
        
    def validate_pattern(self, pattern: CompiledPattern, language: str) -> bool:
        """Validate pattern matches parser type."""
        is_tree_sitter = language in TREE_SITTER_LANGUAGES
        return is_tree_sitter == (pattern.definition.pattern_type == "tree-sitter")

    def process_node(self, source_code: str, pattern: CompiledPattern) -> List[PatternMatch]:
        """Process a node using appropriate pattern type."""
        if pattern.tree_sitter:
            return self._process_tree_sitter_pattern(source_code, pattern)
        elif pattern.regex:
            return self._process_regex_pattern(source_code, pattern)
        return []

    def _process_regex_pattern(self, source_code: str, pattern: CompiledPattern) -> List[PatternMatch]:
        """Process using regex pattern."""
        matches = []
        for match in pattern.regex.finditer(source_code):
            result = PatternMatch(
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                metadata={
                    "groups": match.groups(),
                    "named_groups": match.groupdict()
                }
            )
            if pattern.extract:
                result.metadata.update(pattern.extract(result))
            matches.append(result)
        return matches

    def _process_tree_sitter_pattern(self, source_code: str, pattern: CompiledPattern) -> List[PatternMatch]:
        """Process using tree-sitter pattern."""
        # Tree-sitter pattern processing moved from TreeSitterParser
        # This is handled in feature extraction now
        return []

# Global instance
pattern_processor = PatternProcessor() 