"""Base parser interface and implementations."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from .types import FileType, FeatureCategory, ParserType, ParserResult, ParserConfig, ParsingStatistics
from dataclasses import dataclass, field
from utils.logger import log

@dataclass
class BaseParser(ABC):
    """Abstract base class for all parsers.
    
    Implementations:
    - TreeSitterParser: For languages with tree-sitter support
    - Language-specific parsers (NimParser, PlaintextParser, etc.): For custom parsing
    """
    
    language_id: str
    file_type: FileType
    parser_type: ParserType
    _initialized: bool = False
    config: ParserConfig = field(default_factory=lambda: ParserConfig())
    stats: ParsingStatistics = field(default_factory=lambda: ParsingStatistics())
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize parser resources."""
        pass
    
    @abstractmethod
    def _parse_source(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Parse source code into AST."""
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