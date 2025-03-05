"""Base parser implementation."""

from abc import abstractmethod
from typing import Optional, Dict, Any, List, Union, Type, Callable, Set
from .types import FileType, FeatureCategory, ParserType, ParserResult, ParserConfig, ParsingStatistics
from dataclasses import field
import re
import asyncio
from parsers.types import PatternCategory
from parsers.models import PatternType, QueryPattern, BaseNodeDict
from utils.logger import log
from .parser_interfaces import BaseParserInterface
from utils.error_handling import AsyncErrorBoundary, ErrorSeverity
from utils.cache import cache_coordinator
from utils.shutdown import register_shutdown_handler
from db.transaction import transaction_scope
from db.upsert_ops import coordinator as upsert_coordinator
from utils.error_handling import ProcessingError
from utils.cache import UnifiedCache

class BaseParser(BaseParserInterface):
    """Base implementation for parsers.
    
    Implementations:
    - TreeSitterParser: For languages with tree-sitter support
    - Language-specific parsers (NimParser, PlaintextParser, etc.): For custom parsing
    """
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self.feature_extractor = None
        self._cache = None
        self._lock = asyncio.Lock()
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError(f"{self.language_id} parser not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls, language_id: str, file_type: FileType, parser_type: ParserType) -> 'BaseParser':
        """Async factory method to create and initialize a BaseParser instance."""
        instance = cls()
        instance.language_id = language_id
        instance.file_type = file_type
        instance.parser_type = parser_type
        
        try:
            async with AsyncErrorBoundary(f"{language_id} parser initialization"):
                # Initialize feature extractor according to parser type
                from parsers.feature_extractor import TreeSitterFeatureExtractor, CustomFeatureExtractor
                if parser_type == ParserType.TREE_SITTER:
                    instance.feature_extractor = TreeSitterFeatureExtractor(language_id, file_type)
                elif parser_type == ParserType.CUSTOM:
                    instance.feature_extractor = CustomFeatureExtractor(language_id, file_type)
                
                # Initialize cache coordinator
                task = asyncio.create_task(cache_coordinator.initialize())
                instance._pending_tasks.add(task)
                try:
                    await task
                finally:
                    instance._pending_tasks.remove(task)
                
                # Initialize upsert coordinator
                task = asyncio.create_task(upsert_coordinator.initialize())
                instance._pending_tasks.add(task)
                try:
                    await task
                finally:
                    instance._pending_tasks.remove(task)
                
                # Initialize feature extractor if present
                if instance.feature_extractor:
                    task = asyncio.create_task(instance.feature_extractor.initialize())
                    instance._pending_tasks.add(task)
                    try:
                        await task
                    finally:
                        instance._pending_tasks.remove(task)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                instance._initialized = True
                await log(f"Base parser initialized for {language_id}", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing base parser for {language_id}: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize base parser for {language_id}: {e}")
    
    async def cleanup(self):
        """Clean up parser resources."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up feature extractor
            if self.feature_extractor:
                await self.feature_extractor.cleanup()
            
            self._initialized = False
            self.stats = ParsingStatistics()
            await log(f"Base parser cleaned up for {self.language_id}", level="info")
        except Exception as e:
            await log(f"Error cleaning up base parser for {self.language_id}: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup base parser for {self.language_id}: {e}")

    def _create_node(self, node_type: str, start_point: List[int], end_point: List[int], **kwargs) -> BaseNodeDict:
        """Helper for creating a standardized AST node. (Subclasses can override if needed.)"""
        return {
            "type": node_type,
            "start_point": start_point,
            "end_point": end_point,
            "children": [],
            "metadata": {},
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

    async def _initialize_cache(self):
        """Initialize cache based on parser type."""
        if not self._cache:
            # Only initialize cache for custom parsers
            # Tree-sitter parsers use tree-sitter-language-pack's caching
            if self.parser_type == ParserType.CUSTOM:
                self._cache = UnifiedCache(f"parser_{self.language_id}")
                await cache_coordinator.register_cache(self._cache)
    
    async def _check_ast_cache(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Check if an AST for this source code is already cached."""
        # Only use caching for custom parsers
        if self.parser_type != ParserType.CUSTOM or not self._cache:
            return None
            
        import hashlib
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"ast:{self.language_id}:{source_hash}"
        
        async with AsyncErrorBoundary(f"check_ast_cache_{self.language_id}", error_types=(Exception,)):
            task = asyncio.create_task(self._cache.get(cache_key))
            self._pending_tasks.add(task)
            try:
                cached_ast = await task
                if cached_ast:
                    log(f"AST cache hit for {self.language_id}", level="debug")
                    return cached_ast
            finally:
                self._pending_tasks.remove(task)
        
        return None
            
    async def _store_ast_in_cache(self, source_code: str, ast: Dict[str, Any]) -> None:
        """Store an AST in the cache."""
        # Only cache for custom parsers
        if self.parser_type != ParserType.CUSTOM or not self._cache:
            return
            
        import hashlib
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"ast:{self.language_id}:{source_hash}"
        
        async with AsyncErrorBoundary(f"store_ast_in_cache_{self.language_id}", error_types=(Exception,)):
            task = asyncio.create_task(self._cache.set(cache_key, ast))
            self._pending_tasks.add(task)
            try:
                await task
                log(f"AST cached for {self.language_id}", level="debug")
            finally:
                self._pending_tasks.remove(task)

    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """[2.2] Unified parsing pipeline."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("parse_source", error_types=(Exception,)):
            # [2.2.1] Initialize Parser
            if not self._initialized and not await self.initialize():
                log(f"Failed to initialize {self.language_id} parser", level="error")
                return None

            # [2.2.2] Generate AST
            ast = None
            
            # For custom parsers, check cache first
            if self.parser_type == ParserType.CUSTOM:
                ast = await self._check_ast_cache(source_code)
            
            if not ast:
                # If not in cache or using tree-sitter, parse the source
                task = asyncio.create_task(self._parse_source(source_code))
                self._pending_tasks.add(task)
                try:
                    ast = await task
                finally:
                    self._pending_tasks.remove(task)
                
                # Cache AST for custom parsers
                if ast and self.parser_type == ParserType.CUSTOM:
                    await self._store_ast_in_cache(source_code, ast)
            
            if not ast:
                return None

            # [2.2.3] Extract Features
            task = asyncio.create_task(self.feature_extractor.extract_features(ast, source_code))
            self._pending_tasks.add(task)
            try:
                features = await task
            finally:
                self._pending_tasks.remove(task)

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
        
        with AsyncErrorBoundary(f"extract_patterns_{self.language_id}", error_types=(Exception,)):
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