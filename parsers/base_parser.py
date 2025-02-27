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

class BaseParser(BaseParserInterface):
    """Base implementation for parsers.
    
    Implementations:
    - TreeSitterParser: For languages with tree-sitter support
    - Language-specific parsers (NimParser, PlaintextParser, etc.): For custom parsing
    """
    
    def __post_init__(self):
        self._initialized = False
        # Initialize feature extractor according to parser type.
        from parsers.feature_extractor import TreeSitterFeatureExtractor, CustomFeatureExtractor
        if self.parser_type == ParserType.TREE_SITTER:
            self.feature_extractor = TreeSitterFeatureExtractor(self.language_id, self.file_type)
        elif self.parser_type == ParserType.CUSTOM:
            self.feature_extractor = CustomFeatureExtractor(self.language_id, self.file_type)
        else:
            self.feature_extractor = None

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
        """Get syntax errors from AST.
        
        Args:
            ast (Dict[str, Any]): AST to check for errors
            
        Returns:
            List[Dict[str, Any]]: List of syntax errors
        """
        return []

    def parse(self, source_code: str) -> Optional[ParserResult]:
        """[2.2] Unified parsing pipeline."""
        try:
            # [2.2.1] Initialize Parser
            if not self._initialized and not self.initialize():
                log(f"Failed to initialize {self.language_id} parser", level="error")
                return None

            # [2.2.2] Generate AST
            # USES: Implemented by TreeSitterParser or CustomParser
            ast = self._parse_source(source_code)
            if not ast:
                return None

            # [2.2.3] Extract Features
            # USES: [feature_extractor.py] FeatureExtractor.extract_features()
            features = self.feature_extractor.extract_features(ast, source_code)

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
        except Exception as e:
            log(f"Error parsing content: {e}", level="error")
            return None

    def cleanup(self):
        """Clean up parser resources."""
        self._initialized = False
        self.stats = ParsingStatistics()

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
        
        try:
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
                
        except Exception as e:
            log(f"Error extracting patterns from {self.language_id}: {e}", level="error")
            
        return patterns
        
    def _extract_code_patterns(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Extract code patterns from AST. Override in subclasses for language-specific behavior."""
        return []
        
    def _extract_doc_patterns(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Extract documentation patterns from AST. Override in subclasses for language-specific behavior."""
        return [] 