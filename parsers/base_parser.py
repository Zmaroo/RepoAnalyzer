"""Base parser implementation."""

from abc import abstractmethod
from typing import Optional, Dict, Any, List, Union, Type, Callable, Set
from .types import FileType, FeatureCategory, ParserType, ParserResult, ParserConfig, ParsingStatistics
from dataclasses import field
import re
import asyncio
from parsers.types import PatternCategory
from parsers.models import PatternType, QueryPattern
from utils.logger import log
from .parser_interfaces import BaseParserInterface
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary, ErrorSeverity
from utils.cache import cache_coordinator
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
from db.transaction import transaction_scope
from db.upsert_ops import coordinator as upsert_coordinator

class BaseParser(BaseParserInterface):
    """Base implementation for parsers.
    
    Implementations:
    - TreeSitterParser: For languages with tree-sitter support
    - Language-specific parsers (NimParser, PlaintextParser, etc.): For custom parsing
    """
    
    def __init__(self):
        """Initialize the base parser."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
        
        # Initialize feature extractor according to parser type.
        from parsers.feature_extractor import TreeSitterFeatureExtractor, CustomFeatureExtractor
        if self.parser_type == ParserType.TREE_SITTER:
            self.feature_extractor = TreeSitterFeatureExtractor(self.language_id, self.file_type)
        elif self.parser_type == ParserType.CUSTOM:
            self.feature_extractor = CustomFeatureExtractor(self.language_id, self.file_type)
        else:
            self.feature_extractor = None

    async def initialize(self):
        """Initialize parser resources."""
        if not self._initialized:
            try:
                # Initialize cache coordinator
                future = submit_async_task(cache_coordinator.initialize())
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                # Initialize upsert coordinator
                future = submit_async_task(upsert_coordinator.initialize())
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                # Initialize feature extractor
                if self.feature_extractor:
                    future = submit_async_task(self.feature_extractor.initialize())
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                
                self._initialized = True
                log(f"Base parser initialized for {self.language_id}", level="info")
            except Exception as e:
                log(f"Error initializing base parser: {e}", level="error")
                raise

    def _create_node(self, node_type: str, start_point: List[int], end_point: List[int], **kwargs) -> Dict[str, Any]:
        """Helper for creating a standardized AST node. (Subclasses can override if needed.)"""
        return {
            "type": node_type,
            "start_point": start_point,
            "end_point": end_point,
            "children": [],
            **kwargs
        }

    def _compile_patterns(self, patterns_dict: dict) -> dict:
        """Helper to compile regex patterns from a definitions dictionary."""
        compiled = {}
        for category in patterns_dict.values():
            for name, pattern_obj in category.items():
                compiled[name] = re.compile(pattern_obj.pattern)
        return compiled
    
    def _get_syntax_errors(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get syntax errors from AST."""
        return []

    async def _check_ast_cache(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Check if an AST for this source code is already cached."""
        import hashlib
        
        # Create a unique cache key based on language and source code hash
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"ast:{self.language_id}:{source_hash}"
        
        with ErrorBoundary(f"check_ast_cache_{self.language_id}", error_types=(Exception,)):
            # Try to get from cache
            future = submit_async_task(cache_coordinator.get_async(cache_key))
            self._pending_tasks.add(future)
            try:
                cached_ast = await asyncio.wrap_future(future)
                if cached_ast:
                    log(f"AST cache hit for {self.language_id}", level="debug")
                    return cached_ast
            finally:
                self._pending_tasks.remove(future)
        
        return None
            
    async def _store_ast_in_cache(self, source_code: str, ast: Dict[str, Any]) -> None:
        """Store an AST in the cache."""
        import hashlib
        
        # Create a unique cache key based on language and source code hash
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"ast:{self.language_id}:{source_hash}"
        
        with ErrorBoundary(f"store_ast_in_cache_{self.language_id}", error_types=(Exception,)):
            # Store in cache asynchronously
            future = submit_async_task(cache_coordinator.set_async(cache_key, ast))
            self._pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
                log(f"AST cached for {self.language_id}", level="debug")
            finally:
                self._pending_tasks.remove(future)

    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """[2.2] Unified parsing pipeline."""
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary("parse_source", error_types=(Exception,)):
            # [2.2.1] Initialize Parser
            if not self._initialized and not await self.initialize():
                log(f"Failed to initialize {self.language_id} parser", level="error")
                return None

            # [2.2.2] Generate AST
            # First check if we have a cached AST
            cached_ast = await self._check_ast_cache(source_code)
            if cached_ast:
                ast = cached_ast
            else:
                # If not in cache, parse the source
                future = submit_async_task(self._parse_source(source_code))
                self._pending_tasks.add(future)
                try:
                    ast = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                if ast:
                    # Cache the AST for future use
                    await self._store_ast_in_cache(source_code, ast)
            
            if not ast:
                return None

            # [2.2.3] Extract Features
            # USES: [feature_extractor.py] FeatureExtractor.extract_features()
            future = submit_async_task(self.feature_extractor.extract_features(ast, source_code))
            self._pending_tasks.add(future)
            try:
                features = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)

            # [2.2.4] Get Syntax Errors
            errors = self._get_syntax_errors(ast)

            # RETURNS: [models.py] ParserResult
            return ParserResult(
                success=True,
                ast=ast,
                features=features.features,
                documentation=features.documentation.__dict__,
                complexity=features.metrics.__dict__,
                statistics=self.stats.__dict__,
                errors=errors
            )
        
        return None

    async def cleanup(self):
        """Clean up parser resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up feature extractor
            if self.feature_extractor:
                await self.feature_extractor.cleanup()
            
            self._initialized = False
            self.stats = ParsingStatistics()
            log(f"Base parser cleaned up for {self.language_id}", level="info")
        except Exception as e:
            log(f"Error cleaning up base parser: {e}", level="error")

    def _extract_category_features(
        self,
        category: FeatureCategory,
        ast: Dict[str, Any],
        source_code: str
    ) -> Dict[str, Any]:
        """Extract features for a specific category."""
        patterns = self.feature_extractor._patterns  # Or use a proper getter if needed.
        
        if category == FeatureCategory.SYNTAX:
            return self._extract_syntax_features(ast, patterns)
        elif category == FeatureCategory.SEMANTICS:
            return self._extract_semantic_features(ast, patterns)
        elif category == FeatureCategory.DOCUMENTATION:
            return self._extract_documentation_features(source_code, patterns)
        elif category == FeatureCategory.STRUCTURE:
            return self._extract_structure_features(ast, patterns)
        
        return {}

    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract patterns from source code for repository learning.
        
        This base implementation provides a general pattern extraction capability
        that custom parsers can override with more specific implementations.
        
        Args:
            source_code: The source code content to extract patterns from
            
        Returns:
            A list of extracted patterns with metadata
        """
        patterns = []
        
        with ErrorBoundary(f"extract_patterns_{self.language_id}", error_types=(Exception,)):
            # Parse the source first
            ast = self.parse(source_code)
            
            # Use the language-specific pattern processor if available
            from parsers.pattern_processor import pattern_processor
            if hasattr(pattern_processor, 'extract_repository_patterns'):
                language_patterns = pattern_processor.extract_repository_patterns(
                    file_path="",  # Not needed for pattern extraction
                    source_code=source_code,
                    language=self.language_id
                )
                patterns.extend(language_patterns)
                
            # Add file type specific patterns
            if self.file_type == FileType.CODE:
                # Add code-specific pattern extraction
                code_patterns = self._extract_code_patterns(ast, source_code)
                patterns.extend(code_patterns)
            elif self.file_type == FileType.DOCUMENTATION:
                # Add documentation-specific pattern extraction
                doc_patterns = self._extract_doc_patterns(ast, source_code)
                patterns.extend(doc_patterns)
        
        return patterns
        
    def _extract_code_patterns(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Extract code patterns from AST. Override in subclasses for language-specific behavior."""
        return []
        
    def _extract_doc_patterns(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Extract documentation patterns from AST. Override in subclasses for language-specific behavior."""
        return [] 