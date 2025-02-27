"""Unified pattern processing and query system."""

from typing import Dict, Any, List, Union, Callable, Optional
from dataclasses import dataclass, field
from parsers.language_mapping import TREE_SITTER_LANGUAGES, CUSTOM_PARSER_LANGUAGES, normalize_language_name
import re
from parsers.types import ParserType
from parsers.models import PatternDefinition, PatternMatch, FileClassification
from utils.logger import log
import os
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
                log(f"Error compiling pattern {name}: {e}", level="error")
    return compiled

class PatternProcessor:
    """Central pattern processing system."""
    
    def __init__(self):
        """
        Initialize the pattern processor with dictionaries for both tree-sitter
        and custom regex patterns. Patterns are loaded on demand.
        """
        # Initialize dictionaries for all supported languages first
        self._tree_sitter_patterns = {lang: {} for lang in TREE_SITTER_LANGUAGES}
        self._regex_patterns = {lang: {} for lang in CUSTOM_PARSER_LANGUAGES}
        
        # Used to track which language patterns have been loaded
        self._loaded_languages = set()
        
    def _ensure_patterns_loaded(self, language: str):
        """
        Ensure patterns for the specified language are loaded.
        Uses lazy loading to improve performance.
        
        Args:
            language: The language to load patterns for
        """
        normalized_lang = normalize_language_name(language)
        
        # Skip if already loaded
        if normalized_lang in self._loaded_languages:
            return
            
        # Load the patterns based on parser type
        try:
            if normalized_lang in TREE_SITTER_LANGUAGES:
                self._load_tree_sitter_patterns(normalized_lang)
            elif normalized_lang in CUSTOM_PARSER_LANGUAGES:
                self._load_custom_patterns(normalized_lang)
                
            # Mark as loaded even if there were no patterns
            self._loaded_languages.add(normalized_lang)
        except Exception as e:
            log(f"Error loading patterns for {language}: {e}", level="error")
    
    def _load_tree_sitter_patterns(self, language: str):
        """
        Load tree-sitter specific patterns for a language.
        
        Args:
            language: The language to load patterns for
        """
        from parsers.query_patterns import get_patterns_for_language
        
        patterns = get_patterns_for_language(language)
        if patterns:
            self._tree_sitter_patterns[language] = patterns
            log(f"Loaded {len(patterns)} tree-sitter patterns for {language}", level="debug")
                    
    def _load_custom_patterns(self, language: str):
        """
        Load custom parser patterns for a language.
        
        Args:
            language: The language to load patterns for
        """
        from parsers.query_patterns import get_patterns_for_language
        
        patterns = get_patterns_for_language(language)
        if patterns:
            self._regex_patterns[language] = patterns
            log(f"Loaded {len(patterns)} regex patterns for {language}", level="debug")

    def get_patterns_for_file(self, classification: FileClassification) -> dict:
        """
        Get patterns based on parser type and language.
        Ensures patterns are loaded before returning them.
        
        Args:
            classification: File classification containing language and parser type
            
        Returns:
            Dictionary of patterns for the specified language
        """
        # Make sure patterns are loaded for this language
        self._ensure_patterns_loaded(classification.language_id)
        
        # Return the appropriate pattern set
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
        try:
            # Get the tree-sitter parser for this language
            from tree_sitter_language_pack import get_parser
            from parsers.models import PatternMatch
            
            parser = get_parser(pattern.language_id)
            if not parser:
                return []
                
            # Parse the source code
            tree = parser.parse(bytes(source_code, "utf8"))
            if not tree:
                return []
                
            # Execute the tree-sitter query
            query = parser.language.query(pattern.tree_sitter)
            
            matches = []
            for match in query.matches(tree.root_node):
                captures = {capture.name: capture.node for capture in match.captures}
                
                # Create a pattern match result
                result = PatternMatch(
                    text=match.pattern_node.text.decode('utf8'),
                    start=match.pattern_node.start_point,
                    end=match.pattern_node.end_point,
                    metadata={"captures": captures}
                )
                
                # Apply custom extraction if available
                if pattern.extract:
                    try:
                        extracted = pattern.extract(result)
                        if extracted:
                            result.metadata.update(extracted)
                    except Exception as e:
                        log(f"Error in pattern extraction: {e}", level="error")
                
                matches.append(result)
                
            return matches
            
        except Exception as e:
            log(f"Error processing tree-sitter pattern: {e}", level="error")
            return []
        
    def extract_repository_patterns(self, file_path: str, source_code: str, language: str) -> List[Dict[str, Any]]:
        """
        Extract potential patterns from a file for repository learning.
        
        Args:
            file_path: Path to the file being processed
            source_code: Source code content
            language: Programming language of the file
            
        Returns:
            List of extracted patterns with metadata
        """
        # Ensure patterns are loaded for this language
        self._ensure_patterns_loaded(language)
        
        patterns = []
        
        # Get language-specific rules
        from ai_tools.rule_config import get_language_rules, get_policy_for_pattern, PatternType
        
        language_rules = get_language_rules(language)
        
        # Extract code structure patterns
        structure_patterns = self._extract_code_structure_patterns(source_code, language_rules)
        for pattern in structure_patterns:
            pattern['pattern_type'] = PatternType.CODE_STRUCTURE
            patterns.append(pattern)
            
        # Extract naming convention patterns
        naming_patterns = self._extract_naming_convention_patterns(source_code, language_rules)
        for pattern in naming_patterns:
            pattern['pattern_type'] = PatternType.CODE_NAMING
            patterns.append(pattern)
            
        # Extract error handling patterns
        error_patterns = self._extract_error_handling_patterns(source_code, language_rules)
        for pattern in error_patterns:
            pattern['pattern_type'] = PatternType.ERROR_HANDLING
            patterns.append(pattern)
            
        return patterns
        
    def _extract_code_structure_patterns(self, source_code: str, language_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract code structure patterns like class/function structures."""
        patterns = []
        
        # For common patterns like class/function definitions
        if 'class' in language_rules.get('naming_conventions', {}):
            class_pattern = language_rules['naming_conventions']['class']
            class_matches = re.finditer(r'class\s+(' + class_pattern + r')', source_code)
            
            for match in class_matches:
                # Find the class body
                class_name = match.group(1)
                class_start = match.start()
                
                # Simple heuristic to find class end - can be improved with actual parsing
                class_content = self._extract_block_content(source_code, class_start)
                if class_content:
                    patterns.append({
                        'name': f'class_{class_name}',
                        'content': class_content,
                        'language': language_rules.get('language', 'unknown'),
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'class',
                            'class_name': class_name
                        }
                    })
        
        # Similar for functions/methods
        if 'function' in language_rules.get('naming_conventions', {}):
            func_pattern = language_rules['naming_conventions']['function']
            func_matches = re.finditer(r'(def|function)\s+(' + func_pattern + r')', source_code)
            
            for match in func_matches:
                func_name = match.group(2)
                func_start = match.start()
                
                func_content = self._extract_block_content(source_code, func_start)
                if func_content:
                    patterns.append({
                        'name': f'function_{func_name}',
                        'content': func_content,
                        'language': language_rules.get('language', 'unknown'),
                        'confidence': 0.75,
                        'metadata': {
                            'type': 'function',
                            'function_name': func_name
                        }
                    })
        
        return patterns
    
    def _extract_naming_convention_patterns(self, source_code: str, language_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract naming convention patterns."""
        patterns = []
        naming_conventions = language_rules.get('naming_conventions', {})
        
        # Extract variable naming patterns
        if 'variable' in naming_conventions:
            var_pattern = naming_conventions['variable']
            var_matches = re.finditer(r'(?<!def\s)(?<!class\s)(?<!import\s)(\b' + var_pattern + r')\s*=', source_code)
            
            var_names = set()
            for match in var_matches:
                var_name = match.group(1)
                if var_name not in var_names:
                    var_names.add(var_name)
                    patterns.append({
                        'name': f'variable_naming',
                        'content': var_name,
                        'language': language_rules.get('language', 'unknown'),
                        'confidence': 0.7,
                        'metadata': {
                            'type': 'naming_convention',
                            'subtype': 'variable'
                        }
                    })
        
        return patterns
    
    def _extract_error_handling_patterns(self, source_code: str, language_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract error handling patterns."""
        patterns = []
        error_keywords = language_rules.get('error_patterns', [])
        
        for keyword in error_keywords:
            if keyword in ['try', 'catch', 'except']:
                # Find try-except/try-catch blocks
                try_matches = re.finditer(r'try\s*:', source_code) if keyword == 'try' else []
                
                for match in try_matches:
                    try_start = match.start()
                    
                    # Extract the full try-except block
                    try_block = self._extract_block_content(source_code, try_start)
                    if try_block:
                        patterns.append({
                            'name': 'error_handling',
                            'content': try_block,
                            'language': language_rules.get('language', 'unknown'),
                            'confidence': 0.85,
                            'metadata': {
                                'type': 'error_handling',
                                'subtype': 'try_except' 
                            }
                        })
        
        return patterns
    
    def _extract_block_content(self, source_code: str, start_pos: int) -> Optional[str]:
        """
        Extract a code block (like function/class body) starting from a position.
        Simple implementation that can be enhanced with actual parsing.
        """
        try:
            # Find the opening brace or colon
            block_start = source_code.find(':', start_pos)
            if block_start == -1:
                block_start = source_code.find('{', start_pos)
                if block_start == -1:
                    return None
                    
            # Simple approach to find block end - this is a heuristic
            # and would be better with actual parsing
            lines = source_code[block_start:].splitlines()
            
            if not lines:
                return None
                
            # Handle Python indentation-based blocks
            if source_code[block_start] == ':':
                block_content = [lines[0]]
                initial_indent = len(lines[1]) - len(lines[1].lstrip())
                
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() and len(line) - len(line.lstrip()) <= initial_indent:
                        break
                    block_content.append(line)
                    
                return '\n'.join(block_content)
            
            # Handle brace-based blocks
            else:
                brace_count = 1
                block_content = [lines[0]]
                
                for i, line in enumerate(lines[1:], 1):
                    block_content.append(line)
                    brace_count += line.count('{') - line.count('}')
                    
                    if brace_count <= 0:
                        break
                        
                return '\n'.join(block_content)
        
        except Exception as e:
            log(f"Error extracting block content: {e}", level="error")
            return None

# Global instance
pattern_processor = PatternProcessor() 