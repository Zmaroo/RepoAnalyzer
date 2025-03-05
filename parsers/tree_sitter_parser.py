"""Tree-sitter based code parsing."""

from typing import Dict, Set, Optional, Any, List
import hashlib
import asyncio
from tree_sitter_language_pack import get_parser, get_language, SupportedLanguage
from utils.logger import log
from parsers.base_parser import BaseParser
from utils.error_handling import handle_errors, handle_async_errors, ProcessingError, ErrorBoundary, AsyncErrorBoundary, ErrorSeverity
from parsers.language_mapping import TREE_SITTER_LANGUAGES
from parsers.models import PatternMatch, ProcessedPattern
from parsers.types import FileType, ParserType, FeatureCategory, ParserResult
from utils.cache import cache_coordinator
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task

class TreeSitterError(ProcessingError):
    """Tree-sitter specific errors."""
    pass

class TreeSitterParser(BaseParser):
    """Tree-sitter implementation of the base parser."""
    
    def __init__(self, language_id: str, file_type: FileType):
        super().__init__(language_id, file_type, parser_type=ParserType.TREE_SITTER)
        self._language = None
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        
        # Initialize the block extractor
        from parsers.block_extractor import block_extractor
        self.block_extractor = block_extractor
        
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary(f"tree-sitter {self.language_id} initialization"):
                    self._language = get_parser(self.language_id)
                    if not self._language:
                        raise TreeSitterError(f"Failed to get tree-sitter parser for {self.language_id}")
                    self._initialized = True
                    log(f"Tree-sitter {self.language_id} parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing tree-sitter {self.language_id} parser: {e}", level="error")
                raise
        return True

    @handle_errors(error_types=(LookupError, TreeSitterError))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Generate AST using tree-sitter with caching."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"tree-sitter {self.language_id} parsing"):
            try:
                # Create a unique cache key based on language and source code hash
                source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
                cache_key = f"ast:{self.language_id}:{source_hash}"
                
                # First try to get from cache
                future = submit_async_task(cache_coordinator.get_async(cache_key))
                self._pending_tasks.add(future)
                try:
                    cached_ast = await asyncio.wrap_future(future)
                    if cached_ast and "tree" in cached_ast:
                        log(f"AST cache hit for {self.language_id}", level="debug")
                        return cached_ast
                finally:
                    self._pending_tasks.remove(future)
                
                # If not in cache, generate the AST
                future = submit_async_task(self._parse_content, source_code)
                self._pending_tasks.add(future)
                try:
                    ast_dict = await asyncio.wrap_future(future)
                    
                    # Cache the AST for future use
                    cache_data = {"tree": ast_dict["tree"], "metadata": {"language": self.language_id}}
                    future = submit_async_task(cache_coordinator.set_async(cache_key, cache_data))
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                        log(f"AST cached for {self.language_id}", level="debug")
                    finally:
                        self._pending_tasks.remove(future)
                    
                    return ast_dict
                finally:
                    self._pending_tasks.remove(future)
                    
            except Exception as e:
                log(f"Error in tree-sitter parsing for {self.language_id}: {e}", level="error")
                raise

    def _parse_content(self, source_code: str) -> Dict[str, Any]:
        """Internal synchronous parsing method."""
        tree = self._language.parse(source_code.encode("utf8"))
        root_node = tree.root_node
        
        # Full AST with root node (not serializable for caching)
        ast_dict = {
            "root": root_node,
            "tree": self._convert_tree_to_dict(root_node)
        }
        
        return ast_dict

    @handle_async_errors(error_types=(Exception,))
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code and return structured results."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"tree-sitter {self.language_id} parsing"):
            try:
                # Parse the source
                ast = await self._parse_source(source_code)
                if not ast:
                    return None
                
                # Extract features asynchronously
                future = submit_async_task(self._extract_features, ast, source_code)
                self._pending_tasks.add(future)
                try:
                    features = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                return ParserResult(
                    success=True,
                    ast=ast,
                    features=features,
                    documentation=features.get(FeatureCategory.DOCUMENTATION.value, {}),
                    complexity=features.get(FeatureCategory.SYNTAX.value, {}).get("metrics", {}),
                    statistics=self.stats
                )
            except Exception as e:
                log(f"Error in tree-sitter {self.language_id} parser: {e}", level="error")
                return None

    def _extract_features(self, ast: Dict[str, Any], source_code: str) -> Dict[str, Dict[str, Any]]:
        """Extract features from the AST."""
        features = {}
        
        # Extract syntax features
        syntax_features = self._extract_syntax_features(ast, source_code)
        if syntax_features:
            features[FeatureCategory.SYNTAX.value] = syntax_features
        
        # Extract semantic features
        semantic_features = self._extract_semantic_features(ast, source_code)
        if semantic_features:
            features[FeatureCategory.SEMANTICS.value] = semantic_features
        
        # Extract documentation features
        doc_features = self._extract_documentation_features(ast, source_code)
        if doc_features:
            features[FeatureCategory.DOCUMENTATION.value] = doc_features
        
        # Extract structural features
        structure_features = self._extract_structure_features(ast, source_code)
        if structure_features:
            features[FeatureCategory.STRUCTURE.value] = structure_features
        
        return features

    def _extract_syntax_features(self, ast: Dict[str, Any], source_code: str) -> Dict[str, Any]:
        """Extract syntax features from the AST."""
        features = {}
        
        # Extract basic syntax metrics
        metrics = self._extract_syntax_metrics(ast)
        if metrics:
            features["metrics"] = metrics
        
        # Extract syntax patterns
        patterns = self._extract_syntax_patterns(ast, source_code)
        if patterns:
            features["patterns"] = patterns
        
        return features

    def _extract_semantic_features(self, ast: Dict[str, Any], source_code: str) -> Dict[str, Any]:
        """Extract semantic features from the AST."""
        features = {}
        
        # Extract type information
        types = self._extract_type_info(ast)
        if types:
            features["types"] = types
        
        # Extract variable usage
        variables = self._extract_variable_usage(ast)
        if variables:
            features["variables"] = variables
        
        return features

    def _extract_documentation_features(self, ast: Dict[str, Any], source_code: str) -> Dict[str, Any]:
        """Extract documentation features from the AST."""
        features = {}
        
        # Extract comments and docstrings
        docs = self._extract_comments_and_docs(ast, source_code)
        if docs:
            features["documentation"] = docs
        
        return features

    def _extract_structure_features(self, ast: Dict[str, Any], source_code: str) -> Dict[str, Any]:
        """Extract structural features from the AST."""
        features = {}
        
        # Extract module structure
        structure = self._extract_module_structure(ast)
        if structure:
            features["structure"] = structure
        
        return features

    def _convert_tree_to_dict(self, node) -> Dict[str, Any]:
        """Convert tree-sitter node to dict."""
        return {
            'type': node.type,
            'start': node.start_point,
            'end': node.end_point,
            'text': node.text.decode('utf8') if len(node.children) == 0 else None,
            'children': [self._convert_tree_to_dict(child) for child in node.children] if node.children else []
        }

    def get_supported_languages(self) -> Set[str]:
        """Get set of supported languages."""
        return TREE_SITTER_LANGUAGES.copy()

    async def cleanup(self):
        """Clean up parser resources."""
        try:
            if self._pending_tasks:
                log(f"Cleaning up {len(self._pending_tasks)} pending tree-sitter {self.language_id} tasks", level="info")
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            self._language = None
            log(f"Tree-sitter {self.language_id} parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up tree-sitter {self.language_id} parser: {e}", level="error") 