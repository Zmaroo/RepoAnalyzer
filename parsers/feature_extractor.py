"""Feature extraction implementations."""

from typing import Dict, Any, List, Optional, Union, Generator, Tuple, Callable, TypeVar, cast, Awaitable, Set
from tree_sitter import Node, Query, QueryError, Parser, Language, TreeCursor
from .types import FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics, ExtractedFeatures, PatternCategory
from parsers.models import QueryResult, FileClassification
from parsers.language_support import language_registry
from utils.logger import log
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary, handle_async_errors
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
from parsers.pattern_processor import PatternProcessor, PatternMatch, pattern_processor
from parsers.language_mapping import TREE_SITTER_LANGUAGES
from abc import ABC, abstractmethod
import asyncio

# Define a type for extractor functions
# Support both sync and async extractors
ExtractorFn = Union[Callable[[Any], Dict[str, Any]], Callable[[Any], Awaitable[Dict[str, Any]]]]

class BaseFeatureExtractor(ABC):
    """[3.2.0] Abstract base class for feature extraction."""
    
    def __init__(self, language_id: str, file_type: FileType):
        # [3.2.0.1] Initialize Base Extractor
        self.language_id = language_id
        self.file_type = file_type
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
        self._patterns = None
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize feature extractor resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("feature_extractor_initialization"):
                    # Get patterns for this file type
                    future = submit_async_task(pattern_processor.get_patterns_for_file(
                        FileClassification(
                            file_type=self.file_type,
                            language_id=self.language_id,
                            parser_type=language_registry.get_parser_type(self.language_id)
                        )
                    ))
                    self._pending_tasks.add(future)
                    try:
                        self._patterns = await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                    
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing feature extractor: {e}", level="error")
                raise
        return True
    
    @abstractmethod
    async def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features from existing AST."""
        pass
    
    async def cleanup(self):
        """Clean up feature extractor resources."""
        try:
            # Clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log(f"Feature extractor cleaned up for {self.language_id}", level="info")
        except Exception as e:
            log(f"Error cleaning up feature extractor: {e}", level="error")

class TreeSitterFeatureExtractor(BaseFeatureExtractor):
    """[3.2.1] Tree-sitter specific feature extraction."""
    
    # Constants for query execution limits
    QUERY_TIMEOUT_MICROS = 5000000  # 5 seconds
    QUERY_MATCH_LIMIT = 10000
    
    def __init__(self, language_id: str, file_type: FileType):
        super().__init__(language_id, file_type)
        # [3.2.1.1] Initialize Tree-sitter Components
        self._language_registry = language_registry
        self._parser = None
        self._queries = {}
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """Initialize tree-sitter feature extractor."""
        if not await super().initialize():
            return False
            
        try:
            async with AsyncErrorBoundary("tree_sitter_feature_extractor_initialization"):
                # Initialize parser
                future = submit_async_task(self._initialize_parser())
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                # Load patterns
                future = submit_async_task(self._load_patterns())
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                return True
        except Exception as e:
            log(f"Error initializing tree-sitter feature extractor: {e}", level="error")
            return False
    
    async def _initialize_parser(self):
        """Initialize tree-sitter parser."""
        self._parser = Parser()
        self._language = await self._language_registry.get_language(self.language_id)
        self._parser.set_language(self._language)
    
    async def _load_patterns(self):
        """Load patterns from central pattern processor."""
        for category in PatternCategory:
            category_name = category.value
            if category_name in self._patterns:
                for pattern in self._patterns[category_name].values():
                    if pattern_processor.validate_pattern(pattern, self.language_id):
                        await self._compile_pattern(pattern, category_name, "")
    
    @handle_async_errors(error_types=(Exception,))
    async def _compile_pattern(self, pattern_def: Union[str, Dict[str, Any]], category: str, name: str) -> None:
        """Compile a Tree-sitter query pattern and store in queries dict."""
        async with AsyncErrorBoundary(f"compile_pattern_{category}_{name}", error_types=(Exception,)):
            if isinstance(pattern_def, str):
                query_str = pattern_def
                extractor_func: Optional[ExtractorFn] = None
            else:
                query_str = pattern_def['pattern']
                # Get the extractor function from pattern definition
                extractor_func = pattern_def.get('extract')
                if extractor_func is not None and not callable(extractor_func):
                    log(f"Warning: Non-callable extractor for pattern {name}. Got {type(extractor_func)}", level="warning")
                    extractor_func = None
            
            # Create and configure query
            future = submit_async_task(self._language.query(query_str))
            self._pending_tasks.add(future)
            try:
                query = await asyncio.wrap_future(future)
                query.set_timeout_micros(self.QUERY_TIMEOUT_MICROS)
                query.set_match_limit(self.QUERY_MATCH_LIMIT)
                
                self._queries.setdefault(category, {})[name] = {
                    'query': query,
                    'extract': extractor_func
                }
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(Exception,))
    async def _process_query_result(self, result: QueryResult) -> Dict[str, Any]:
        """Process a single query result."""
        async with AsyncErrorBoundary(f"process_query_result_{result.pattern_name}", error_types=(Exception,)):
            future = submit_async_task(self._extract_node_features(result.node))
            self._pending_tasks.add(future)
            try:
                node_features = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
            
            # Add capture information
            node_features['captures'] = {}
            for name, node in result.captures.items():
                future = submit_async_task(self._extract_node_features(node))
                self._pending_tasks.add(future)
                try:
                    node_features['captures'][name] = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
            
            # Add metadata
            node_features.update(result.metadata)
            
            return node_features
        
        return {}
    
    async def _extract_node_features(self, node: Node) -> Dict[str, Any]:
        """Extract features from a node."""
        return {
            'type': node.type,
            'text': node.text.decode('utf8'),
            'start_byte': node.start_byte,
            'end_byte': node.end_byte,
            'start_point': node.start_point,
            'end_point': node.end_point,
            'is_named': node.is_named,
            'has_error': node.has_error,
            'grammar_name': node.grammar_name,
            'child_count': node.child_count,
            'named_child_count': node.named_child_count
        }
    
    @handle_async_errors(error_types=(Exception,))
    async def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """[3.2.1.2] Extract features from Tree-sitter AST."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("extract_features_tree_sitter", error_types=(Exception,)):
            # Check if we have a valid AST with a tree structure
            tree = None
            root_node = None
            
            if ast and "root" in ast:
                # If we have a complete AST with root node (directly from parser)
                root_node = ast["root"]
            else:
                # If we don't have a root node or need to create a new tree
                # [3.2.1.3] Parse Tree and Extract Features
                future = submit_async_task(self._parser.parse(bytes(source_code, "utf8")))
                self._pending_tasks.add(future)
                try:
                    tree = await asyncio.wrap_future(future)
                    if not tree:
                        raise ValueError("Failed to parse source code")
                    root_node = tree.root_node
                finally:
                    self._pending_tasks.remove(future)
                
            features = {category: {} for category in PatternCategory}
            
            # [3.2.1.4] Process Patterns by Category
            # USES: [pattern_processor.py] QueryResult
            for category, patterns in self._queries.items():
                category_features = {}
                for pattern_name, pattern_info in patterns.items():
                    query = pattern_info['query']
                    extractor_func: Optional[ExtractorFn] = pattern_info['extract']
                    matches = []
                    
                    # Process matches
                    future = submit_async_task(query.matches(root_node))
                    self._pending_tasks.add(future)
                    try:
                        query_matches = await asyncio.wrap_future(future)
                        for match in query_matches:
                            async with AsyncErrorBoundary(f"process_match_{pattern_name}", error_types=(Exception,)):
                                result = QueryResult(
                                    pattern_name=pattern_name,
                                    node=match.pattern_node,
                                    captures={c.name: c.node for c in match.captures}
                                )
                                if extractor_func:
                                    # Handle both sync and async extractors
                                    metadata = extractor_func(result)
                                    if hasattr(metadata, '__await__'):
                                        # This is an async function
                                        result.metadata = await metadata
                                    else:
                                        result.metadata = metadata
                                processed = await self._process_query_result(result)
                                if processed:
                                    matches.append(processed)
                    finally:
                        self._pending_tasks.remove(future)
                            
                    if matches:
                        category_features[pattern_name] = matches
                        
                features[category] = category_features
            
            # [3.2.1.5] Return Extracted Features
            # RETURNS: [models.py] ExtractedFeatures
            return ExtractedFeatures(
                features=features,
                documentation=await self._extract_documentation(features),
                metrics=await self._calculate_metrics(features, source_code)
            )
        
        # Return empty features on error
        return ExtractedFeatures()

    @handle_async_errors(error_types=(Exception,))
    async def _extract_documentation(self, features: Dict[str, Any]) -> Documentation:
        """Extract documentation features from parsed content."""
        doc_features = features.get(PatternCategory.DOCUMENTATION.value, {})
        
        # Initialize Documentation object
        documentation = Documentation()
        
        # Extract docstrings
        if 'docstring' in doc_features:
            documentation.docstrings = doc_features['docstring']
            
            # Combine docstring content
            for doc in documentation.docstrings:
                if 'text' in doc:
                    documentation.content += doc['text'] + "\n"
        
        # Extract comments
        if 'comment' in doc_features:
            documentation.comments = doc_features['comment']
        
        # Extract TODOs
        for comment_type in ['todo', 'fixme', 'note', 'warning']:
            if comment_type in doc_features:
                documentation.todos.extend(doc_features[comment_type])
        
        # Extract metadata (author, version, etc.)
        if 'metadata' in doc_features:
            documentation.metadata = {
                item.get('key', ''): item.get('value', '')
                for item in doc_features.get('metadata', [])
                if 'key' in item and 'value' in item
            }
            
        return documentation
    
    @handle_async_errors(error_types=(Exception,))
    async def _calculate_metrics(self, features: Dict[str, Any], source_code: str) -> ComplexityMetrics:
        """Calculate complexity metrics from extracted features."""
        metrics = ComplexityMetrics()
        
        # Calculate basic complexity metrics
        metrics.loc = len(source_code.splitlines())
        
        # Calculate cyclomatic complexity
        future = submit_async_task(self._calculate_cyclomatic_complexity(features))
        self._pending_tasks.add(future)
        try:
            metrics.cyclomatic_complexity = await asyncio.wrap_future(future)
        finally:
            self._pending_tasks.remove(future)
        
        # Calculate maintainability metrics
        future = submit_async_task(self._calculate_halstead_metrics(features))
        self._pending_tasks.add(future)
        try:
            metrics.halstead_metrics = await asyncio.wrap_future(future)
        finally:
            self._pending_tasks.remove(future)
        
        future = submit_async_task(self._calculate_maintainability_index(metrics))
        self._pending_tasks.add(future)
        try:
            metrics.maintainability_index = await asyncio.wrap_future(future)
        finally:
            self._pending_tasks.remove(future)
        
        return metrics

class CustomFeatureExtractor(BaseFeatureExtractor):
    """[3.2.2] Custom parser feature extraction."""
    
    def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """
        Extract features using regex patterns.
        
        USES: [pattern_processor.py] pattern_processor.get_patterns_for_file()
        RETURNS: [models.py] ExtractedFeatures containing:
        - Documentation
        - Complexity metrics
        - Pattern matches
        """
        with ErrorBoundary("extract_features_custom", error_types=(Exception,)):
            # Check if we have a valid AST structure
            if not ast:
                log(f"No AST provided for feature extraction", level="debug")
                ast = {}  # Initialize empty AST to continue with regex-based extraction
            
            # [3.2.2.1] Initialize Feature Categories
            features = {category.value: {} for category in PatternCategory}
            
            # [3.2.2.2] Process each category
            for category_enum in PatternCategory:
                category = category_enum.value
                if category not in self._patterns:
                    continue
                    
                category_features = {}
                
                # [3.2.2.3] Process each regex pattern
                for pattern_name, pattern in self._patterns[category].items():
                    if pattern.regex:
                        matches = []
                        for match in pattern.regex.finditer(source_code):
                            result = {
                                'text': match.group(0),
                                'start': match.start(),
                                'end': match.end(),
                                'groups': match.groups(),
                                'named_groups': match.groupdict()
                            }
                            
                            # [3.2.2.4] Apply custom extractor if available
                            if pattern.extract:
                                with ErrorBoundary(f"pattern_extraction_{pattern_name}", error_types=(Exception,)):
                                    extracted = pattern.extract(result)
                                    if extracted:
                                        result.update(extracted)
                                
                            matches.append(result)
                            
                        if matches:
                            category_features[pattern_name] = matches
                
                features[category] = category_features
            
            # Extract AST nodes if available
            if ast and 'nodes' in ast:
                self._process_ast_nodes(ast['nodes'], features)
                
            # [3.2.2.5] Return standardized features
            # RETURNS: [models.py] ExtractedFeatures
            documentation = self._extract_documentation(features)
            metrics = self._calculate_metrics(features, source_code)
            
            return ExtractedFeatures(
                features=features,
                documentation=documentation,
                metrics=metrics
            )
        
        # Return empty features on error
        return ExtractedFeatures()
            
    def _process_ast_nodes(self, nodes: List[Dict[str, Any]], features: Dict[str, Dict[str, Any]]) -> None:
        """Process AST nodes from a custom parser and add them to features."""
        if not nodes:
            return
            
        # Map node types to feature categories
        for node in nodes:
            node_type = node.get('type')
            if not node_type:
                continue
                
            # Determine which category this node belongs to
            category = self._get_category_for_node_type(node_type)
            if not category:
                continue
                
            # Add node to appropriate category
            if node_type not in features[category]:
                features[category][node_type] = []
                
            features[category][node_type].append(node)
    
    def _get_category_for_node_type(self, node_type: str) -> Optional[str]:
        """Map a node type to a feature category."""
        from parsers.models import PATTERN_CATEGORIES
        
        # Check each category's patterns
        for category in PatternCategory:
            category_value = category.value
            for file_type in PATTERN_CATEGORIES.get(category, {}):
                if node_type in PATTERN_CATEGORIES[category][file_type]:
                    return category_value
        
        # Default categorization based on node type
        if node_type in ['comment', 'docstring', 'javadoc']:
            return PatternCategory.DOCUMENTATION.value
        elif node_type in ['import', 'include', 'namespace', 'module']:
            return PatternCategory.STRUCTURE.value
        elif node_type in ['function', 'class', 'method', 'constructor']:
            return PatternCategory.SYNTAX.value
        elif node_type in ['type', 'variable', 'parameter']:
            return PatternCategory.SEMANTICS.value
            
        return None
            
    def _extract_documentation(self, features: Dict[str, Any]) -> Documentation:
        """Extract documentation features from parsed content."""
        # Reuse same logic as TreeSitterFeatureExtractor
        doc_features = features.get(PatternCategory.DOCUMENTATION.value, {})
        
        # Initialize Documentation object
        documentation = Documentation()
        
        # Extract docstrings
        if 'docstring' in doc_features:
            documentation.docstrings = doc_features['docstring']
            
            # Combine docstring content
            for doc in documentation.docstrings:
                if 'text' in doc:
                    documentation.content += doc['text'] + "\n"
        
        # Extract comments
        if 'comment' in doc_features:
            documentation.comments = doc_features['comment']
        
        # Extract TODOs
        for comment_type in ['todo', 'fixme', 'note', 'warning']:
            if comment_type in doc_features:
                documentation.todos.extend(doc_features[comment_type])
        
        # Extract metadata (author, version, etc.)
        if 'metadata' in doc_features:
            documentation.metadata = {
                item.get('key', ''): item.get('value', '')
                for item in doc_features.get('metadata', [])
                if 'key' in item and 'value' in item
            }
            
        return documentation
    
    def _calculate_metrics(self, features: Dict[str, Any], source_code: str) -> ComplexityMetrics:
        """Calculate code complexity metrics based on extracted features."""
        # Reuse same logic as TreeSitterFeatureExtractor
        metrics = ComplexityMetrics()
        
        # Count lines of code
        lines = source_code.splitlines()
        metrics.lines_of_code = {
            'total': len(lines),
            'code': len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'comment': len([l for l in lines if l.strip() and l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'blank': len([l for l in lines if not l.strip()])
        }
        
        # Basic complexity metrics for custom parsers
        # (more limited than tree-sitter but still useful)
        syntax_features = features.get(PatternCategory.SYNTAX.value, {})
        
        # Count branches
        branch_count = 0
        for branch_type in ['if', 'for', 'while', 'case', 'switch']:
            if branch_type in syntax_features:
                branch_count += len(syntax_features[branch_type])
        
        metrics.cyclomatic = branch_count + 1
        metrics.cognitive = branch_count
        
        return metrics