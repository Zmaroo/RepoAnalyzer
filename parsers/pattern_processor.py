"""Unified pattern processing and query system."""
from typing import Dict, Any, List, Union, Callable, Optional
from dataclasses import dataclass, field
from parsers.language_mapping import TREE_SITTER_LANGUAGES, CUSTOM_PARSER_LANGUAGES, normalize_language_name
import re
import time
from parsers.types import ParserType
from parsers.models import PatternDefinition, PatternMatch, FileClassification, PatternType
from utils.logger import log
import os
import importlib
from parsers.language_mapping import is_supported_language
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary
try:
    from analytics.pattern_statistics import pattern_statistics
    PATTERN_STATS_ENABLED = True
except ImportError:
    PATTERN_STATS_ENABLED = False
    log('Pattern statistics module not available, statistics collection disabled'
        , level='warning')
COMMON_PATTERNS = {'comment_single': re.compile('//\\s*(.+)$|#\\s*(.+)$'),
    'comment_multi': re.compile(
    '/\\*.*?\\*/|""".*?"""|\\\'\\\'\\\'.*?\\\'\\\'\\\'', re.DOTALL),
    'metadata': re.compile('^@(\\w+):\\s*(.*)$'), 'url': re.compile(
    'https?://\\S+|www\\.\\S+'), 'email': re.compile(
    '\\b[\\w\\.-]+@[\\w\\.-]+\\.\\w+\\b'), 'path': re.compile(
    '(?:^|[\\s(])(?:/[\\w.-]+)+|\\b[\\w.-]+/[\\w.-/]+')}


@dataclass
class CompiledPattern:
    """Holds compiled versions (tree-sitter and regex) of a pattern."""
    tree_sitter: Optional[str] = None
    regex: Optional[Union[str, re.Pattern]] = None
    extract: Optional[Callable] = None
    definition: Optional[PatternDefinition] = None


def compile_patterns(pattern_defs: Dict[str, Any]) ->Dict[str, Any]:
    """Compile regex patterns from a pattern definitions dictionary."""
    compiled = {}
    for category, patterns in pattern_defs.items():
        for name, pattern_obj in patterns.items():
            with ErrorBoundary(f'compile_pattern_{name}', error_types=(
                Exception,)):
                compiled[name] = re.compile(pattern_obj.pattern, re.DOTALL)
    return compiled


class PatternProcessor:
    """Central pattern processing system."""

    def __init__(self):
        """
        Initialize the pattern processor with dictionaries for both tree-sitter
        and custom regex patterns. Patterns are loaded on demand.
        """
        self._tree_sitter_patterns = {lang: {} for lang in
            TREE_SITTER_LANGUAGES}
        self._regex_patterns = {lang: {} for lang in CUSTOM_PARSER_LANGUAGES}
        self._loaded_languages = set()
        from parsers.block_extractor import block_extractor
        self.block_extractor = block_extractor
        self.tree_sitter_languages = TREE_SITTER_LANGUAGES

    def _ensure_patterns_loaded(self, language: str):
        """
        Ensure patterns for a language are loaded.
        
        Args:
            language: The language to load patterns for
        """
        normalized_lang = normalize_language_name(language)
        if normalized_lang in self._loaded_languages:
            return
        with ErrorBoundary(f'load_patterns_{normalized_lang}', error_types=
            (Exception,)):
            if normalized_lang in TREE_SITTER_LANGUAGES:
                self._load_tree_sitter_patterns(normalized_lang)
            elif normalized_lang in CUSTOM_PARSER_LANGUAGES:
                self._load_custom_patterns(normalized_lang)
            self._loaded_languages.add(normalized_lang)

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
            log(f'Loaded {len(patterns)} tree-sitter patterns for {language}',
                level='debug')

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
            log(f'Loaded {len(patterns)} regex patterns for {language}',
                level='debug')

@handle_errors(error_types=(Exception,))
    def get_patterns_for_file(self, classification: FileClassification) ->dict:
        """
        Get patterns based on parser type and language.
        Ensures patterns are loaded before returning them.
        
        Args:
            classification: File classification containing language and parser type
            
        Returns:
            Dictionary of patterns for the specified language
        """
        self._ensure_patterns_loaded(classification.language_id)
        patterns = (self._tree_sitter_patterns if classification.
            parser_type == ParserType.TREE_SITTER else self._regex_patterns)
        return patterns.get(classification.language_id, {})
@handle_errors(error_types=(Exception,))

    def validate_pattern(self, pattern: CompiledPattern, language: str) ->bool:
        """Validate pattern matches parser type."""
        is_tree_sitter = language in TREE_SITTER_LANGUAGES
        return is_tree_sitter == (pattern.definition.pattern_type ==
@handle_errors(error_types=(Exception,))
            'tree-sitter')

    def process_node(self, source_code: str, pattern: CompiledPattern) ->List[
        PatternMatch]:
        """Process a node using appropriate pattern type."""
        start_time = time.time()
        compilation_time = 0
        if hasattr(pattern, 'compilation_time_ms'):
            compilation_time = pattern.compilation_time_ms
        if pattern.tree_sitter:
            matches = self._process_tree_sitter_pattern(source_code, pattern)
        elif pattern.regex:
            matches = self._process_regex_pattern(source_code, pattern)
        else:
            matches = []
        if PATTERN_STATS_ENABLED and hasattr(pattern, 'definition'
            ) and pattern.definition:
            execution_time_ms = (time.time() - start_time) * 1000
            pattern_id = getattr(pattern.definition, 'id', pattern.
                definition.name if hasattr(pattern.definition, 'name') else
                'unknown')
            pattern_type = getattr(pattern.definition, 'pattern_type',
                PatternType.CODE_STRUCTURE)
            language = getattr(pattern.definition, 'language', 'unknown')
            if isinstance(pattern_type, str):
                try:
                    pattern_type = PatternType(pattern_type)
                except ValueError:
                    pattern_type = PatternType.CODE_STRUCTURE
            try:
                pattern_statistics.track_pattern_execution(pattern_id=
                    pattern_id, pattern_type=pattern_type, language=
                    language, execution_time_ms=execution_time_ms,
                    compilation_time_ms=compilation_time, matches_found=len
                    (matches), memory_bytes=len(source_code) if matches else 0)
            except Exception as e:
                log(f'Error tracking pattern statistics: {str(e)}', level=
                    'error')
        return matches

    def _process_regex_pattern(self, source_code: str, pattern: CompiledPattern
        ) ->List[PatternMatch]:
        """Process using regex pattern."""
        start_time = time.time()
        matches = []
        for match in pattern.regex.finditer(source_code):
            result = PatternMatch(text=match.group(0), start=match.start(),
                end=match.end(), metadata={'groups': match.groups(),
                'named_groups': match.groupdict(), 'execution_time_ms': (
                time.time() - start_time) * 1000})
            if pattern.extract:
                result.metadata.update(pattern.extract(result))
            matches.append(result)
        return matches

    def _process_tree_sitter_pattern(self, source_code: str, pattern:
        CompiledPattern) ->List[PatternMatch]:
        """Process using tree-sitter pattern."""
        from tree_sitter_language_pack import get_parser
        from parsers.models import PatternMatch
        import hashlib
        import asyncio
        from utils.cache import ast_cache
        start_time = time.time()

        def process_pattern():
            parser = get_parser(pattern.language_id)
            if not parser:
                return []
            source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
            cache_key = f'ast:{pattern.language_id}:{source_hash}'
            cached_ast = asyncio.run(ast_cache.get_async(cache_key))
            if cached_ast and 'tree' in cached_ast:
                log(f'Using cached AST for pattern processing', level='debug')
                tree = parser.parse(bytes(source_code, 'utf8'))
                if not tree:
                    return []
            else:
                tree = parser.parse(bytes(source_code, 'utf8'))
                if not tree:
                    return []
                cache_data = {'tree': self._convert_tree_to_dict(tree.
                    root_node)}
                asyncio.run(ast_cache.set_async(cache_key, cache_data))
                log(f'AST cached for pattern processing', level='debug')
            query = parser.language.query(pattern.tree_sitter)
            matches = []
            for match in query.matches(tree.root_node):
                captures = {capture.name: capture.node for capture in match
                    .captures}
                result = PatternMatch(text=match.pattern_node.text.decode(
                    'utf8'), start=match.pattern_node.start_point, end=
                    match.pattern_node.end_point, metadata={'captures':
                    captures, 'execution_time_ms': (time.time() -
                    start_time) * 1000})
                if pattern.extract:
                    with ErrorBoundary(operation_name='pattern extraction'):
                        extracted = pattern.extract(result)
                        if extracted:
                            result.metadata.update(extracted)
                matches.append(result)
            return matches
        with ErrorBoundary(operation_name='tree-sitter pattern processing'):
            return process_pattern()
        return []

    def _convert_tree_to_dict(self, node) ->Dict[str, Any]:
        """Convert tree-sitter node to dict."""
        if not node:
            return {}
        return {'type': node.type, 'start': node.start_point, 'end': node.
            end_point, 'text': node.text.decode('utf8') if len(node.
            children) == 0 else None, 'children': [self.
            _convert_tree_to_dict(child) for child in node.children] if
            node.children else []}

    def extract_repository_patterns(self, file_path: str, source_code: str,
        language: str) ->List[Dict[str, Any]]:
        """
        Extract patterns from source code for repository learning.
        
        Args:
            file_path: Path to the file (used for language detection if not specified)
            source_code: Source code content
            language: Programming language
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        with ErrorBoundary(error_types=(Exception,), operation_name=
            'extract_repository_patterns'):
            from parsers.language_mapping import REPOSITORY_LEARNING_PATTERNS
            language_rules = REPOSITORY_LEARNING_PATTERNS.get(language, {})
            if not language_rules:
                log(f'No repository learning patterns defined for {language}',
                    level='debug')
                return patterns
            structure_patterns = self._extract_code_structure_patterns(
                source_code, language_rules, language)
            naming_patterns = self._extract_naming_convention_patterns(
                source_code, language_rules)
            error_patterns = self._extract_error_handling_patterns(source_code,
                language_rules, language)
            patterns.extend(structure_patterns)
            patterns.extend(naming_patterns)
            patterns.extend(error_patterns)
            if language in self.tree_sitter_languages:
                try:
                    from tree_sitter_language_pack import get_parser
                    import importlib
                    pattern_module_name = f'parsers.query_patterns.{language}'
                    learning_patterns = None
                    try:
                        pattern_module = importlib.import_module(
                            pattern_module_name)
                        if hasattr(pattern_module,
                            f'{language.upper()}_PATTERNS'):
                            pattern_dict = getattr(pattern_module,
                                f'{language.upper()}_PATTERNS')
                            learning_patterns = pattern_dict.get(
                                'REPOSITORY_LEARNING', {})
                    except (ImportError, AttributeError):
                        pass
                    if learning_patterns:
                        parser = get_parser(language)
                        tree = parser.parse(source_code.encode('utf8'))
                        root_node = tree.root_node
                        for pattern_name, pattern_def in learning_patterns.items(
                            ):
                            if ('pattern' in pattern_def and 'extract' in
                                pattern_def):
                                try:
                                    query = parser.query(pattern_def['pattern']
                                        )
                                    for capture in query.captures(root_node):
                                        capture_name, node = capture
                                        block = (self.block_extractor.
                                            extract_block(language, source_code,
                                            node))
                                        if block and block.content:
                                            capture_result = {'node': node,
                                                'captures': {capture_name: node},
                                                'text': block.content}
                                            try:
                                                metadata = pattern_def['extract'](
                                                    capture_result)
                                                if metadata:
                                                    patterns.append({'name': pattern_name,
                                                        'content': block.content,
                                                        'pattern_type': metadata.get('type',
                                                        PatternType.CUSTOM), 'language':
                                                        language, 'confidence': 0.95,
                                                        'metadata': metadata})
                                            except Exception as e:
                                                log(f'Error in extract function for {pattern_name}: {str(e)}'
                                                    , level='error')
                                except Exception as e:
                                    log(f'Error processing tree-sitter query for {pattern_name}: {str(e)}'
                                        , level='error')
                except Exception as e:
                    log(f'Error using tree-sitter for pattern extraction: {str(e)}'
                        , level='error')
        return patterns

    def _extract_code_structure_patterns(self, source_code: str,
        language_rules: Dict[str, Any], language_id: str=None) ->List[Dict[
        str, Any]]:
        """Extract code structure patterns from source using regex or tree-sitter queries."""
        patterns = []
        with ErrorBoundary(error_types=(Exception,), operation_name=
            'extract_code_structure'):
            class_pattern = language_rules.get('class_pattern')
            if class_pattern:
                class_matches = re.finditer(class_pattern, source_code)
                for match in class_matches:
                    class_name = match.group('class_name'
                        ) if 'class_name' in match.groupdict() else ''
                    class_start = match.start()
                    class_content = self._extract_block_content(source_code,
                        class_start, language_id)
                    if class_content:
                        patterns.append({'name': f'class_{class_name}',
                            'content': class_content, 'pattern_type':
                            PatternType.CLASS_DEFINITION, 'language': 
                            language_id or 'unknown', 'confidence': 0.9,
                            'metadata': {'type': 'class', 'name': class_name}})
            function_pattern = language_rules.get('function_pattern')
            if function_pattern:
                func_matches = re.finditer(function_pattern, source_code)
                for match in func_matches:
                    func_name = match.group('func_name'
                        ) if 'func_name' in match.groupdict() else ''
                    func_start = match.start()
                    func_content = self._extract_block_content(source_code,
                        func_start, language_id)
                    if func_content:
                        patterns.append({'name': f'function_{func_name}',
                            'content': func_content, 'pattern_type':
                            PatternType.FUNCTION_DEFINITION, 'language': 
                            language_id or 'unknown', 'confidence': 0.85,
                            'metadata': {'type': 'function', 'name':
                            func_name}})
        return patterns

    def _extract_naming_convention_patterns(self, source_code: str,
        language_rules: Dict[str, Any]) ->List[Dict[str, Any]]:
        """Extract naming convention patterns."""
        patterns = []
        naming_conventions = language_rules.get('naming_conventions', {})
        if 'variable' in naming_conventions:
            var_pattern = naming_conventions['variable']
            var_matches = re.finditer(
                '(?<!def\\s)(?<!class\\s)(?<!import\\s)(\\b' + var_pattern +
                ')\\s*=', source_code)
            var_names = set()
            for match in var_matches:
                var_name = match.group(1)
                if var_name not in var_names:
                    var_names.add(var_name)
                    patterns.append({'name': f'variable_naming', 'content':
                        var_name, 'language': language_rules.get('language',
                        'unknown'), 'confidence': 0.7, 'metadata': {'type':
                        'naming_convention', 'subtype': 'variable'}})
        return patterns

    def _extract_error_handling_patterns(self, source_code: str,
        language_rules: Dict[str, Any], language_id: str=None) ->List[Dict[
        str, Any]]:
        """Extract error handling patterns from source."""
        patterns = []
        with ErrorBoundary(error_types=(Exception,), operation_name=
            'extract_error_handling'):
            try_pattern = language_rules.get('try_pattern')
            if try_pattern:
                try_matches = re.finditer(try_pattern, source_code)
                for match in try_matches:
                    try_start = match.start()
                    try_block = self._extract_block_content(source_code,
                        try_start, language_id)
                    if try_block:
                        patterns.append({'name': 'error_handling',
                            'content': try_block, 'pattern_type':
                            PatternType.ERROR_HANDLING, 'language': 
                            language_id or 'unknown', 'confidence': 0.8,
                            'metadata': {'type': 'try_catch', 'has_finally':
                            'finally' in try_block.lower(),
                            'has_multiple_catches': try_block.lower().count
                            ('catch') > 1}})
        return patterns

    def _extract_block_content(self, source_code: str, start_pos: int,
        language_id: str=None) ->Optional[str]:
        """
        Extract a code block (like function/class body) starting from a position.
        Uses tree-sitter block extraction if available, otherwise falls back to heuristic approach.
        
        Args:
            source_code: The complete source code
            start_pos: Position where the block starts
            language_id: Optional language identifier for language-specific extraction
            
        Returns:
            Extracted block content or None if extraction failed
        """
        with ErrorBoundary(error_types=(Exception,), operation_name=
            'extract_block_content'):
            if language_id and language_id in self.tree_sitter_languages:
                try:
                    from tree_sitter_language_pack import get_parser
                    parser = get_parser(language_id)
                    if parser:
                        tree = parser.parse(source_code.encode('utf8'))
                        lines = source_code[:start_pos].splitlines()
                        if not lines:
                            line = 0
                            col = start_pos
                        else:
                            line = len(lines) - 1
                            col = len(lines[-1])
                        cursor = tree.root_node.walk()
                        cursor.goto_first_child_for_point((line, col))
                        if cursor.node:
                            block = self.block_extractor.extract_block(
                                language_id, source_code, cursor.node)
                            if block and block.content:
                                return block.content
                except Exception as e:
                    log(f'Tree-sitter block extraction failed, falling back to heuristic: {str(e)}'
                        , level='debug')
            block_start = source_code.find(':', start_pos)
            if block_start == -1:
                block_start = source_code.find('{', start_pos)
                if block_start == -1:
                    return None
            lines = source_code[block_start:].splitlines()
            if not lines:
                return None
            if source_code[block_start] == ':':
                block_content = [lines[0]]
                initial_indent = len(lines[1]) - len(lines[1].lstrip()) if len(
                    lines) > 1 else 0
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() and len(line) - len(line.lstrip()
                        ) <= initial_indent:
                        break
                    block_content.append(line)
                return '\n'.join(block_content)
            else:
                brace_count = 1
                block_content = [lines[0]]
                for i, line in enumerate(lines[1:], 1):
                    block_content.append(line)
                    brace_count += line.count('{') - line.count('}')
                    if brace_count <= 0:
                        break
                return '\n'.join(block_content)
        return None


pattern_processor = PatternProcessor()
