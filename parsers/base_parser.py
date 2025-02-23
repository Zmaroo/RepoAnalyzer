"""Base parser interface and implementations."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from parsers.models import (
    ParserResult,
    ParserConfig,
    ParsingStatistics,
    FileType,
    ExtractedFeatures,
    ParserType
)
from parsers.feature_extractor import TreeSitterFeatureExtractor, CustomFeatureExtractor
from parsers.language_mapping import TREE_SITTER_LANGUAGES
from utils.logger import log
from parsers.pattern_processor import PatternProcessor
from parsers.models import FeatureCategory

class BaseParser(ABC):
    """Abstract base class for all parsers.
    
    Implementations:
    - TreeSitterParser: For languages with tree-sitter support
    - Language-specific parsers (NimParser, PlaintextParser, etc.): For custom parsing
    """
    
    def __init__(self, language_id: str, file_type: FileType, parser_type: ParserType):
        self.language_id = language_id
        self.file_type = file_type
        self.parser_type = parser_type
        self._initialized = False
        self.config = ParserConfig()
        self.stats = ParsingStatistics()
        
        # Create appropriate feature extractor based on parser type
        self.feature_extractor = (
            TreeSitterFeatureExtractor(language_id, file_type)
            if parser_type == ParserType.TREE_SITTER
            else CustomFeatureExtractor(language_id, file_type)
        )
        
        self.pattern_processor = PatternProcessor()
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize parser-specific resources.
        
        Returns:
            bool: True if initialization successful
        """
        pass
    
    @abstractmethod
    def _parse_source(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Generate AST from source code.
        
        Args:
            source_code (str): Source code to parse
            
        Returns:
            Optional[Dict[str, Any]]: AST structure or None if parsing fails
            
        For tree-sitter parsers:
            Returns {"type": "tree-sitter", "root": Node, "tree": Dict}
            
        For custom parsers:
            Returns CustomParserNode.__dict__ with structure:
            {
                "type": str,
                "start_point": List[int],
                "end_point": List[int],
                "children": List[Dict],
                "metadata": Dict[str, Any]
            }
        """
        pass

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
                features=features.model_dump(),
                documentation=features.documentation.model_dump(),
                complexity=features.metrics.model_dump(),
                statistics=self.stats.model_dump(),
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
        patterns = self.pattern_processor.get_patterns_for_category(category)
        
        if category == FeatureCategory.SYNTAX:
            return self._extract_syntax_features(ast, patterns)
        elif category == FeatureCategory.SEMANTICS:
            return self._extract_semantic_features(ast, patterns)
        elif category == FeatureCategory.DOCUMENTATION:
            return self._extract_documentation_features(source_code, patterns)
        elif category == FeatureCategory.STRUCTURE:
            return self._extract_structure_features(ast, patterns)
        
        return {} 