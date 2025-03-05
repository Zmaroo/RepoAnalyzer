"""Feature extraction implementations."""

from typing import Dict, Any, List, Optional, Union, Generator, Tuple, Callable, TypeVar, cast, Awaitable, Set
from tree_sitter import Node, Query, QueryError, Parser, Language, TreeCursor
from .types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult
)
from parsers.models import QueryResult, FileClassification, PATTERN_CATEGORIES
from parsers.language_support import language_registry
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors
from utils.shutdown import register_shutdown_handler
from parsers.pattern_processor import PatternProcessor, PatternMatch, pattern_processor
from parsers.language_mapping import TREE_SITTER_LANGUAGES
from parsers.parser_interfaces import AIParserInterface
from abc import ABC, abstractmethod
import asyncio
from utils.error_handling import ProcessingError, ErrorSeverity
from utils.cache import UnifiedCache, cache_coordinator

# Define a type for extractor functions
# Support both sync and async extractors
ExtractorFn = Union[Callable[[Any], Dict[str, Any]], Callable[[Any], Awaitable[Dict[str, Any]]]]

class BaseFeatureExtractor(ABC, AIParserInterface):
    """[3.2.0] Abstract base class for feature extraction."""
    
    def __init__(self, language_id: str):
        """Private constructor - use create() instead."""
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION
            }
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._cache = None
        self._lock = asyncio.Lock()
    
    async def _initialize_cache(self):
        """Initialize cache based on extractor type."""
        if not self._cache:
            self._cache = UnifiedCache(f"feature_extractor_{self.language_id}")
            await cache_coordinator.register_cache(self._cache)
    
    async def _check_features_cache(self, ast: Dict[str, Any], source_code: str) -> Optional[ExtractedFeatures]:
        """Check if features are cached."""
        if not self._cache:
            return None
            
        import hashlib
        # Create cache key based on both AST and source code
        # This ensures cache invalidation if either changes
        ast_hash = hashlib.md5(str(ast).encode('utf8')).hexdigest()
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"features:{self.language_id}:{ast_hash}:{source_hash}"
        
        cached_features = await self._cache.get(cache_key)
        if cached_features:
            return ExtractedFeatures(**cached_features)
        return None
    
    async def _store_features_in_cache(self, ast: Dict[str, Any], source_code: str, features: ExtractedFeatures):
        """Store extracted features in cache."""
        if not self._cache:
            return
            
        import hashlib
        ast_hash = hashlib.md5(str(ast).encode('utf8')).hexdigest()
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"features:{self.language_id}:{ast_hash}:{source_hash}"
        
        await self._cache.set(cache_key, {
            'features': features.features,
            'documentation': features.documentation.__dict__,
            'metrics': features.metrics.__dict__
        })
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError(f"Feature extractor not initialized for {self.language_id}. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls, language_id: str) -> 'BaseFeatureExtractor':
        """Async factory method to create and initialize a BaseFeatureExtractor instance."""
        instance = cls(language_id)
        try:
            async with AsyncErrorBoundary(
                operation_name=f"feature extractor initialization for {language_id}",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component(f"feature_extractor_{language_id}")
                
                instance._initialized = True
                await log(f"Feature extractor initialized for {language_id}", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing feature extractor for {language_id}: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize feature extractor for {language_id}: {e}")
    
    @abstractmethod
    async def extract_features(self, code: str) -> Dict[str, Any]:
        """Extract features from code. Must be implemented by subclasses."""
        pass
    
    async def cleanup(self):
        """Clean up feature extractor resources."""
        try:
            if not self._initialized:
                return
                
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component(f"feature_extractor_{self.language_id}")
            
            self._initialized = False
            await log(f"Feature extractor cleaned up for {self.language_id}", level="info")
        except Exception as e:
            await log(f"Error cleaning up feature extractor for {self.language_id}: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup feature extractor for {self.language_id}: {e}")

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"{self.language_id} feature extraction AI processing"):
            try:
                results = AIProcessingResult(success=True)
                
                # Extract features first
                features = await self.extract_features(source_code)
                
                # Process with understanding capability
                if AICapability.CODE_UNDERSTANDING in self.capabilities:
                    understanding = await self._process_with_understanding(features, context)
                    results.context_info.update(understanding)
                
                # Process with generation capability
                if AICapability.CODE_GENERATION in self.capabilities:
                    generation = await self._process_with_generation(features, context)
                    results.suggestions.extend(generation)
                
                # Process with modification capability
                if AICapability.CODE_MODIFICATION in self.capabilities:
                    modification = await self._process_with_modification(features, context)
                    results.ai_insights.update(modification)
                
                return results
            except Exception as e:
                log(f"Error in feature extraction AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )
    
    async def _process_with_understanding(
        self,
        features: ExtractedFeatures,
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code understanding capability."""
        understanding = {}
        
        # Analyze feature categories
        for category in features.features:
            category_understanding = await self._analyze_feature_category(
                category,
                features.features[category],
                context
            )
            if category_understanding:
                understanding[category] = category_understanding
        
        # Add documentation insights
        if features.documentation:
            understanding["documentation"] = features.documentation
        
        # Add complexity insights
        if features.metrics:
            understanding["complexity"] = features.metrics
        
        return understanding
    
    async def _process_with_generation(
        self,
        features: ExtractedFeatures,
        context: AIContext
    ) -> List[str]:
        """Process with code generation capability."""
        suggestions = []
        
        # Generate suggestions based on features
        for category in features.features:
            category_suggestions = await self._generate_from_category(
                category,
                features.features[category],
                context
            )
            suggestions.extend(category_suggestions)
        
        return suggestions
    
    async def _process_with_modification(
        self,
        features: ExtractedFeatures,
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code modification capability."""
        insights = {}
        
        # Analyze modification opportunities
        for category in features.features:
            category_insights = await self._analyze_modification_opportunities(
                category,
                features.features[category],
                context
            )
            if category_insights:
                insights[category] = category_insights
        
        return insights
    
    async def _analyze_feature_category(
        self,
        category: str,
        features: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze features in a category."""
        analysis = {
            "patterns": self._identify_patterns(features),
            "relationships": self._analyze_relationships(features),
            "metrics": self._calculate_metrics(features)
        }
        
        # Add category-specific analysis
        if category == "syntax":
            analysis.update(self._analyze_syntax(features))
        elif category == "semantics":
            analysis.update(self._analyze_semantics(features))
        elif category == "documentation":
            analysis.update(self._analyze_documentation(features))
        
        return analysis
    
    async def _generate_from_category(
        self,
        category: str,
        features: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Generate suggestions from category features."""
        suggestions = []
        
        # Generate category-specific suggestions
        if category == "syntax":
            suggestions.extend(self._generate_syntax_suggestions(features, context))
        elif category == "semantics":
            suggestions.extend(self._generate_semantic_suggestions(features, context))
        elif category == "documentation":
            suggestions.extend(self._generate_documentation_suggestions(features, context))
        
        return suggestions
    
    async def _analyze_modification_opportunities(
        self,
        category: str,
        features: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze opportunities for code modification."""
        opportunities = {
            "improvements": [],
            "refactoring": [],
            "optimizations": []
        }
        
        # Analyze category-specific opportunities
        if category == "syntax":
            opportunities.update(self._analyze_syntax_modifications(features, context))
        elif category == "semantics":
            opportunities.update(self._analyze_semantic_modifications(features, context))
        elif category == "documentation":
            opportunities.update(self._analyze_documentation_modifications(features, context))
        
        return opportunities
    
    def _identify_patterns(self, features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify patterns in features."""
        patterns = []
        
        for feature_type, feature_data in features.items():
            if isinstance(feature_data, dict):
                patterns.extend(self._extract_patterns_from_dict(feature_type, feature_data))
            elif isinstance(feature_data, list):
                patterns.extend(self._extract_patterns_from_list(feature_type, feature_data))
        
        return patterns
    
    def _analyze_relationships(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze relationships between features."""
        relationships = {
            "dependencies": [],
            "hierarchy": [],
            "usage": []
        }
        
        # Analyze feature relationships
        for feature1 in features:
            for feature2 in features:
                if feature1 != feature2:
                    if self._are_dependent(features[feature1], features[feature2]):
                        relationships["dependencies"].append((feature1, feature2))
                    if self._has_hierarchy(features[feature1], features[feature2]):
                        relationships["hierarchy"].append((feature1, feature2))
                    if self._has_usage(features[feature1], features[feature2]):
                        relationships["usage"].append((feature1, feature2))
        
        return relationships
    
    def _calculate_metrics(self, features: Dict[str, Any]) -> Dict[str, float]:
        """Calculate metrics for features."""
        return {
            "complexity": self._calculate_complexity(features),
            "cohesion": self._calculate_cohesion(features),
            "coupling": self._calculate_coupling(features)
        }
    
    def _analyze_syntax(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze syntax-specific features."""
        return {
            "structure": self._analyze_code_structure(features),
            "style": self._analyze_coding_style(features),
            "patterns": self._identify_syntax_patterns(features)
        }
    
    def _analyze_semantics(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze semantic features."""
        return {
            "types": self._analyze_type_usage(features),
            "flow": self._analyze_control_flow(features),
            "data": self._analyze_data_flow(features)
        }
    
    def _analyze_documentation(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze documentation features."""
        return {
            "coverage": self._analyze_doc_coverage(features),
            "quality": self._analyze_doc_quality(features),
            "patterns": self._identify_doc_patterns(features)
        }
    
    def _generate_syntax_suggestions(
        self,
        features: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Generate syntax-related suggestions."""
        suggestions = []
        
        # Check structure
        structure_issues = self._check_structure_issues(features)
        if structure_issues:
            suggestions.extend(structure_issues)
        
        # Check style
        style_issues = self._check_style_issues(features, context)
        if style_issues:
            suggestions.extend(style_issues)
        
        return suggestions
    
    def _generate_semantic_suggestions(
        self,
        features: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Generate semantic suggestions."""
        suggestions = []
        
        # Check types
        type_issues = self._check_type_issues(features)
        if type_issues:
            suggestions.extend(type_issues)
        
        # Check flow
        flow_issues = self._check_flow_issues(features)
        if flow_issues:
            suggestions.extend(flow_issues)
        
        return suggestions
    
    def _generate_documentation_suggestions(
        self,
        features: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Generate documentation suggestions."""
        suggestions = []
        
        # Check coverage
        coverage_issues = self._check_doc_coverage(features)
        if coverage_issues:
            suggestions.extend(coverage_issues)
        
        # Check quality
        quality_issues = self._check_doc_quality(features)
        if quality_issues:
            suggestions.extend(quality_issues)
        
        return suggestions
    
    def _analyze_syntax_modifications(
        self,
        features: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze syntax modification opportunities."""
        return {
            "structure_improvements": self._find_structure_improvements(features),
            "style_improvements": self._find_style_improvements(features, context),
            "pattern_improvements": self._find_pattern_improvements(features)
        }
    
    def _analyze_semantic_modifications(
        self,
        features: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze semantic modification opportunities."""
        return {
            "type_improvements": self._find_type_improvements(features),
            "flow_improvements": self._find_flow_improvements(features),
            "data_improvements": self._find_data_improvements(features)
        }
    
    def _analyze_documentation_modifications(
        self,
        features: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze documentation modification opportunities."""
        return {
            "coverage_improvements": self._find_coverage_improvements(features),
            "quality_improvements": self._find_quality_improvements(features),
            "pattern_improvements": self._find_doc_pattern_improvements(features)
        }

    async def extract_cross_repo_features(
        self,
        repo_features: Dict[int, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract features across repositories."""
        common_features = await self._find_common_features(repo_features)
        insights = await self._generate_cross_repo_insights(common_features)
        return {
            "common_features": common_features,
            "insights": insights
        }

class TreeSitterFeatureExtractor(BaseFeatureExtractor):
    """[3.2.1] Tree-sitter specific feature extraction."""
    
    # Constants for query execution limits
    QUERY_TIMEOUT_MICROS = 5000000  # 5 seconds
    QUERY_MATCH_LIMIT = 10000
    
    def __init__(self, language_id: str, file_type: FileType):
        super().__init__(language_id)
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
                task = asyncio.create_task(self._initialize_parser())
                self._pending_tasks.add(task)
                try:
                    await task
                finally:
                    self._pending_tasks.remove(task)
                
                # Load patterns
                task = asyncio.create_task(self._load_patterns())
                self._pending_tasks.add(task)
                try:
                    await task
                finally:
                    self._pending_tasks.remove(task)
                
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
            task = asyncio.create_task(self._language.query(query_str))
            self._pending_tasks.add(task)
            try:
                query = await task
                query.set_timeout_micros(self.QUERY_TIMEOUT_MICROS)
                query.set_match_limit(self.QUERY_MATCH_LIMIT)
                
                self._queries.setdefault(category, {})[name] = {
                    'query': query,
                    'extract': extractor_func
                }
            finally:
                self._pending_tasks.remove(task)
    
    @handle_async_errors(error_types=(Exception,))
    async def _process_query_result(self, result: QueryResult) -> Dict[str, Any]:
        """Process a single query result."""
        async with AsyncErrorBoundary(f"process_query_result_{result.pattern_name}", error_types=(Exception,)):
            task = asyncio.create_task(self._extract_node_features(result.node))
            self._pending_tasks.add(task)
            try:
                node_features = await task
            finally:
                self._pending_tasks.remove(task)
            
            # Add capture information
            node_features['captures'] = {}
            for name, node in result.captures.items():
                task = asyncio.create_task(self._extract_node_features(node))
                self._pending_tasks.add(task)
                try:
                    node_features['captures'][name] = await task
                finally:
                    self._pending_tasks.remove(task)
            
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
            # Check cache first
            cached_features = await self._check_features_cache(ast, source_code)
            if cached_features:
                return cached_features
            
            # Check if we have a valid AST with a tree structure
            tree = None
            root_node = None
            
            if ast and "root" in ast:
                # If we have a complete AST with root node (directly from parser)
                root_node = ast["root"]
            else:
                # If we don't have a root node or need to create a new tree
                # [3.2.1.3] Parse Tree and Extract Features
                task = asyncio.create_task(self._parser.parse(bytes(source_code, "utf8")))
                self._pending_tasks.add(task)
                try:
                    tree = await task
                    if not tree:
                        raise ValueError("Failed to parse source code")
                    root_node = tree.root_node
                finally:
                    self._pending_tasks.remove(task)
                
            features = {category: {} for category in PatternCategory}
            
            # [3.2.1.4] Process Patterns by Category
            for category, patterns in self._queries.items():
                category_features = {}
                for pattern_name, pattern_info in patterns.items():
                    query = pattern_info['query']
                    extractor_func: Optional[ExtractorFn] = pattern_info['extract']
                    matches = []
                    
                    # Process matches
                    task = asyncio.create_task(query.matches(root_node))
                    self._pending_tasks.add(task)
                    try:
                        query_matches = await task
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
                        self._pending_tasks.remove(task)
                            
                    if matches:
                        category_features[pattern_name] = matches
                        
                features[category] = category_features
            
            # Create ExtractedFeatures instance
            extracted_features = ExtractedFeatures(
                features=features,
                documentation=await self._extract_documentation(features),
                metrics=await self._calculate_metrics(features, source_code)
            )
            
            # Cache the results
            await self._store_features_in_cache(ast, source_code, extracted_features)
            
            return extracted_features
        
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
        task = asyncio.create_task(self._calculate_cyclomatic_complexity(features))
        self._pending_tasks.add(task)
        try:
            metrics.cyclomatic_complexity = await task
        finally:
            self._pending_tasks.remove(task)
        
        # Calculate maintainability metrics
        task = asyncio.create_task(self._calculate_halstead_metrics(features))
        self._pending_tasks.add(task)
        try:
            metrics.halstead_metrics = await task
        finally:
            self._pending_tasks.remove(task)
        
        task = asyncio.create_task(self._calculate_maintainability_index(metrics))
        self._pending_tasks.add(task)
        try:
            metrics.maintainability_index = await task
        finally:
            self._pending_tasks.remove(task)
        
        return metrics

class CustomFeatureExtractor(BaseFeatureExtractor):
    """[3.2.2] Custom parser feature extraction."""
    
    async def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features using regex patterns."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("extract_features_custom", error_types=(Exception,)):
            # Check cache first
            cached_features = await self._check_features_cache(ast, source_code)
            if cached_features:
                return cached_features
            
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
                                with AsyncErrorBoundary(f"pattern_extraction_{pattern_name}", error_types=(Exception,)):
                                    extracted = pattern.extract(result)
                                    if extracted:
                                        result.update(extracted)
                                
                            matches.append(result)
                            
                        if matches:
                            category_features[pattern_name] = matches
                
                features[category] = category_features
            
            # Extract AST nodes if available
            if ast and 'nodes' in ast:
                await self._process_ast_nodes(ast['nodes'], features)
                
            # Create ExtractedFeatures instance
            documentation = await self._extract_documentation(features)
            metrics = await self._calculate_metrics(features, source_code)
            extracted_features = ExtractedFeatures(
                features=features,
                documentation=documentation,
                metrics=metrics
            )
            
            # Cache the results
            await self._store_features_in_cache(ast, source_code, extracted_features)
            
            return extracted_features
    
    async def _process_ast_nodes(self, nodes: List[Dict[str, Any]], features: Dict[str, Dict[str, Any]]) -> None:
        """Process AST nodes from a custom parser and add them to features."""
        if not nodes:
            return
            
        # Map node types to feature categories
        for node in nodes:
            node_type = node.get('type')
            if not node_type:
                continue
                
            # Determine which category this node belongs to
            category = await self._get_category_for_node_type(node_type)
            if not category:
                continue
                
            # Add node to appropriate category
            if node_type not in features[category]:
                features[category][node_type] = []
                
            features[category][node_type].append(node)
    
    async def _get_category_for_node_type(self, node_type: str) -> Optional[str]:
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
            
    async def _extract_documentation(self, features: Dict[str, Any]) -> Documentation:
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
    
    async def _calculate_metrics(self, features: Dict[str, Any], source_code: str) -> ComplexityMetrics:
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

class UnifiedFeatureExtractor(BaseFeatureExtractor):
    """[3.2.3] Unified feature extraction."""
    
    async def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features using the unified category system."""
        features = {category: {} for category in PatternCategory}
        
        # Extract features by category and purpose
        for category in PatternCategory:
            for purpose in PatternPurpose:
                extracted = await self._extract_features_for_purpose(
                    ast,
                    source_code,
                    category,
                    purpose
                )
                if extracted:
                    features[category][purpose.value] = extracted
        
        # Create documentation features
        documentation = await self._extract_documentation(
            features[PatternCategory.DOCUMENTATION]
        )
        
        # Calculate complexity metrics
        metrics = await self._calculate_metrics(
            features[PatternCategory.SYNTAX],
            source_code
        )
        
        return ExtractedFeatures(
            features=features,
            documentation=documentation,
            metrics=metrics
        )
    
    async def _extract_features_for_purpose(
        self,
        ast: Dict[str, Any],
        source_code: str,
        category: PatternCategory,
        purpose: PatternPurpose
    ) -> Dict[str, Any]:
        """Extract features for a specific category and purpose."""
        features = {}
        
        # Get valid pattern types for this category/purpose
        valid_types = PATTERN_CATEGORIES.get(category, {}).get(self.file_type, {}).get(purpose, [])
        
        if not valid_types:
            return features
            
        # Extract features based on pattern types
        for pattern_type in valid_types:
            if pattern := self._patterns.get(category, {}).get(purpose, {}).get(pattern_type):
                matches = await self._process_pattern(source_code, pattern)
                if matches:
                    features[pattern_type] = matches
        
        return features

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