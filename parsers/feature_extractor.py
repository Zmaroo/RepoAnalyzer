"""Feature extraction implementations."""
from typing import Dict, Any, List, Optional, Union, Generator, Tuple, Callable, TypeVar, cast, Awaitable
from tree_sitter import Node, Query, QueryError, Parser, Language, TreeCursor
from .types import FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics, ExtractedFeatures, PatternCategory
from parsers.models import QueryResult, FileClassification
from parsers.language_support import language_registry
from utils.logger import log
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary
from parsers.pattern_processor import PatternProcessor, PatternMatch, pattern_processor
from parsers.language_mapping import TREE_SITTER_LANGUAGES
from abc import ABC, abstractmethod
ExtractorFn = Union[Callable[[Any], Dict[str, Any]], Callable[[Any],
    Awaitable[Dict[str, Any]]]]


class BaseFeatureExtractor(ABC):
    """[3.2.0] Abstract base class for feature extraction."""

    def __init__(self, language_id: str, file_type: FileType):
        self.language_id = language_id
        self.file_type = file_type
        self._patterns = pattern_processor.get_patterns_for_file(
            FileClassification(file_type=file_type, language_id=language_id,
            parser_type=language_registry.get_parser_type(language_id)))

    @abstractmethod
    def extract_features(self, ast: Dict[str, Any], source_code: str
        ) ->ExtractedFeatures:
        """Extract features from existing AST."""
        pass


class TreeSitterFeatureExtractor(BaseFeatureExtractor):
    """[3.2.1] Tree-sitter specific feature extraction."""
    QUERY_TIMEOUT_MICROS = 5000000
    QUERY_MATCH_LIMIT = 10000

    def __init__(self, language_id: str, file_type: FileType):
        super().__init__(language_id, file_type)
        self._language_registry = language_registry
        self._parser = None
        self._queries = {}
        self._initialize_parser()

    def _initialize_parser(self):
        """Initialize tree-sitter parser."""
        self._parser = Parser()
        self._language = self._language_registry.get_language(self.language_id)
        self._parser.set_language(self._language)
        self._load_patterns()

    def _load_patterns(self):
        """Load patterns from central pattern processor."""
        for category in PatternCategory:
            category_name = category.value
            if category_name in self._patterns:
                for pattern in self._patterns[category_name].values():
                    if pattern_processor.validate_pattern(pattern, self.
                        language_id):
                        self._compile_pattern(pattern, category_name, '')

    def _compile_pattern(self, pattern_def: Union[str, Dict[str, Any]],
        category: str, name: str) ->None:
        """Compile a Tree-sitter query pattern and store in queries dict."""
        with ErrorBoundary(f'compile_pattern_{category}_{name}',
            error_types=(Exception,)):
            if isinstance(pattern_def, str):
                query_str = pattern_def
                extractor_func: Optional[ExtractorFn] = None
            else:
                query_str = pattern_def['pattern']
                extractor_func = pattern_def.get('extract')
                if extractor_func is not None and not callable(extractor_func):
                    log(f'Warning: Non-callable extractor for pattern {name}. Got {type(extractor_func)}'
                        , level='warning')
                    extractor_func = None
            query = self._language.query(query_str)
            query.set_timeout_micros(self.QUERY_TIMEOUT_MICROS)
            query.set_match_limit(self.QUERY_MATCH_LIMIT)
            self._queries.setdefault(category, {})[name] = {'query': query,
                'extract': extractor_func}

    def _process_query_result(self, result: QueryResult) ->Dict[str, Any]:
        """Process a single query result."""
        with ErrorBoundary(f'process_query_result_{result.pattern_name}',
            error_types=(Exception,)):
            node_features = self._extract_node_features(result.node)
            node_features['captures'] = {name: self._extract_node_features(
                node) for name, node in result.captures.items()}
            node_features.update(result.metadata)
            return node_features
        return {}

    def _extract_node_features(self, node: Node) ->Dict[str, Any]:
        """Extract features from a node."""
        return {'type': node.type, 'text': node.text.decode('utf8'),
            'start_byte': node.start_byte, 'end_byte': node.end_byte,
            'start_point': node.start_point, 'end_point': node.end_point,
            'is_named': node.is_named, 'has_error': node.has_error,
            'grammar_name': node.grammar_name, 'child_count': node.
            child_count, 'named_child_count': node.named_child_count}

    def extract_features(self, ast: Dict[str, Any], source_code: str
        ) ->ExtractedFeatures:
        """[3.2.1.2] Extract features from Tree-sitter AST."""
        with ErrorBoundary(error_types=(Exception,), operation_name=
            'extract_features_tree_sitter'):
            tree = None
            root_node = None
            if ast and 'root' in ast:
                root_node = ast['root']
            else:
                tree = self._parser.parse(bytes(source_code, 'utf8'))
                if not tree:
                    raise ValueError('Failed to parse source code')
                root_node = tree.root_node
            features = {category: {} for category in PatternCategory}
            for category, patterns in self._queries.items():
                category_features = {}
                for pattern_name, pattern_info in patterns.items():
                    query = pattern_info['query']
                    extractor_func: Optional[ExtractorFn] = pattern_info[
                        'extract']
                    matches = []
                    for match in query.matches(root_node):
                        with ErrorBoundary(f'process_match_{pattern_name}',
                            error_types=(Exception,)):
                            result = QueryResult(pattern_name=pattern_name,
                                node=match.pattern_node, captures={c.name:
                                c.node for c in match.captures})
                            if extractor_func:
                                metadata = extractor_func(result)
                                if hasattr(metadata, '__await__'):
                                    log(f'Warning: Async extractor used in sync context for pattern {pattern_name}'
                                        , level='warning')
                                    result.metadata = {}
                                else:
                                    result.metadata = metadata
                            processed = self._process_query_result(result)
                            if processed:
                                matches.append(processed)
                    if matches:
                        category_features[pattern_name] = matches
                features[category] = category_features
            return ExtractedFeatures(features=features, documentation=self.
                _extract_documentation(features), metrics=self.
                _calculate_metrics(features, source_code))
        return ExtractedFeatures()

    def _extract_documentation(self, features: Dict[str, Any]) ->Documentation:
        """Extract documentation features from parsed content.
        
        This extracts docstrings, comments, TODOs, and other documentation elements
        from the parsed features.
        """
        doc_features = features.get(PatternCategory.DOCUMENTATION.value, {})
        documentation = Documentation()
        if 'docstring' in doc_features:
            documentation.docstrings = doc_features['docstring']
            for doc in documentation.docstrings:
                if 'text' in doc:
                    documentation.content += doc['text'] + '\n'
        if 'comment' in doc_features:
            documentation.comments = doc_features['comment']
        for comment_type in ['todo', 'fixme', 'note', 'warning']:
            if comment_type in doc_features:
                documentation.todos.extend(doc_features[comment_type])
        if 'metadata' in doc_features:
            documentation.metadata = {item.get('key', ''): item.get('value',
                '') for item in doc_features.get('metadata', []) if 'key' in
                item and 'value' in item}
        return documentation

    def _calculate_metrics(self, features: Dict[str, Any], source_code: str
        ) ->ComplexityMetrics:
        """Calculate complexity metrics from extracted features."""
        metrics = ComplexityMetrics()
        metrics.loc = len(source_code.splitlines())
        metrics.cyclomatic_complexity = self._calculate_cyclomatic_complexity(
            features)
        metrics.halstead_metrics = self._calculate_halstead_metrics(features)
        metrics.maintainability_index = self._calculate_maintainability_index(
            metrics)
        return metrics

    def _register_language_patterns(self) ->None:
        """Register pattern queries for the current language."""
        if self.language_id in self._patterns:
            for category_name, patterns in self._patterns[self.language_id
                ].items():
                for pattern_name, pattern in patterns.items():
                    if hasattr(pattern, 'pattern_type'
                        ) and pattern.pattern_type == ParserType.TREE_SITTER.value:
                        pattern_def = getattr(pattern, 'definition', pattern)
                        self._compile_pattern(pattern_def, category_name,
                            pattern_name)
        if 'common' in self._patterns:
            for category_name, patterns in self._patterns['common'].items():
                for pattern_name, pattern in patterns.items():
                    if hasattr(pattern, 'pattern_type'
                        ) and pattern.pattern_type == ParserType.TREE_SITTER.value:
                        pattern_def = getattr(pattern, 'definition', pattern)
                        self._compile_pattern(pattern_def, category_name,
                            pattern_name)


class CustomFeatureExtractor(BaseFeatureExtractor):
    """[3.2.2] Custom parser feature extraction."""

    def extract_features(self, ast: Dict[str, Any], source_code: str
        ) ->ExtractedFeatures:
        """
        Extract features using regex patterns.
        
        USES: [pattern_processor.py] pattern_processor.get_patterns_for_file()
        RETURNS: [models.py] ExtractedFeatures containing:
        - Documentation
        - Complexity metrics
        - Pattern matches
        """
        with ErrorBoundary(error_types=(Exception,), operation_name=
            'extract_features_custom'):
            if not ast:
                log(f'No AST provided for feature extraction', level='debug')
                ast = {}
            features = {category.value: {} for category in PatternCategory}
            for category_enum in PatternCategory:
                category = category_enum.value
                if category not in self._patterns:
                    continue
                category_features = {}
                for pattern_name, pattern in self._patterns[category].items():
                    if pattern.regex:
                        matches = []
                        for match in pattern.regex.finditer(source_code):
                            result = {'text': match.group(0), 'start':
                                match.start(), 'end': match.end(), 'groups':
                                match.groups(), 'named_groups': match.
                                groupdict()}
                            if pattern.extract:
                                with ErrorBoundary(
                                    f'pattern_extraction_{pattern_name}',
                                    error_types=(Exception,)):
                                    extracted = pattern.extract(result)
                                    if extracted:
                                        result.update(extracted)
                            matches.append(result)
                        if matches:
                            category_features[pattern_name] = matches
                features[category] = category_features
            if ast and 'nodes' in ast:
                self._process_ast_nodes(ast['nodes'], features)
            documentation = self._extract_documentation(features)
            metrics = self._calculate_metrics(features, source_code)
            return ExtractedFeatures(features=features, documentation=
                documentation, metrics=metrics)
        return ExtractedFeatures()

    def _process_ast_nodes(self, nodes: List[Dict[str, Any]], features:
        Dict[str, Dict[str, Any]]) ->None:
        """Process AST nodes from a custom parser and add them to features."""
        if not nodes:
            return
        for node in nodes:
            node_type = node.get('type')
            if not node_type:
                continue
            category = self._get_category_for_node_type(node_type)
            if not category:
                continue
            if node_type not in features[category]:
                features[category][node_type] = []
            features[category][node_type].append(node)

    def _get_category_for_node_type(self, node_type: str) ->Optional[str]:
        """Map a node type to a feature category."""
        from parsers.models import PATTERN_CATEGORIES
        for category in PatternCategory:
            category_value = category.value
            for file_type in PATTERN_CATEGORIES.get(category, {}):
                if node_type in PATTERN_CATEGORIES[category][file_type]:
                    return category_value
        if node_type in ['comment', 'docstring', 'javadoc']:
            return PatternCategory.DOCUMENTATION.value
        elif node_type in ['import', 'include', 'namespace', 'module']:
            return PatternCategory.STRUCTURE.value
        elif node_type in ['function', 'class', 'method', 'constructor']:
            return PatternCategory.SYNTAX.value
        elif node_type in ['type', 'variable', 'parameter']:
            return PatternCategory.SEMANTICS.value
        return None

    def _extract_documentation(self, features: Dict[str, Any]) ->Documentation:
        """Extract documentation features from parsed content."""
        doc_features = features.get(PatternCategory.DOCUMENTATION.value, {})
        documentation = Documentation()
        if 'docstring' in doc_features:
            documentation.docstrings = doc_features['docstring']
            for doc in documentation.docstrings:
                if 'text' in doc:
                    documentation.content += doc['text'] + '\n'
        if 'comment' in doc_features:
            documentation.comments = doc_features['comment']
        for comment_type in ['todo', 'fixme', 'note', 'warning']:
            if comment_type in doc_features:
                documentation.todos.extend(doc_features[comment_type])
        if 'metadata' in doc_features:
            documentation.metadata = {item.get('key', ''): item.get('value',
                '') for item in doc_features.get('metadata', []) if 'key' in
                item and 'value' in item}
        return documentation

    def _calculate_metrics(self, features: Dict[str, Any], source_code: str
        ) ->ComplexityMetrics:
        """Calculate code complexity metrics based on extracted features."""
        metrics = ComplexityMetrics()
        lines = source_code.splitlines()
        metrics.lines_of_code = {'total': len(lines), 'code': len([l for l in
            lines if l.strip() and not l.strip().startswith(('#', '//',
            '/*', '*', '"""', "'''"))]), 'comment': len([l for l in lines if
            l.strip() and l.strip().startswith(('#', '//', '/*', '*', '"""',
            "'''"))]), 'blank': len([l for l in lines if not l.strip()])}
        syntax_features = features.get(PatternCategory.SYNTAX.value, {})
        branch_count = 0
        for branch_type in ['if', 'for', 'while', 'case', 'switch']:
            if branch_type in syntax_features:
                branch_count += len(syntax_features[branch_type])
        metrics.cyclomatic = branch_count + 1
        metrics.cognitive = branch_count
        return metrics
