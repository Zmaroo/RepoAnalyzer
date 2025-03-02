"""Base parser implementation."""
from abc import abstractmethod
from typing import Optional, Dict, Any, List, Union, Type, Callable
from .types import FileType, FeatureCategory, ParserType, ParserResult, ParserConfig, ParsingStatistics
from dataclasses import field
import re
from parsers.types import PatternCategory
from parsers.models import PatternType, QueryPattern
from utils.logger import log
from .parser_interfaces import BaseParserInterface
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary


class BaseParser(BaseParserInterface):
    """Base implementation for parsers.
    
    Implementations:
    - TreeSitterParser: For languages with tree-sitter support
    - Language-specific parsers (NimParser, PlaintextParser, etc.): For custom parsing
    """

    def __post_init__(self):
        self._initialized = False
        from parsers.feature_extractor import TreeSitterFeatureExtractor, CustomFeatureExtractor
        if self.parser_type == ParserType.TREE_SITTER:
            self.feature_extractor = TreeSitterFeatureExtractor(self.
                language_id, self.file_type)
        elif self.parser_type == ParserType.CUSTOM:
            self.feature_extractor = CustomFeatureExtractor(self.
                language_id, self.file_type)
        else:
            self.feature_extractor = None

    def _create_node(self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs) ->Dict[str, Any]:
        """Helper for creating a standardized AST node. (Subclasses can override if needed.)"""
        return {'type': node_type, 'start_point': start_point, 'end_point':
            end_point, 'children': [], **kwargs}

    def _compile_patterns(self, patterns_dict: dict) ->dict:
        """Helper to compile regex patterns from a definitions dictionary."""
        compiled = {}
        for category in patterns_dict.values():
            for name, pattern_obj in category.items():
                compiled[name] = re.compile(pattern_obj.pattern)
        return compiled

    def _get_syntax_errors(self, ast: Dict[str, Any]) ->List[Dict[str, Any]]:
        """Get syntax errors from AST.
        
        Args:
            ast (Dict[str, Any]): AST to check for errors
            
        Returns:
            List[Dict[str, Any]]: List of syntax errors
        """
        return []

    def _check_ast_cache(self, source_code: str) ->Optional[Dict[str, Any]]:
        """Check if an AST for this source code is already cached.
        
        Args:
            source_code (str): The source code to check for in the cache
            
        Returns:
            Optional[Dict[str, Any]]: The cached AST if found, None otherwise
        """
        import warnings
        warnings.warn(f"{__name__}::_check_ast_cache is deprecated. Use async_check_ast_cache instead.", DeprecationWarning, stacklevel=2)
        import hashlib
        import asyncio
        from utils.cache import ast_cache
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f'ast:{self.language_id}:{source_hash}'
        with ErrorBoundary(f'check_ast_cache_{self.language_id}',
            error_types=(Exception,)):
            cached_ast = asyncio.run(ast_cache.get_async(cache_key))
            if cached_ast:
                log(f'AST cache hit for {self.language_id}', level='debug')
                return cached_ast
        return None

    def _store_ast_in_cache(self, source_code: str, ast: Dict[str, Any]) ->None:
        """Store an AST in the cache.
        
        Args:
            source_code (str): The source code associated with the AST
            ast (Dict[str, Any]): The AST to cache
        """
        import warnings
        warnings.warn(f"{__name__}::_store_ast_in_cache is deprecated. Use async_store_ast_in_cache instead.", DeprecationWarning, stacklevel=2)
        import hashlib
        import asyncio
        from utils.cache import ast_cache
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f'ast:{self.language_id}:{source_hash}'
        with ErrorBoundary(f'store_ast_in_cache_{self.language_id}',
            error_types=(Exception,)):
            asyncio.run(ast_cache.set_async(cache_key, ast))
            log(f'AST cached for {self.language_id}', level='debug')

    def parse(self, source_code: str) ->Optional[ParserResult]:
        """[2.2] Unified parsing pipeline."""
        with ErrorBoundary(error_types=(Exception,), operation_name=
            'parse_source'):
            if not self._initialized and not self.initialize():
                log(f'Failed to initialize {self.language_id} parser',
                    level='error')
                return None
            cached_ast = self._check_ast_cache(source_code)
            if cached_ast:
                ast = cached_ast
            else:
                ast = self._parse_source(source_code)
                if ast:
                    self._store_ast_in_cache(source_code, ast)
            if not ast:
                return None
            features = self.feature_extractor.extract_features(ast, source_code
                )
            errors = self._get_syntax_errors(ast)
            return ParserResult(success=True, ast=ast, features=features.
                features, documentation=features.documentation.__dict__,
                complexity=features.metrics.__dict__, statistics=self.stats
                .__dict__, errors=errors)
        return None

@handle_errors(error_types=(Exception,))
    def cleanup(self):
        """Clean up parser resources."""
        self._initialized = False
        self.stats = ParsingStatistics()

    def _extract_category_features(self, category: FeatureCategory, ast:
        Dict[str, Any], source_code: str) ->Dict[str, Any]:
        """Extract features for a specific category."""
        patterns = self.feature_extractor._patterns
        if category == FeatureCategory.SYNTAX:
            return self._extract_syntax_features(ast, patterns)
        elif category == FeatureCategory.SEMANTICS:
            return self._extract_semantic_features(ast, patterns)
        elif category == FeatureCategory.DOCUMENTATION:
            return self._extract_documentation_features(source_code, patterns)
        elif category == FeatureCategory.STRUCTURE:
            return self._extract_structure_features(ast, patterns)
        return {}

    def extract_patterns(self, source_code: str) ->List[Dict[str, Any]]:
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
        with ErrorBoundary(f'extract_patterns_{self.language_id}',
            error_types=(Exception,)):
            ast = self.parse(source_code)
            from parsers.pattern_processor import pattern_processor
            if hasattr(pattern_processor, 'extract_repository_patterns'):
                language_patterns = (pattern_processor.
                    extract_repository_patterns(file_path='', source_code=
                    source_code, language=self.language_id))
                patterns.extend(language_patterns)
            if self.file_type == FileType.CODE:
                code_patterns = self._extract_code_patterns(ast, source_code)
                patterns.extend(code_patterns)
            elif self.file_type == FileType.DOCUMENTATION:
                doc_patterns = self._extract_doc_patterns(ast, source_code)
                patterns.extend(doc_patterns)
        return patterns

    def _extract_code_patterns(self, ast: Dict[str, Any], source_code: str) ->List[Dict[str, Any]]:
        """Extract code patterns from AST. Override in subclasses for language-specific behavior."""
        import warnings
        warnings.warn(f"'_extract_code_patterns' is deprecated, use '_extract_code_patterns' instead", DeprecationWarning, stacklevel=2)
        return []


    # Add deprecation warning

    import warnings

    warnings.warn(f"'_extract_doc_patterns' is deprecated, use '_extract_doc_patterns' instead", DeprecationWarning, stacklevel=2)
    def _extract_doc_patterns(self, ast: Dict[str, Any], source_code: str) ->List[Dict[str, Any]]:
        """Extract documentation patterns from AST. Override in subclasses for language-specific behavior."""
        import warnings
        warnings.warn(f"'_extract_doc_patterns' is deprecated, use '_extract_doc_patterns' instead", DeprecationWarning, stacklevel=2)
        return []
        # Add deprecation warning
        import warnings
        warnings.warn(f"'_extract_code_patterns' is deprecated, use '_extract_code_patterns' instead", DeprecationWarning, stacklevel=2)
