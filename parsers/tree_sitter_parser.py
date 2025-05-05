"""Tree-sitter parser implementation.

This module provides the tree-sitter based parser implementation, integrating with
tree-sitter-language-pack for efficient parsing capabilities.

Core Utility Integration:
- Uses utils.shutdown to properly register cleanup handlers
- Uses utils.async_runner for long-running parsing operations
- Uses utils.cache.UnifiedCache for parser instance caching
- Uses utils.health_monitor for health reporting
- Properly initializes through parsers.initialize_parser_system

Resource Management:
- Parser instances are cached using UnifiedCache
- Cleanup handlers are registered to release resources on shutdown
- Long-running operations are handled by async_runner
"""

from typing import Dict, Optional, Set, List, Any, Union, TYPE_CHECKING, Tuple, Callable
import asyncio
import json
import time
import difflib
from datetime import datetime
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel,
    ParserResult, PatternValidationResult, QueryPattern
)
from parsers.models import FileClassification, BaseNodeDict
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary,
    handle_async_errors,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context, cached_in_request
from db.transaction import transaction_scope, get_transaction_coordinator
import importlib
import re
import os
import logging
import platform

if TYPE_CHECKING:
    from parsers.base_parser import BaseParser
    from parsers.feature_extractor import TreeSitterFeatureExtractor

class QueryPatternRegistry:
    """Registry for tree-sitter query patterns.
    
    This class manages query patterns for tree-sitter languages, providing
    versioning, caching, and utilities for pattern management.
    
    Attributes:
        language_id: Language identifier
        patterns: Dictionary of patterns by category
        pattern_versions: Version numbers for patterns
        pattern_metrics: Performance metrics for patterns
    """
    
    def __init__(self, language_id: str):
        """Initialize QueryPatternRegistry.
        
        Args:
            language_id: Language identifier
        """
        self.language_id = language_id
        self.patterns = {}
        self.pattern_versions = {}
        self.pattern_metrics = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._initialized = False
        
    async def initialize(self) -> bool:
        """Initialize the registry.
        
        This method loads patterns from the pattern storage system and
        registers the registry with the health monitoring system.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            # Register with health monitor
            from utils.health_monitor import register_component
            register_component(
                f"tree_sitter_query_registry_{self.language_id}",
                self._report_health
            )
            
            # Load patterns
            await self._load_patterns()
            
            self._initialized = True
            await log(f"Query pattern registry initialized for {self.language_id}", level="info")
            return True
            
        except Exception as e:
            await log(f"Error initializing query pattern registry: {e}", level="error")
            return False
    
    async def _report_health(self) -> Dict[str, Any]:
        """Report health metrics for the registry.
        
        Returns:
            Dict[str, Any]: Health metrics
        """
        return {
            'language_id': self.language_id,
            'initialized': self._initialized,
            'pattern_count': len(self.patterns),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'pattern_categories': list(self.patterns.keys())
        }
    
    async def _load_patterns(self) -> None:
        """Load patterns from all available sources.
        
        This method loads patterns from:
        1. Pattern storage system
        2. Language-specific pattern modules
        3. Default patterns
        """
        # First try to load from cache/storage
        await self._load_from_pattern_storage()
        
        # Then load language-specific patterns
        if not self.patterns:
            await self._load_language_patterns()
            
            # Register loaded patterns with pattern storage
            if self.patterns:
                await self._register_with_pattern_storage()
        
        # Fall back to defaults if needed
        if not self.patterns:
            await self._load_default_patterns()
    
    async def _load_from_pattern_storage(self) -> None:
        """Load patterns from the pattern storage system.
        
        This method checks for cached patterns in the pattern storage system
        and loads them if available.
        """
        try:
            from db.pattern_storage import get_tree_sitter_patterns
            
            # Try to get patterns from storage
            stored_patterns = await get_tree_sitter_patterns(self.language_id)
            
            if stored_patterns:
                self.patterns = stored_patterns
                self._cache_hits += 1
                await log(f"Loaded {len(stored_patterns)} patterns from storage for {self.language_id}", level="info")
            else:
                self._cache_misses += 1
                
        except ImportError:
            await log("Pattern storage module not available", level="warning")
        except Exception as e:
            await log(f"Error loading patterns from storage: {e}", level="warning")
    
    async def _load_language_patterns(self) -> None:
        """Load language-specific patterns from query modules.
        
        This method imports language-specific query pattern modules and
        extracts patterns from them.
        """
        try:
            # Try to import language-specific query patterns
            module_path = f"parsers.query_patterns.{self.language_id}"
            
            try:
                module = importlib.import_module(module_path)
                
                # Check if it has TS_QUERIES attribute
                if hasattr(module, "TS_QUERIES"):
                    self.patterns = module.TS_QUERIES
                    await log(f"Loaded patterns from {module_path}", level="info")
                    
            except (ImportError, AttributeError):
                await log(f"No specific patterns found for {self.language_id}", level="info")
                
        except Exception as e:
            await log(f"Error loading language patterns: {e}", level="warning")
    
    async def _load_default_patterns(self) -> None:
        """Load default patterns for the language.
        
        This method generates basic default patterns that should work
        for most languages.
        """
        try:
            # Generate default queries based on common syntax elements
            self.patterns = {
                'functions': """
                (function_definition name: (identifier) @function.name body: (block) @function.body) @function.def
                """,
                'classes': """
                (class_definition name: (identifier) @class.name body: (block) @class.body) @class.def
                """,
                'comments': """
                (comment) @comment
                """,
                'imports': """
                (import_statement module: (identifier) @import.module) @import
                """
            }
            
            await log(f"Using default patterns for {self.language_id}", level="info")
            
        except Exception as e:
            await log(f"Error loading default patterns: {e}", level="warning")
    
    async def _register_with_pattern_storage(self) -> None:
        """Register patterns with the pattern storage system.
        
        This method saves the loaded patterns to the pattern storage system
        for future use.
        """
        try:
            from db.pattern_storage import store_tree_sitter_patterns
            
            # Add metadata to patterns
            patterns_with_metadata = {}
            for category, pattern in self.patterns.items():
                patterns_with_metadata[category] = {
                    'query': pattern,
                    'metadata': {
                        'complexity': self._estimate_pattern_complexity(pattern),
                        'captures': self._extract_capture_names(pattern),
                        'version': 1,
                        'language': self.language_id
                    }
                }
            
            # Store patterns
            await store_tree_sitter_patterns(self.language_id, self.patterns)
            await log(f"Registered {len(self.patterns)} patterns with storage", level="info")
            
        except ImportError:
            await log("Pattern storage module not available", level="warning")
        except Exception as e:
            await log(f"Error registering patterns with storage: {e}", level="warning")
    
    def _estimate_pattern_complexity(self, pattern: str) -> int:
        """Estimate complexity of a query pattern.
        
        Args:
            pattern: Query pattern string
            
        Returns:
            int: Complexity score (higher means more complex)
        """
        # Simple heuristics for complexity
        complexity = len(pattern) * 0.1  # Length factor
        complexity += pattern.count('@') * 2  # Capture factor
        complexity += pattern.count('|') * 5  # Alternative factor
        complexity += pattern.count('*') * 3  # Wildcard factor
        complexity += pattern.count('?') * 2  # Optional factor
        complexity += pattern.count('(') * 0.5  # Grouping factor
        
        return int(complexity)
    
    def _extract_capture_names(self, pattern: str) -> List[str]:
        """Extract capture names from a query pattern.
        
        Args:
            pattern: Query pattern string
            
        Returns:
            List[str]: List of capture names
        """
        # Simple regex to extract capture names
        import re
        captures = re.findall(r'@([a-zA-Z0-9._]+)', pattern)
        return list(set(captures))  # Remove duplicates
    
    def get_pattern(self, category: str) -> Optional[str]:
        """Get a query pattern by category.
        
        Args:
            category: Pattern category
            
        Returns:
            Optional[str]: Query pattern or None if not found
        """
        return self.patterns.get(category)
    
    def get_all_patterns(self) -> Dict[str, str]:
        """Get all query patterns.
        
        Returns:
            Dict[str, str]: Dictionary of query patterns by category
        """
        return self.patterns
    
    def register_pattern(self, category: str, pattern: str) -> None:
        """Register a new query pattern.
        
        Args:
            category: Pattern category
            pattern: Query pattern string
        """
        self.patterns[category] = pattern
        self.pattern_versions[category] = self.pattern_versions.get(category, 0) + 1
    
    def invalidate_pattern(self, category: str) -> None:
        """Invalidate a pattern by category.
        
        Args:
            category: Pattern category to invalidate
        """
        if category in self.patterns:
            del self.patterns[category]
        if category in self.pattern_versions:
            del self.pattern_versions[category]
        if category in self.pattern_metrics:
            del self.pattern_metrics[category]

class TreeSitterParser(BaseParserInterface, AIParserInterface):
    """Parser implementation using tree-sitter for syntax parsing.
    
    This parser leverages the tree-sitter library to parse source code
    and provide rich syntax tree information.
    
    Attributes:
        language_id: Language identifier
        language: Tree-sitter language instance
        parser: Tree-sitter parser instance
    """
    
    def __init__(self, language_id: str):
        """Initialize tree-sitter parser.
        
        Args:
            language_id: Language identifier
        """
        super().__init__(language_id)
        self.parser_type = ParserType.TREE_SITTER
        self.language = None
        self.parser = None
        self.query_registry = None
        self._component_id = f"tree_sitter_parser_{language_id}"
        
        # Register with shutdown handler for proper cleanup
        from utils.shutdown import register_shutdown_handler
        register_shutdown_handler(self.cleanup)
    
    async def _initialize(self) -> bool:
        """Initialize tree-sitter parser components.
        
        This method initializes the tree-sitter parser, language, and
        query registry components.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            # Import tree-sitter and language-specific modules
            from tree_sitter import Parser
            
            # Convert language ID to format used by tree-sitter-languages
            normalized_language_id = self._normalize_language_id()
            
            # Get language
            await self._load_tree_sitter_language(normalized_language_id)
            if not self.language:
                return False
                
            # Create parser
            self.parser = Parser()
            self.parser.set_language(self.language)
            
            # Create query registry
            self.query_registry = QueryPatternRegistry(self.language_id)
            await self.query_registry.initialize()
            
            # Register with health monitor
            from utils.health_monitor import register_component
            register_component(self._component_id, self._report_health)
            
            # Register with error audit
            from utils.error_handling import register_error_boundary
            register_error_boundary(f"tree_sitter_{self.language_id}", self._handle_error)
            
            await log(f"Tree-sitter parser initialized for {self.language_id}", level="info")
            return True
            
        except ImportError as e:
            await log(f"Tree-sitter or language not available: {e}", level="error")
            return False
        except Exception as e:
            await log(f"Error initializing tree-sitter parser: {e}", level="error")
            return False
    
    async def _report_health(self) -> Dict[str, Any]:
        """Report health metrics for the parser.
        
        Returns:
            Dict[str, Any]: Health metrics
        """
        metrics = {
            'language_id': self.language_id,
            'initialized': self.language is not None and self.parser is not None,
            'query_registry_initialized': self.query_registry is not None and self.query_registry._initialized,
            'memory_usage': self._estimate_memory_usage()
        }
        
        # Add query registry metrics if available
        if self.query_registry:
            metrics['query_pattern_count'] = len(self.query_registry.patterns)
            metrics['query_cache_hits'] = self.query_registry._cache_hits
            metrics['query_cache_misses'] = self.query_registry._cache_misses
            
        return metrics
    
    async def _handle_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Handle errors in tree-sitter operations.
        
        Args:
            error: The exception
            context: Error context
        """
        # Log details about the error
        await log(f"Tree-sitter error ({self.language_id}): {error}", level="error")
        
        # Record error details for analysis
        from utils.error_handling import record_error
        await record_error(
            component=self._component_id,
            error_type=type(error).__name__,
            message=str(error),
            context=context
        )
    
    def _normalize_language_id(self) -> str:
        """Normalize language ID for tree-sitter-languages format.
        
        Returns:
            str: Normalized language ID
        """
        # Map common language IDs to tree-sitter format
        language_map = {
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'py': 'python',
            'rb': 'ruby',
            'go': 'go',
            'java': 'java',
            'c': 'c',
            'cpp': 'cpp',
            'cs': 'c_sharp',
            'php': 'php',
            'rust': 'rust',
            'scala': 'scala',
            'swift': 'swift',
            'kotlin': 'kotlin',
            'html': 'html',
            'css': 'css'
        }
        
        return language_map.get(self.language_id.lower(), self.language_id.lower())
    
    async def _load_tree_sitter_language(self, language_id: str) -> None:
        """Load tree-sitter language.
        
        Args:
            language_id: Normalized language ID
        """
        try:
            # Import tree-sitter-languages
            from tree_sitter_language_pack import get_language
            
            # Get language
            self.language = get_language(language_id)
            
            if not self.language:
                await log(f"Language {language_id} not supported by tree-sitter", level="warning")
                
        except ImportError as e:
            await log(f"tree-sitter-language-pack not available: {e}", level="error")
        except Exception as e:
            await log(f"Error loading tree-sitter language: {e}", level="error")
    
    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage of the parser components.
        
        Returns:
            int: Estimated memory usage in bytes
        """
        # Base memory usage
        memory = 1000  # Base object
        
        # Add parser and language memory
        if self.parser:
            memory += 10000  # Parser instance
            
        # Add query registry memory
        if self.query_registry:
            memory += 5000  # Base registry
            memory += sum(len(pattern) for pattern in self.query_registry.patterns.values())
            
        return memory
    
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse source code using tree-sitter with error recovery.
        
        Args:
            source_code: The source code to parse
            
        Returns:
            Dict[str, Any]: The parsed AST
            
        Raises:
            ProcessingError: If parsing fails
        """
        try:
            async with AsyncErrorBoundary(f"tree_sitter_parse_{self.language_id}"):
                # Parse with tree-sitter through async_runner
                parse_task = submit_async_task(self._parse_with_tree_sitter(source_code))
                tree = await asyncio.wrap_future(parse_task)
                
                if not tree or not tree.root_node:
                    raise ProcessingError("Tree-sitter parsing failed")
                
                # Convert to our AST format
                ast = self._convert_node(tree.root_node)
                
                return ast
                
        except Exception as e:
            await log(f"Initial parse failed, attempting recovery: {e}", level="warning")
            
            try:
                # Configure parser for error recovery if supported
                if hasattr(self.parser, 'set_timeout_micros'):
                    self.parser.set_timeout_micros(100000)  # Increase timeout for recovery
                
                # Try again with error recovery through async_runner
                recovery_task = submit_async_task(self._parse_with_tree_sitter(source_code))
                tree = await asyncio.wrap_future(recovery_task)
                
                if not tree or not tree.root_node:
                    raise ProcessingError("Recovery failed: no valid tree produced")
                
                # Log partial success
                await log(f"Recovered with potential parsing errors for {self.language_id}", level="info")
                
                # Track recovery metrics
                await global_health_monitor.increment_counter(
                    f"tree_sitter_parser.{self.language_id}.recovery_attempts.success"
                )
                
                # Convert and return
                ast = self._convert_node(tree.root_node)
                return ast
                
            except Exception as recovery_e:
                # Track failed recovery
                await global_health_monitor.increment_counter(
                    f"tree_sitter_parser.{self.language_id}.recovery_attempts.failure"
                )
                
                await log(f"Recovery failed: {recovery_e}", level="error")
                await ErrorAudit.record_error(
                    e,
                    f"tree_sitter_parse_{self.language_id}",
                    ProcessingError,
                    context={"source_size": len(source_code), "recovery_error": str(recovery_e)}
                )
                raise ProcessingError(f"Tree-sitter parsing failed: {e}, recovery failed: {recovery_e}")
    
    async def _parse_with_tree_sitter(self, source_code: str, old_tree=None) -> Any:
        """Parse source code with tree-sitter.
        
        This method parses the given source code using tree-sitter
        and returns the resulting syntax tree.
        
        Args:
            source_code: Source code to parse
            old_tree: Optional previous tree for incremental parsing
            
        Returns:
            Any: The tree-sitter syntax tree or None on failure
        """
        try:
            # Use async_runner for potentially long-running parsing operation
            from utils.async_runner import submit_async_task
            parse_task = submit_async_task(self._do_tree_sitter_parse(source_code, old_tree))
            return await asyncio.wrap_future(parse_task)
                
        except Exception as e:
            await log(f"Error parsing with tree-sitter: {e}", level="error")
            return None
    
    async def _do_tree_sitter_parse(self, source_code: str, old_tree=None) -> Any:
        """Perform the actual tree-sitter parsing operation.
        
        This is a helper method called by _parse_with_tree_sitter that does
        the actual parsing work.
        
        Args:
            source_code: Source code to parse
            old_tree: Optional previous tree for incremental parsing
            
        Returns:
            Any: The tree-sitter syntax tree or None on failure
        """
        if not self.parser or not self.language:
            await log("Parser or language not initialized", level="error")
            return None
            
        # Convert source code to bytes for tree-sitter
        source_bytes = source_code.encode('utf-8')
        
        # Parse source code
        try:
            if old_tree:
                # Incremental parsing
                tree = self.parser.parse(source_bytes, old_tree)
            else:
                # Full parsing
                tree = self.parser.parse(source_bytes)
                
            if tree:
                await log(f"Successfully parsed {self.language_id} code", level="debug")
                return tree
            else:
                await log("Parser returned None", level="warning")
                return None
                
        except Exception as e:
            await log(f"Exception in tree-sitter parsing: {e}", level="error")
            return None
    
    async def _track_edits(self, old_source: str, new_source: str) -> List[Dict[str, Any]]:
        """Calculate detailed edits between source versions.
        
        This method analyzes the differences between two versions of source code
        and returns the edit information in a format suitable for tree-sitter's
        incremental parsing.
        
        Args:
            old_source: The previous source code
            new_source: The new source code
            
        Returns:
            List of edits for tree-sitter
        """
        try:
            import difflib
            
            # Get changes using difflib
            matcher = difflib.SequenceMatcher(None, old_source, new_source)
            edits = []
            
            for op, old_start, old_end, new_start, new_end in matcher.get_opcodes():
                if op == 'replace' or op == 'delete' or op == 'insert':
                    # Calculate line/column positions for old_start
                    old_start_line = old_source.count('\n', 0, old_start)
                    if old_start_line > 0:
                        last_nl = old_source.rfind('\n', 0, old_start)
                        old_start_col = old_start - last_nl - 1
                    else:
                        old_start_col = old_start
                    
                    # Calculate line/column positions for old_end
                    old_end_line = old_source.count('\n', 0, old_end)
                    if old_end_line > 0:
                        last_nl = old_source.rfind('\n', 0, old_end)
                        old_end_col = old_end - last_nl - 1
                    else:
                        old_end_col = old_end
                    
                    # Calculate line/column positions for new_end
                    new_end_line = new_source.count('\n', 0, new_end)
                    if new_end_line > 0:
                        last_nl = new_source.rfind('\n', 0, new_end)
                        new_end_col = new_end - last_nl - 1
                    else:
                        new_end_col = new_end
                    
                    edits.append({
                        'start_byte': old_start,
                        'old_end_byte': old_end,
                        'new_end_byte': new_end,
                        'start_point': (old_start_line, old_start_col),
                        'old_end_point': (old_end_line, old_end_col),
                        'new_end_point': (new_end_line, new_end_col)
                    })
            
            return edits
            
        except Exception as e:
            await log(f"Error tracking edits: {e}", level="error")
            return []

    async def parse_incremental(self, source_code: str, old_tree=None, file_path: Optional[str] = None) -> ParserResult:
        """Parse source code with incremental parsing support.
        
        This enhanced method uses tree-sitter's incremental parsing capabilities to
        efficiently reparse only the changed portions of the source code.
        
        Args:
            source_code: The source code to parse
            old_tree: Optional previous tree for incremental parsing
            file_path: Optional file path for error reporting
            
        Returns:
            ParserResult: The parsing result
        """
        if not self.language:
            await self.ensure_initialized()
            if not self.language:
                return ParserResult(
                    success=False,
                    file_type=self.file_type,
                    parser_type=self.parser_type,
                    language=self.language_id,
                    errors=[str(e) for e in self._error_audit.errors]
                )
        
        start_time = time.time()
        
        try:
            async with AsyncErrorBoundary(f"incremental_parse_{self.language_id}"):
                # Store the old source if we have an old tree
                old_source = getattr(old_tree, '_source', None) if old_tree else None
                
                # If we have both old tree and old source, track edits and apply them
                if old_tree and old_source and hasattr(old_tree, 'edit'):
                    # Track edits between old and new source
                    edits = await self._track_edits(old_source, source_code)
                    
                    # Apply edits to the old tree
                    for edit in edits:
                        old_tree.edit(
                            start_byte=edit['start_byte'],
                            old_end_byte=edit['old_end_byte'],
                            new_end_byte=edit['new_end_byte'],
                            start_point=edit['start_point'],
                            old_end_point=edit['old_end_point'],
                            new_end_point=edit['new_end_point']
                        )
                
                # Parse with tree-sitter
                bytes_source = bytes(source_code, "utf8")
                tree = self.parser.parse(bytes_source, old_tree)
                
                # Store source with tree for future incremental parsing
                setattr(tree, '_source', source_code)
                
                if not tree or not tree.root_node:
                    raise ProcessingError(f"Incremental parsing failed for {file_path or 'unknown file'}")
                
                # Convert to our AST format
                ast = self._convert_node(tree.root_node)
                
                # Extract features
                features = await self._extract_features(ast, source_code)
                
                # Calculate parse time
                parse_time = time.time() - start_time
                
                # Get syntax errors if present
                syntax_errors = []
                if hasattr(tree.root_node, 'has_error') and tree.root_node.has_error:
                    # Find all ERROR nodes
                    error_nodes = self._find_error_nodes(tree.root_node)
                    for error_node in error_nodes:
                        syntax_errors.append({
                            'type': 'syntax_error',
                            'message': f"Syntax error at line {error_node.start_point[0] + 1}, column {error_node.start_point[1] + 1}",
                            'location': {
                                'start': error_node.start_point,
                                'end': error_node.end_point
                            }
                        })
                
                # Create result
                result = ParserResult(
                    success=True,
                    file_type=self.file_type,
                    parser_type=self.parser_type,
                    language=self.language_id,
                    ast=ast,
                    features=features.__dict__,
                    tree=tree,  # Store the raw tree for future incremental parsing
                    errors=syntax_errors,
                    parse_time=parse_time
                )
                
                # Update metrics
                self._metrics = self._metrics or {}
                self._metrics.setdefault("parse_times", []).append(parse_time)
                
                return result
                
        except Exception as e:
            await log(f"Error in incremental parsing: {e}", level="error")
            return ParserResult(
                success=False,
                file_type=self.file_type,
                parser_type=self.parser_type,
                language=self.language_id,
                errors=[str(e)]
            )

    def _find_error_nodes(self, node):
        """Find all error nodes in the tree."""
        error_nodes = []
        
        # Check if this node is an error node
        if node.type == 'ERROR':
            error_nodes.append(node)
        
        # Check children recursively
        for child in node.children:
            error_nodes.extend(self._find_error_nodes(child))
        
        return error_nodes
    
    def _convert_node(self, node: Any) -> Dict[str, Any]:
        """Convert a tree-sitter node to our AST format.
        
        Args:
            node: The tree-sitter node to convert
            
        Returns:
            Dict[str, Any]: The converted AST node
        """
        return self._create_node(
            node_type=node.type,
            start_point=list(node.start_point),
            end_point=list(node.end_point),
            children=[self._convert_node(child) for child in node.children],
            metadata={
                "named": node.is_named,
                "error": node.has_error,
                "missing": node.is_missing
            }
        )
    
    def traverse_with_cursor(self, tree) -> List[Dict[str, Any]]:
        """Efficiently traverse a syntax tree using tree-sitter's cursor API.
        
        This method provides a more efficient way to traverse the entire syntax
        tree compared to recursive traversal. It uses tree-sitter's cursor API
        which does not rely on recursive function calls.
        
        Args:
            tree: The tree-sitter tree to traverse
            
        Returns:
            List of converted nodes
        """
        try:
            nodes = []
            
            # Create a tree cursor from the root node
            cursor = tree.root_node.walk()
            
            # First traversal: gather all nodes
            reached_root = False
            while not reached_root:
                # Convert current node
                current_node = cursor.node
                
                # Add to results
                nodes.append(self._convert_node(current_node))
                
                # Try to move to the first child
                if cursor.goto_first_child():
                    continue
                    
                # If no children, try to move to the next sibling
                if cursor.goto_next_sibling():
                    continue
                    
                # If no next sibling, try to move to the parent and then next sibling
                reached_parent = False
                while not reached_parent:
                    # Go to parent
                    reached_parent = cursor.goto_parent()
                    
                    # If we reached the root, we're done
                    if reached_parent and cursor.node == tree.root_node:
                        reached_root = True
                        break
                        
                    # Try to go to next sibling
                    if reached_parent and cursor.goto_next_sibling():
                        break
                        
            return nodes
            
        except Exception as e:
            # Return what we have so far or empty list
            return nodes or []
    
    async def _validate_ast(self, ast: Dict[str, Any]) -> List[str]:
        """Validate AST structure.
        
        Args:
            ast: The AST to validate
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        # Check for basic structure
        if not ast or not isinstance(ast, dict):
            errors.append("Invalid AST structure")
            return errors
        
        # Check required fields
        required_fields = ["type", "start_point", "end_point", "children"]
        for field in required_fields:
            if field not in ast:
                errors.append(f"Missing required field: {field}")
        
        # Check for parsing errors
        if ast.get("metadata", {}).get("error"):
            errors.append(f"Node {ast['type']} has parsing errors")
        
        # Recursively validate children
        for child in ast.get("children", []):
            child_errors = await self._validate_ast(child)
            errors.extend(child_errors)
        
        return errors
    
    async def _extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features from AST using tree-sitter capabilities.
        
        Args:
            ast: The AST to extract features from
            source_code: The original source code
            
        Returns:
            ExtractedFeatures: The extracted features
        """
        features = await super()._extract_features(ast, source_code)
        
        # Add tree-sitter specific features
        if self.language and self.binding:
            try:
                # Extract additional features through tree-sitter queries
                query_task = submit_async_task(self._extract_tree_sitter_features(ast))
                ts_features = await asyncio.wrap_future(query_task)
                features.update(ts_features)
            except Exception as e:
                await log(f"Error extracting tree-sitter features: {e}", level="warning")
        
        return features
    
    async def _extract_tree_sitter_features(self, tree: Any) -> Dict[str, Any]:
        """Extract features using tree-sitter specific capabilities.
        
        This method extracts features from a tree-sitter syntax tree using native
        tree-sitter capabilities such as queries, cursors, and node relationships.
        
        Args:
            tree: The tree-sitter tree to extract features from
            
        Returns:
            Dict with extracted features
        """
        features = {}
        
        try:
            # Check if query registry is available
            if not self.query_registry:
                await log(f"Query registry not available for {self.language_id}", level="warning")
                return features
                
            # Get all registered patterns from the query registry
            registered_patterns = self.query_registry.get_all_patterns()
            if not registered_patterns:
                await log(f"No registered patterns for {self.language_id}", level="warning")
                
                # Fall back to legacy approach
                query_patterns = await self._get_language_queries()
                
                # Execute each query to extract features
                for category, query_string in query_patterns.items():
                    try:
                        results = await self._execute_optimized_query(
                            query_string,
                            tree,
                            match_limit=1000,
                            timeout_micros=50000
                        )
                        feature_data = self._process_query_results(results, category)
                        
                        if feature_data:
                            features[category] = feature_data
                            
                    except Exception as e:
                        await log(f"Error extracting {category} features: {e}", level="warning")
            else:
                # Group patterns by category for organized results
                patterns_by_category = {}
                for pattern_name, pattern in registered_patterns.items():
                    category = str(pattern.category)
                    if category not in patterns_by_category:
                        patterns_by_category[category] = []
                    patterns_by_category[category].append(pattern)
                
                await log(f"Processing {len(registered_patterns)} patterns in {len(patterns_by_category)} categories", level="debug")
                
                # Execute queries for each category
                for category, patterns in patterns_by_category.items():
                    category_features = {
                        'count': 0,
                        'patterns': {}
                    }
                    
                    for pattern in patterns:
                        try:
                            # Get compiled query from registry
                            compiled_query = self.query_registry.get_compiled_query(pattern.name)
                            if not compiled_query:
                                continue
                                
                            # For complex patterns, use matches
                            if pattern.pattern.count('@') > 10 or pattern.pattern.count('(') > 20:
                                # First analyze the query
                                analysis = self.analyze_query(pattern.pattern)
                                
                                # Use appropriate method based on analysis
                                if any(opt.get('issue') == 'non_local_pattern' for opt in analysis['optimizations']):
                                    matches = compiled_query.matches(tree.root_node)
                                    
                                    # Process matches
                                    if matches:
                                        match_results = []
                                        for pattern_index, captures in matches:
                                            match_data = {
                                                'pattern_index': pattern_index,
                                                'captures': {}
                                            }
                                            
                                            for name, node in captures.items():
                                                node_text = node.text.decode('utf8') if len(node.text) < 100 else f"{node.text[:97].decode('utf8')}..."
                                                match_data['captures'][name] = {
                                                    'text': node_text,
                                                    'start_point': node.start_point,
                                                    'end_point': node.end_point,
                                                    'type': node.type
                                                }
                                                
                                            match_results.append(match_data)
                                            
                                        if match_results:
                                            category_features['patterns'][pattern.name] = {
                                                'count': len(match_results),
                                                'matches': match_results[:50],  # Limit to 50 matches for memory
                                                'confidence': pattern.confidence
                                            }
                                            category_features['count'] += len(match_results)
                                else:
                                    # Use captures for simpler patterns
                                    captures = compiled_query.captures(tree.root_node)
                                    
                                    # Process captures
                                    if captures:
                                        results_by_name = {}
                                        for node, capture_name in captures:
                                            if capture_name not in results_by_name:
                                                results_by_name[capture_name] = []
                                                
                                            node_text = node.text.decode('utf8') if len(node.text) < 100 else f"{node.text[:97].decode('utf8')}..."
                                            results_by_name[capture_name].append({
                                                'text': node_text,
                                                'start_point': node.start_point,
                                                'end_point': node.end_point,
                                                'type': node.type
                                            })
                                            
                                        if results_by_name:
                                            capture_count = sum(len(items) for items in results_by_name.values())
                                            category_features['patterns'][pattern.name] = {
                                                'count': capture_count,
                                                'captures': results_by_name,
                                                'confidence': pattern.confidence
                                            }
                                            category_features['count'] += capture_count
                                            
                        except Exception as e:
                            await log(f"Error executing pattern {pattern.name}: {e}", level="warning")
                            continue
                    
                    # Add category features if we found any
                    if category_features['count'] > 0:
                        features[category] = category_features
            
            # Extract structural features using cursor-based traversal
            features['structure'] = self._extract_structural_features(tree.root_node)
            
            # Extract syntax error information
            features['errors'] = self._extract_error_information(tree.root_node)
            
            # Extract node type distribution
            features['node_types'] = self._count_node_types(tree.root_node)
            
            # Add overall tree statistics
            features['statistics'] = {
                'node_count': self._count_nodes(tree.root_node),
                'max_depth': self._calculate_max_depth(tree.root_node),
                'error_count': len(features.get('errors', [])),
                'tree_size_bytes': self._estimate_tree_size(tree)
            }
            
            # If we have a query registry, add registry statistics
            if self.query_registry:
                features['registry_stats'] = self.query_registry.get_statistics()
            
            return features
            
        except Exception as e:
            await log(f"Error in tree-sitter feature extraction: {e}", level="error")
            return {
                'error': str(e),
                'statistics': {
                    'node_count': 0,
                    'max_depth': 0,
                    'error_count': 0
                }
            }
    
    async def _get_language_queries(self) -> Dict[str, str]:
        """Get language-specific query patterns.
        
        Returns:
            Dict[str, str]: Dictionary of query categories and query strings
        """
        if not self.query_registry:
            # Create and initialize registry if not already done
            self.query_registry = QueryPatternRegistry(self.language_id)
            await self.query_registry.initialize()
        
        return self.query_registry.get_all_patterns()
    
    def _process_query_results(self, results: Dict[str, List[Dict[str, Any]]], category: str) -> Dict[str, Any]:
        """Process raw query results into structured feature data.
        
        This method transforms raw tree-sitter query results into a more
        user-friendly format based on the category of features being extracted.
        
        Args:
            results: Raw query results from _execute_query
            category: Category of features (functions, classes, etc.)
            
        Returns:
            Dict[str, Any]: Processed feature data
        """
        processed = {}
        
        try:
            if category == 'functions':
                # Process function definitions
                functions = []
                for node in results.get('function.def', []):
                    function = {
                        'name': self._get_node_text(results.get('function.name', []), node['id']),
                        'parameters': self._get_node_text(results.get('function.parameters', []), node['id']),
                        'body': node.get('text', ''),
                        'start_line': node.get('start_row', 0),
                        'end_line': node.get('end_row', 0)
                    }
                    functions.append(function)
                processed['items'] = functions
                
            elif category == 'classes':
                # Process class definitions
                classes = []
                for node in results.get('class.def', []):
                    class_info = {
                        'name': self._get_node_text(results.get('class.name', []), node['id']),
                        'body': node.get('text', ''),
                        'start_line': node.get('start_row', 0),
                        'end_line': node.get('end_row', 0),
                        'methods': self._count_child_nodes(node, 'method.def')
                    }
                    classes.append(class_info)
                processed['items'] = classes
                
            elif category == 'imports':
                # Process import statements
                imports = []
                for node in results.get('import', []):
                    import_info = {
                        'module': self._get_node_text(results.get('import.module', []), node['id']),
                        'line': node.get('start_row', 0)
                    }
                    imports.append(import_info)
                processed['items'] = imports
                
            else:
                # For other categories, just organize by capture name
                for capture_name, nodes in results.items():
                    processed[capture_name] = nodes
                    
        except Exception as e:
            pass  # Silently handle processing errors
            
        return processed
    
    def _get_node_text(self, nodes: List[Dict[str, Any]], parent_id: str) -> str:
        """Get text from a node that belongs to a specific parent.
        
        Args:
            nodes: List of node dictionaries
            parent_id: Parent node ID to match
            
        Returns:
            str: Node text or empty string
        """
        for node in nodes:
            if node.get('parent_id') == parent_id and 'text' in node:
                return node['text']
        return ''
    
    def _count_child_nodes(self, parent_node: Dict[str, Any], child_type: str) -> int:
        """Count children of a specific type within a node.
        
        This method is used for gathering metrics about child nodes.
        
        Args:
            parent_node: Parent node dictionary
            child_type: Type of child node to count
            
        Returns:
            int: Count of matching child nodes
        """
        # This is a simplified implementation - in a real parser, we would
        # traverse the actual node structure, but here we can only approximate
        return 0  # Placeholder
    
    def _extract_structural_features(self, node: Any) -> Dict[str, Any]:
        """Extract structural features from a tree-sitter node.
        
        This method analyzes the structure of the syntax tree, identifying
        patterns like nesting levels, call chains, and code organization.
        
        Args:
            node: The tree-sitter node to analyze
            
        Returns:
            Dict[str, Any]: Dictionary of structural features
        """
        features = {
            'nesting_depth': 0,
            'statement_count': 0,
            'expression_count': 0,
            'control_flow': {
                'if_chains': 0,
                'switch_cases': 0,
                'loops': 0
            },
            'node_distribution': {}
        }
        
        try:
            # Extract nesting depth
            features['nesting_depth'] = self._calculate_max_depth(node)
            
            # Count statements and expressions
            features['statement_count'] = self._count_nodes_by_suffix(node, '_statement')
            features['expression_count'] = self._count_nodes_by_suffix(node, '_expression')
            
            # Analyze control flow
            features['control_flow']['if_chains'] = self._count_if_chains(node)
            features['control_flow']['switch_cases'] = self._count_switch_cases(node)
            features['control_flow']['loops'] = self._count_loops(node)
            
            # Get node type distribution
            features['node_distribution'] = self._count_node_types(node)
            
        except Exception as e:
            pass  # Silently handle analysis errors
            
        return features
    
    async def _extract_error_information(self, node: Any) -> List[Dict[str, Any]]:
        """Extract error information from a tree-sitter node.
        
        This method identifies syntax errors and other issues in the parse tree.
        
        Args:
            node: The tree-sitter node to analyze
            
        Returns:
            List[Dict[str, Any]]: List of error information dictionaries
        """
        errors = []
        
        try:
            # Look for ERROR nodes in the tree
            error_nodes = self._find_nodes_by_type(node, ['ERROR'])
            
            for error_node in error_nodes:
                errors.append({
                    'type': 'syntax_error',
                    'message': 'Syntax error detected by tree-sitter',
                    'start_row': error_node.start_point[0],
                    'start_column': error_node.start_point[1],
                    'end_row': error_node.end_point[0],
                    'end_column': error_node.end_point[1]
                })
                
            # Look for MISSING nodes
            missing_nodes = self._find_nodes_by_type(node, ['MISSING'])
            
            for missing_node in missing_nodes:
                errors.append({
                    'type': 'missing_node',
                    'message': f'Missing {missing_node.type}',
                    'start_row': missing_node.start_point[0],
                    'start_column': missing_node.start_point[1],
                    'end_row': missing_node.end_point[0],
                    'end_column': missing_node.end_point[1]
                })
                
        except Exception as e:
            pass  # Silently handle analysis errors
            
        return errors
    
    def _count_nodes(self, node: Any) -> int:
        """Count all nodes in a tree.
        
        Args:
            node: The tree-sitter node to count
            
        Returns:
            int: Total number of nodes in the tree
        """
        count = 1  # Count the current node
        
        try:
            for child in node.children:
                count += self._count_nodes(child)
        except Exception:
            pass
            
        return count
    
    def _count_node_types(self, node: Any) -> Dict[str, int]:
        """Count nodes by type in a tree.
        
        Args:
            node: The tree-sitter node to analyze
            
        Returns:
            Dict[str, int]: Dictionary of node types and counts
        """
        counts = {}
        
        try:
            # Add current node
            if node.type not in counts:
                counts[node.type] = 0
            counts[node.type] += 1
            
            # Process children recursively
            for child in node.children:
                child_counts = self._count_node_types(child)
                for node_type, count in child_counts.items():
                    if node_type not in counts:
                        counts[node_type] = 0
                    counts[node_type] += count
                    
        except Exception:
            pass
            
        return counts
    
    def _count_nodes_by_suffix(self, node: Any, suffix: str) -> int:
        """Count nodes whose type ends with a specific suffix.
        
        Args:
            node: The tree-sitter node to analyze
            suffix: Type suffix to match
            
        Returns:
            int: Count of matching nodes
        """
        count = 0
        
        try:
            # Check current node
            if node.type.endswith(suffix):
                count += 1
                
            # Process children recursively
            for child in node.children:
                count += self._count_nodes_by_suffix(child, suffix)
                
        except Exception:
            pass
            
        return count
    
    def _count_if_chains(self, node: Any) -> int:
        """Count if-else if-else chains in the tree.
        
        Args:
            node: The tree-sitter node to analyze
            
        Returns:
            int: Number of if chains
        """
        # Simplified implementation - would need language-specific logic
        return self._count_nodes_by_suffix(node, 'if_statement')
    
    def _count_switch_cases(self, node: Any) -> int:
        """Count switch cases in the tree.
        
        Args:
            node: The tree-sitter node to analyze
            
        Returns:
            int: Number of switch cases
        """
        # Simplified implementation - would need language-specific logic
        return self._count_nodes_by_suffix(node, 'switch_statement')
    
    def _count_loops(self, node: Any) -> int:
        """Count loops in the tree.
        
        Args:
            node: The tree-sitter node to analyze
            
        Returns:
            int: Number of loops
        """
        # Count all loop types
        return (
            self._count_nodes_by_suffix(node, 'for_statement') +
            self._count_nodes_by_suffix(node, 'while_statement') +
            self._count_nodes_by_suffix(node, 'do_statement')
        )
    
    def _calculate_max_depth(self, node: Any) -> int:
        """Calculate the maximum depth of a tree.
        
        Args:
            node: The tree-sitter node to analyze
            
        Returns:
            int: Maximum depth of the tree
        """
        if not node.children:
            return 1
            
        max_child_depth = 0
        for child in node.children:
            child_depth = self._calculate_max_depth(child)
            max_child_depth = max(max_child_depth, child_depth)
            
        return 1 + max_child_depth
    
    def _find_nodes_by_type(self, node: Any, node_types: List[str]) -> List[Any]:
        """Find all nodes of specified types in the tree.
        
        Args:
            node: The tree-sitter node to search
            node_types: List of node types to find
            
        Returns:
            List[Any]: List of matching nodes
        """
        found_nodes = []
        
        if node.type in node_types:
            found_nodes.append(node)
            
        for child in node.children:
            found_nodes.extend(self._find_nodes_by_type(child, node_types))
            
        return found_nodes
    
    def _convert_node(self, node: Any) -> Dict[str, Any]:
        """Convert a tree-sitter node to a dictionary representation.
        
        Args:
            node: The tree-sitter node to convert
            
        Returns:
            Dict[str, Any]: Dictionary representation of the node
        """
        return {
            'id': f"{node.id}",
            'parent_id': f"{node.parent.id}" if node.parent else None,
            'type': node.type,
            'start_row': node.start_point[0],
            'start_column': node.start_point[1],
            'end_row': node.end_point[0],
            'end_column': node.end_point[1],
            'text': node.text.decode('utf-8') if hasattr(node, 'text') else ''
        }
    
    def _parse_with_tree_sitter(self, source_code: str) -> Any:
        """Parse source code with tree-sitter.
        
        Args:
            source_code: Source code to parse
            
        Returns:
            Any: The parsed tree
        """
        try:
            if not self.parser:
                # Use sync logging instead of await
                logging.error("Tree-sitter parser not initialized")
                return None
                
            # Parse the source code
            tree = self.parser.parse(bytes(source_code, 'utf-8'))
            return tree
            
        except Exception as e:
            # Use sync logging instead of await
            logging.error(f"Error parsing with tree-sitter: {e}")
            return None
    
    def _estimate_tree_size(self, tree: Any) -> int:
        """Estimate the memory size of a tree.
        
        Args:
            tree: The tree-sitter tree
            
        Returns:
            int: Estimated size in bytes
        """
        # Simplified implementation - would need more accurate calculation
        return self._count_nodes(tree.root_node) * 32  # Rough estimate
    
    async def get_node_relationships(self, node: Any) -> Dict[str, Any]:
        """Get relationships for a node (parent, siblings, children).
        
        Args:
            node: The tree-sitter node
            
        Returns:
            Dict[str, Any]: Dictionary of node relationships
        """
        relationships = {
            'parent': None,
            'siblings': [],
            'children': []
        }
        
        try:
            # Get parent
            if node.parent:
                relationships['parent'] = self._convert_node(node.parent)
                
            # Get siblings (exclude self)
            if node.parent:
                for sibling in node.parent.children:
                    if sibling.id != node.id:
                        relationships['siblings'].append(self._convert_node(sibling))
                        
            # Get children
            for child in node.children:
                relationships['children'].append(self._convert_node(child))
                
        except Exception as e:
            await log(f"Error getting node relationships: {e}", level="warning")
            
        return relationships

    def analyze_query(self, query_string: str) -> Dict[str, Any]:
        """Analyze a tree-sitter query for optimization insights.
        
        This method provides detailed analysis of a query, including information
        about pattern structure, predicate usage, and optimization opportunities.
        
        Args:
            query_string: The query string in tree-sitter query language
            
        Returns:
            Dict with detailed query analysis
        """
        try:
            query = self.language.query(query_string)
            
            analysis = {
                'pattern_count': query.pattern_count,
                'capture_count': query.capture_count,
                'patterns': [],
                'optimizations': []
            }
            
            # Analyze each pattern in the query
            for i in range(query.pattern_count):
                pattern_analysis = {
                    'index': i,
                    'is_rooted': query.is_pattern_rooted(i),
                    'is_non_local': query.is_pattern_non_local(i),
                    'start_byte': query.start_byte_for_pattern(i),
                    'end_byte': query.end_byte_for_pattern(i)
                }
                
                # Get pattern assertions (#is? predicates)
                if hasattr(query, 'pattern_assertions'):
                    pattern_analysis['assertions'] = query.pattern_assertions(i)
                
                # Get pattern settings (#set! predicates)
                if hasattr(query, 'pattern_settings'):
                    pattern_analysis['settings'] = query.pattern_settings(i)
                
                analysis['patterns'].append(pattern_analysis)
                
                # Add optimization recommendations
                if not pattern_analysis['is_rooted']:
                    analysis['optimizations'].append({
                        'pattern_index': i,
                        'issue': 'non_rooted_pattern',
                        'recommendation': 'Make pattern more specific by adding a definite root node',
                        'impact': 'This may cause slower query execution as the engine needs to search more broadly'
                    })
                    
                if pattern_analysis['is_non_local']:
                    analysis['optimizations'].append({
                        'pattern_index': i,
                        'issue': 'non_local_pattern',
                        'recommendation': 'Rewrite pattern to have all captures under a common ancestor',
                        'impact': 'Non-local patterns disable certain optimizations in the query engine'
                    })
            
            # Analyze query complexity
            if query.pattern_count > 20:
                analysis['optimizations'].append({
                    'issue': 'high_pattern_count',
                    'recommendation': 'Split large queries into smaller targeted queries',
                    'impact': 'Large queries can be slow to execute and may hit match limits'
                })
                
            if query.capture_count > 50:
                analysis['optimizations'].append({
                    'issue': 'high_capture_count',
                    'recommendation': 'Reduce number of capture names in query',
                    'impact': 'Too many captures can slow down query execution and increase memory usage'
                })
            
            return analysis
            
        except Exception as e:
            return {
                'error': str(e),
                'pattern_count': 0,
                'capture_count': 0,
                'patterns': [],
                'optimizations': [{
                    'issue': 'query_error',
                    'recommendation': f'Fix query syntax error: {str(e)}',
                    'impact': 'Query cannot be executed until this is fixed'
                }]
            }

    async def export_query_patterns(self, format_type: str = "dict") -> Union[Dict[str, Any], str]:
        """Export query patterns in a specified format.
        
        This method exports all registered query patterns in the specified format,
        which is useful for sharing patterns between languages, debugging, and
        creating pattern libraries.
        
        Args:
            format_type: The output format, one of "dict", "json", "python"
            
        Returns:
            Dictionary or formatted string with patterns
        """
        if not self.query_registry:
            await log(f"Query registry not available for {self.language_id}", level="warning")
            return {} if format_type == "dict" else ""
        
        patterns = self.query_registry.get_all_patterns()
        if not patterns:
            await log(f"No patterns available for {self.language_id}", level="warning")
            return {} if format_type == "dict" else ""
        
        # Create dictionary form first
        result_dict = {}
        for name, pattern in patterns.items():
            result_dict[name] = {
                "pattern": pattern.pattern,
                "category": str(pattern.category),
                "purpose": str(pattern.purpose),
                "confidence": pattern.confidence
            }
        
        # Return requested format
        if format_type == "dict":
            return result_dict
        elif format_type == "json":
            import json
            return json.dumps(result_dict, indent=2)
        elif format_type == "python":
            # Format as a Python module
            python_code = f"""# Tree-sitter queries for {self.language_id}
# Generated by RepoAnalyzer {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

TS_QUERIES = {{
"""
            for name, data in result_dict.items():
                # Format the query string with proper indentation
                query_lines = data["pattern"].split("\n")
                indented_query = "\n        ".join(query_lines)
                python_code += f"""    '{name}': \"\"\"        {indented_query}
        \"\"\",
        
"""
            python_code += "}\n"
            return python_code
        else:
            raise ValueError(f"Unknown format type: {format_type}")
    
    async def test_query(self, query_string: str, source_code: str) -> Dict[str, Any]:
        """Test a tree-sitter query against source code.
        
        This interactive method allows testing of tree-sitter queries against
        source code, providing immediate feedback on query results.
        
        Args:
            query_string: The tree-sitter query string to test
            source_code: The source code to test against
            
        Returns:
            Dict with query results and performance metrics
        """
        if not self.language:
            await self.ensure_initialized()
            if not self.language:
                return {"error": "Language not initialized"}
        
        try:
            # Parse source code
            bytes_source = bytes(source_code, "utf8")
            tree = self.parser.parse(bytes_source)
            
            # Validate query syntax
            try:
                query = self.language.query(query_string)
            except Exception as e:
                return {
                    "error": f"Invalid query syntax: {e}",
                    "source_size": len(source_code),
                    "tree_nodes": tree.root_node.child_count if tree and tree.root_node else 0
                }
            
            # Analyze query
            analysis = self.analyze_query(query_string)
            
            # Performance testing
            perf_metrics = await self._monitor_query_performance(query_string, tree)
            
            # Execute query with both methods
            captures_start = time.time()
            try:
                captures = query.captures(tree.root_node)
                captures_time = time.time() - captures_start
                captures_count = len(captures)
                
                # Organize captures by name
                captures_by_name = {}
                for node, capture_name in captures:
                    if capture_name not in captures_by_name:
                        captures_by_name[capture_name] = []
                    
                    # Limit node text size
                    node_text = node.text.decode('utf8') if len(node.text) < 100 else f"{node.text[:97].decode('utf8')}..."
                    
                    captures_by_name[capture_name].append({
                        'text': node_text,
                        'start_point': node.start_point,
                        'end_point': node.end_point,
                        'type': node.type
                    })
            except Exception as e:
                captures_time = time.time() - captures_start
                captures_count = 0
                captures_by_name = {"error": str(e)}
            
            # Try matches method
            matches_start = time.time()
            try:
                matches = query.matches(tree.root_node)
                matches_time = time.time() - matches_start
                matches_count = len(matches)
                
                # Process first 50 matches
                matches_data = []
                for idx, (pattern_index, capture_dict) in enumerate(matches[:50]):
                    match_data = {
                        'pattern_index': pattern_index,
                        'captures': {}
                    }
                    
                    for name, node in capture_dict.items():
                        # Limit node text size
                        node_text = node.text.decode('utf8') if len(node.text) < 100 else f"{node.text[:97].decode('utf8')}..."
                        
                        match_data['captures'][name] = {
                            'text': node_text,
                            'start_point': node.start_point,
                            'end_point': node.end_point,
                            'type': node.type
                        }
                        
                    matches_data.append(match_data)
            except Exception as e:
                matches_time = time.time() - matches_start
                matches_count = 0
                matches_data = [{"error": str(e)}]
            
            # Return combined results
            return {
                "analysis": analysis,
                "performance": perf_metrics,
                "source_size": len(source_code),
                "tree_nodes": tree.root_node.child_count if tree and tree.root_node else 0,
                "captures": {
                    "time_ms": captures_time * 1000,
                    "count": captures_count,
                    "by_name": captures_by_name
                },
                "matches": {
                    "time_ms": matches_time * 1000,
                    "count": matches_count,
                    "data": matches_data
                }
            }
            
        except Exception as e:
            await log(f"Error testing query: {e}", level="error")
            return {
                "error": str(e),
                "source_size": len(source_code)
            }

    async def register_query_patterns(
        self, 
        patterns: Dict[str, Union[str, Dict[str, Any]]], 
        source: str = "external", 
        category: Optional[PatternCategory] = None,
        purpose: Optional[PatternPurpose] = None,
        confidence: float = 0.7
    ) -> Dict[str, bool]:
        """Register query patterns from external sources.
        
        This method allows registering query patterns from external sources,
        such as user-defined patterns, plugins, or other systems.
        
        Args:
            patterns: Dictionary mapping pattern names to query strings or pattern details
            source: The source identifier for the patterns
            category: Default category for patterns that don't specify one
            purpose: Default purpose for patterns that don't specify one
            confidence: Default confidence for patterns that don't specify one
            
        Returns:
            Dict mapping pattern names to registration success
        """
        if not self.query_registry:
            await log(f"Query registry not available for {self.language_id}", level="warning")
            return {name: False for name in patterns}
        
        results = {}
        
        for name, pattern_data in patterns.items():
            try:
                # Full name with source prefix
                full_name = f"{source}_{name}"
                
                # Handle string or dict pattern data
                if isinstance(pattern_data, str):
                    query_string = pattern_data
                    pattern_category = category or PatternCategory.SYNTAX
                    pattern_purpose = purpose or PatternPurpose.UNDERSTANDING
                    pattern_confidence = confidence
                else:
                    query_string = pattern_data.get("pattern", "")
                    if not query_string:
                        results[name] = False
                        await log(f"Missing pattern string for {name}", level="warning")
                        continue
                        
                    # Get or use defaults for optional data
                    pattern_category = pattern_data.get("category", category or PatternCategory.SYNTAX)
                    if isinstance(pattern_category, str):
                        try:
                            pattern_category = PatternCategory(pattern_category)
                        except ValueError:
                            pattern_category = PatternCategory.SYNTAX
                            
                    pattern_purpose = pattern_data.get("purpose", purpose or PatternPurpose.UNDERSTANDING)
                    if isinstance(pattern_purpose, str):
                        try:
                            pattern_purpose = PatternPurpose(pattern_purpose)
                        except ValueError:
                            pattern_purpose = PatternPurpose.UNDERSTANDING
                            
                    pattern_confidence = pattern_data.get("confidence", confidence)
                
                # Create query pattern
                query_pattern = QueryPattern(
                    name=full_name,
                    pattern=query_string,
                    category=pattern_category,
                    purpose=pattern_purpose,
                    language_id=self.language_id,
                    confidence=pattern_confidence
                )
                
                # Register pattern
                success = self.query_registry.register_pattern(query_pattern)
                results[name] = success
                
                if success:
                    await log(f"Registered pattern {full_name} for {self.language_id}", level="debug")
                else:
                    await log(f"Failed to register pattern {full_name}", level="warning")
                    
            except Exception as e:
                results[name] = False
                await log(f"Error registering pattern {name}: {e}", level="error")
        
        # Log summary
        success_count = sum(1 for success in results.values() if success)
        await log(f"Registered {success_count}/{len(patterns)} patterns from {source}", level="info")
        
        return results

    async def create_feature_extractor(self) -> Optional['TreeSitterFeatureExtractor']:
        """Create a TreeSitterFeatureExtractor for this parser.
        
        This factory method creates a specialized feature extractor that
        leverages the tree-sitter capabilities of this parser.
        
        Returns:
            Optional[TreeSitterFeatureExtractor]: The feature extractor or None if creation fails
        """
        try:
            # Import feature extractor
            from parsers.feature_extractor import TreeSitterFeatureExtractor
            
            # Create and initialize extractor
            extractor = TreeSitterFeatureExtractor(self.language_id)
            
            # Initialize the extractor
            if await extractor.initialize():
                await log(f"Created TreeSitterFeatureExtractor for {self.language_id}", level="info")
                return extractor
            else:
                await log(f"Failed to initialize TreeSitterFeatureExtractor for {self.language_id}", level="warning")
                return None
                
        except ImportError as e:
            await log(f"TreeSitterFeatureExtractor not available: {e}", level="warning")
            return None
        except Exception as e:
            await log(f"Error creating TreeSitterFeatureExtractor: {e}", level="error")
            return None

    async def get_health_metrics(self) -> Dict[str, Any]:
        """Get health metrics for the parser.
        
        Returns:
            Dict[str, Any]: Health metrics dictionary
        """
        # Get basic metrics
        metrics = await self._report_health()
        
        # Add query metrics if available
        if self.query_registry:
            query_metrics = await self.query_registry._report_health()
            metrics["query_registry"] = query_metrics
            
        return metrics

    async def cleanup(self) -> None:
        """Clean up resources used by the parser.
        
        This method releases resources held by the tree-sitter parser
        and unregisters from health monitoring and other systems.
        """
        try:
            # Clean up tree-sitter resources
            if self.parser:
                self.parser = None
            
            # Clean up language resources
            self.language = None
            
            # Clean up query registry
            if self.query_registry:
                self.query_registry.patterns.clear()
                self.query_registry = None
            
            # Unregister from health monitor
            try:
                from utils.health_monitor import unregister_component
                unregister_component(self._component_id)
            except ImportError:
                pass
            
            # Remove from instance cache if using global cache
            try:
                language_id = self.language_id.lower()
                if language_id in _parser_instances:
                    del _parser_instances[language_id]
            except Exception:
                pass
            
            await log(f"Cleaned up tree-sitter parser for {self.language_id}", level="info")
        except Exception as e:
            await log(f"Error cleaning up tree-sitter parser: {e}", level="error")

    async def record_error(self, error: Exception, operation: str, context: Dict[str, Any] = None) -> None:
        """Record an error that occurred during parsing operations.
        
        This method records detailed error information for analysis and
        debugging.
        
        Args:
            error: The exception that occurred
            operation: Name of the operation that failed
            context: Additional context for the error
        """
        try:
            # Import error handling module
            from utils.error_handling import record_error
            
            # Prepare context
            error_context = {
                'language_id': self.language_id,
                'parser_type': self.parser_type.value,
                'operation': operation,
            }
            
            # Add additional context if provided
            if context:
                error_context.update(context)
                
            # Record error
            await record_error(
                component=self._component_id,
                error_type=type(error).__name__,
                message=str(error),
                context=error_context
            )
            
            # Update health metrics
            from utils.health_monitor import increment_counter
            await increment_counter(f"{self._component_id}.errors")
            
        except Exception as e:
            await log(f"Error recording error metrics: {e}", level="warning")

    async def _execute_query(self, query_string: str, tree: Any) -> Dict[str, List[Dict[str, Any]]]:
        """Execute a tree-sitter query and return the results.
        
        Args:
            query_string: The tree-sitter query string
            tree: The tree-sitter parse tree
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of capture name to node information
        """
        results = {}
        
        try:
            # Create tree-sitter query
            query = self.language.query(query_string)
            
            # Execute query
            captures = query.captures(tree.root_node)
            
            # Process captures
            for node, capture_name in captures:
                if capture_name not in results:
                    results[capture_name] = []
                    
                # Convert node to dictionary
                node_info = self._convert_node(node)
                
                # Add to results
                results[capture_name].append(node_info)
                
        except Exception as e:
            await log(f"Error executing tree-sitter query: {e}", level="error")
            
        return results

    async def _execute_optimized_query(self, query_string: str, tree: Any, match_limit: int = 1000, timeout_micros: int = 50000) -> Dict[str, List[Dict[str, Any]]]:
        """Execute a tree-sitter query with optimizations for performance.
        
        This method applies various optimizations to handle complex queries
        efficiently, including limits and timeouts.
        
        Args:
            query_string: The tree-sitter query string
            tree: The tree-sitter parse tree
            match_limit: Maximum number of matches to process
            timeout_micros: Query timeout in microseconds
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of capture name to node information
        """
        results = {}
        
        try:
            # Create tree-sitter query
            query = self.language.query(query_string)
            
            # Set query limit parameter (available in newer versions)
            matches = query.matches(
                tree.root_node,
                max_results=match_limit
            )
            
            # Process matches up to limit
            match_count = 0
            for match in matches:
                if match_count >= match_limit:
                    break
                    
                for capture_index, node in match.captures:
                    capture_name = query.capture_names[capture_index]
                    
                    if capture_name not in results:
                        results[capture_name] = []
                        
                    # Convert node to dictionary
                    node_info = self._convert_node(node)
                    
                    # Add to results
                    results[capture_name].append(node_info)
                    
                match_count += 1
                
        except Exception as e:
            await log(f"Error executing optimized tree-sitter query: {e}", level="error")
            
        return results

    async def _monitor_query_performance(self, query_string: str, tree: Any) -> Dict[str, Any]:
        """Monitor performance metrics for a tree-sitter query.
        
        This method collects performance data for query execution to help
        identify expensive queries and optimize them.
        
        Args:
            query_string: The tree-sitter query string
            tree: The tree-sitter parse tree
            
        Returns:
            Dict[str, Any]: Dictionary of performance metrics
        """
        import time
        
        metrics = {
            'query_length': len(query_string),
            'pattern_count': query_string.count('@'),
            'or_pattern_count': query_string.count('|'),
            'estimated_complexity': 0,
            'execution_time_ms': 0,
            'capture_count': 0,
            'match_count': 0
        }
        
        try:
            # Estimate complexity based on query characteristics
            metrics['estimated_complexity'] = (
                metrics['query_length'] * 0.1 +
                metrics['pattern_count'] * 2 +
                metrics['or_pattern_count'] * 5
            )
            
            # Measure execution time
            start_time = time.time()
            
            # Create tree-sitter query
            query = self.language.query(query_string)
            
            # Execute query to measure performance
            matches = query.matches(tree.root_node)
            captures = query.captures(tree.root_node)
            
            # Record execution time
            end_time = time.time()
            metrics['execution_time_ms'] = (end_time - start_time) * 1000
            
            # Count captures and matches
            metrics['capture_count'] = len(list(captures))
            metrics['match_count'] = len(list(matches))
            
        except Exception as e:
            await log(f"Error monitoring query performance: {e}", level="warning")
            
        return metrics

# Global instance cache
_parser_instances: Dict[str, TreeSitterParser] = {}

async def get_tree_sitter_parser(language_id: str) -> Optional[TreeSitterParser]:
    """Get a tree-sitter parser instance for the specified language.
    
    This factory function creates and initializes a TreeSitterParser for the
    given language, if it's supported by tree-sitter.
    
    Args:
        language_id: The language identifier
        
    Returns:
        Optional[TreeSitterParser]: The parser instance or None if not supported
    """
    language_id = language_id.lower()
    
    # Try to get from cache first using unified cache system
    from utils.cache import UnifiedCache
    cache_key = f"tree_sitter_parser:{language_id}"
    parser = await UnifiedCache.get(cache_key)
    
    if parser:
        return parser
    
    # If not in cache, create new instance
    try:
        # Check if language is supported
        from tree_sitter_language_pack import SupportedLanguage
        if language_id not in SupportedLanguage.__args__:
            await log(f"Language {language_id} not supported by tree-sitter", level="warning")
            return None
            
        # Create parser instance
        parser = TreeSitterParser(language_id)
        
        # Initialize parser
        if await parser._initialize():
            # Store in both caches for backward compatibility
            _parser_instances[language_id] = parser
            
            # Add to unified cache with TTL
            await UnifiedCache.set(
                cache_key,
                parser,
                ttl=3600  # 1 hour cache
            )
            
            await log(f"Tree-sitter parser initialized and cached for {language_id}", level="info")
            return parser
        else:
            await log(f"Failed to initialize tree-sitter parser for {language_id}", level="warning")
            return None
            
    except ImportError:
        await log("tree-sitter-language-pack not available", level="warning")
        return None
    except Exception as e:
        await log(f"Error creating tree-sitter parser for {language_id}: {e}", level="error")
        return None

async def get_tree_sitter_feature_extractor(language_id: str) -> Optional['TreeSitterFeatureExtractor']:
    """Get a tree-sitter feature extractor for the specified language.
    
    This factory function creates and initializes a TreeSitterFeatureExtractor 
    for the given language, using the associated TreeSitterParser.
    
    Args:
        language_id: The language identifier
        
    Returns:
        Optional[TreeSitterFeatureExtractor]: The feature extractor or None if not supported
    """
    language_id = language_id.lower()
    
    # Try to get from cache first
    from utils.cache import UnifiedCache
    cache_key = f"tree_sitter_feature_extractor:{language_id}"
    extractor = await UnifiedCache.get(cache_key)
    
    if extractor:
        return extractor
    
    # Get parser first
    parser = await get_tree_sitter_parser(language_id)
    if not parser:
        await log(f"No tree-sitter parser available for {language_id}", level="warning")
        return None
    
    # Create feature extractor using async runner for potentially long operation
    from utils.async_runner import submit_async_task
    try:
        create_task = submit_async_task(parser.create_feature_extractor())
        extractor = await asyncio.wrap_future(create_task)
        
        if extractor:
            # Cache the extractor
            await UnifiedCache.set(
                cache_key,
                extractor,
                ttl=3600  # 1 hour cache
            )
            
        return extractor
    except Exception as e:
        await log(f"Error creating tree-sitter feature extractor: {e}", level="error")
        return None

async def initialize_tree_sitter_system() -> bool:
    """Initialize the tree-sitter parser system.
    
    This function is called during application initialization to set up
    the tree-sitter parser system, including preloading frequently used parsers.
    
    Returns:
        bool: True if initialization was successful
    """
    try:
        # Register with health monitoring
        from utils.health_monitor import register_component
        register_component("tree_sitter_system", _report_system_health)
        
        # Preload common language parsers for faster startup
        common_langs = ["python", "javascript", "typescript", "java", "go", "rust"]
        
        # Use async gather to load parsers concurrently
        init_tasks = []
        for lang in common_langs:
            try:
                from tree_sitter_language_pack import SupportedLanguage
                if lang in SupportedLanguage.__args__:
                    init_tasks.append(get_tree_sitter_parser(lang))
            except ImportError:
                await log("tree-sitter-language-pack not available", level="warning")
                break
        
        if init_tasks:
            await asyncio.gather(*init_tasks, return_exceptions=True)
        
        # Register cleanup for application shutdown
        from utils.shutdown import register_shutdown_handler
        register_shutdown_handler(cleanup_tree_sitter_system)
        
        await log("Tree-sitter system initialized", level="info")
        return True
        
    except Exception as e:
        await log(f"Error initializing tree-sitter system: {e}", level="error")
        return False

async def _report_system_health() -> Dict[str, Any]:
    """Report health metrics for the tree-sitter system.
    
    Returns:
        Dict[str, Any]: Health metrics
    """
    return {
        'initialized': True,
        'parser_count': len(_parser_instances),
        'parsers': list(_parser_instances.keys())
    }

async def cleanup_tree_sitter_system() -> None:
    """Clean up resources used by the tree-sitter parser system.
    
    This function is registered with the shutdown handler and is called
    during application shutdown.
    """
    try:
        # Clean up parser instances
        tasks = []
        for parser in _parser_instances.values():
            tasks.append(parser.cleanup())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        _parser_instances.clear()
        
        await log("Tree-sitter system cleaned up", level="info")
    except Exception as e:
        await log(f"Error cleaning up tree-sitter system: {e}", level="error")