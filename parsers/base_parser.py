"""Base parser interface and implementations."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from parsers.models import ParserResult, ParserConfig, ParsingStatistics
from parsers.file_classification import FileType, FileClassification
from parsers.feature_extractor import FeatureExtractor
from parsers.pattern_processor import pattern_processor
from utils.logger import log
import time

class BaseParser(ABC):
    """Abstract base class for all parsers."""
    
    def __init__(self, language_id: str, file_type: FileType):
        self.language_id = language_id
        self.file_type = file_type
        self._initialized = False
        self.config = ParserConfig()
        self.stats = ParsingStatistics()
        self.feature_extractor = None
        self.pattern_processor = pattern_processor
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize parser resources."""
        pass
    
    def parse(self, source_code: str) -> ParserResult:
        """Parse source code into AST and extract features."""
        start_time = time.time()
        
        try:
            if not self._initialized and not self.initialize():
                return ParserResult.error("Parser not initialized")
            
            # Parse source code
            parse_start = time.time()
            ast = self._parse_source(source_code)
            self.stats.parse_time_ms = (time.time() - parse_start) * 1000
            
            if not ast:
                return ParserResult.error("Failed to parse source code")
            
            # Extract features
            feature_start = time.time()
            features = self._extract_features(ast, source_code)
            self.stats.feature_extraction_time_ms = (time.time() - feature_start) * 1000
            
            # Calculate complexity
            complexity_start = time.time()
            complexity = self._calculate_complexity(features)
            self.stats.complexity_calculation_time_ms = (time.time() - complexity_start) * 1000
            
            # Update statistics
            self.stats.total_nodes_processed = self._count_nodes(ast)
            self.stats.total_time_ms = (time.time() - start_time) * 1000
            
            return ParserResult(
                success=True,
                language=self.language_id,
                file_type=self.file_type.value,
                ast=ast,
                features=features,
                documentation=features.documentation if features else None,
                complexity=complexity,
                source_code=source_code,
                total_lines=len(source_code.splitlines()),
                statistics=self.stats
            )
            
        except Exception as e:
            log(f"Error in parser: {e}", level="error")
            return ParserResult.error(str(e))
    
    @abstractmethod
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Implementation-specific source code parsing."""
        pass
    
    def _extract_features(self, ast: Dict[str, Any], source_code: str) -> Dict[str, Any]:
        """Extract features using feature extractor."""
        if not self.feature_extractor:
            self.feature_extractor = FeatureExtractor(self.file_type, self.language_id)
        return self.feature_extractor.extract_features(ast, source_code, self.pattern_processor.patterns)
    
    def _calculate_complexity(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate code complexity metrics."""
        from parsers.feature_extractor import calculate_complexity
        return calculate_complexity(features)
    
    def _count_nodes(self, ast: Dict[str, Any]) -> int:
        """Count total nodes in AST."""
        if isinstance(ast, dict):
            return 1 + sum(self._count_nodes(v) for v in ast.values())
        elif isinstance(ast, list):
            return sum(self._count_nodes(item) for item in ast)
        return 0
    
    def cleanup(self):
        """Clean up any resources."""
        self._initialized = False
        self.stats = ParsingStatistics()

class TreeSitterParser(BaseParser):
    """Tree-sitter based parser implementation."""
    
    def __init__(self, language_id: str, classification: FileClassification):
        super().__init__(language_id, classification.file_type)
        self.classification = classification
        self.parser = None
        self.language = None
    
    def initialize(self) -> bool:
        """Initialize tree-sitter parser."""
        try:
            from tree_sitter import Parser, Language
            self.parser = Parser()
            self.language = Language('build/languages.so', self.language_id)
            self.parser.set_language(self.language)
            self._initialized = True
            return True
        except Exception as e:
            log(f"Failed to initialize tree-sitter parser: {e}", level="error")
            return False
    
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse source code using tree-sitter."""
        tree = self.parser.parse(bytes(source_code, "utf8"))
        return {"type": "tree-sitter", "root": tree.root_node}

class CustomParser(BaseParser):
    """Base class for custom parsers."""
    
    def __init__(self, language_id: str, classification: FileClassification):
        super().__init__(language_id, classification.file_type)
        self.classification = classification
    
    def initialize(self) -> bool:
        """Initialize custom parser."""
        self._initialized = True
        return True
    
    @abstractmethod
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Implementation-specific parsing logic."""
        pass 