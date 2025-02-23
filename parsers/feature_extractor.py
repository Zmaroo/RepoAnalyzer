"""Feature extraction implementations."""

from typing import Dict, Any, List, Optional, Union, Generator, Tuple
from tree_sitter import Node, Query, QueryError, Parser, Language, TreeCursor
from .types import FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics
from parsers.models import (
    ExtractedFeatures,
    QueryResult,
    FeatureExtractor,
    FileClassification,
    language_registry,
)
from utils.logger import log
from parsers.language_support import language_registry
from parsers.pattern_processor import PatternProcessor, PatternMatch, PatternCategory, pattern_processor
from parsers.query_patterns import PATTERN_CATEGORIES
from parsers.language_mapping import TREE_SITTER_LANGUAGES
from abc import ABC, abstractmethod

class BaseFeatureExtractor(ABC):
    """[3.2.0] Abstract base class for feature extraction."""
    
    def __init__(self, language_id: str, file_type: FileType):
        # [3.2.0.1] Initialize Base Extractor
        # USES: [pattern_processor.py] pattern_processor.get_patterns_for_file()
        self.language_id = language_id
        self.file_type = file_type
        self._patterns = pattern_processor.get_patterns_for_file(
            FileClassification(
                file_type=file_type,
                language_id=language_id,
                parser_type=language_registry.get_parser_type(language_id)
            )
        )
    
    @abstractmethod
    def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features from existing AST."""
        pass

# FILE: parsers/feature_extractor.py
# PROVIDES: Feature extraction for both parser types
# RETURNS: ExtractedFeatures

class TreeSitterFeatureExtractor(BaseFeatureExtractor):
    """[3.2.1] Tree-sitter specific feature extraction."""
    
    def __init__(self, language_id: str, file_type: FileType):
        super().__init__(language_id, file_type)
        # [3.2.1.1] Initialize Tree-sitter Components
        self._language_registry = language_registry
        self._parser = None
        self._queries = {}
        self._initialize_parser()
    
    def _initialize_parser(self):
        """Initialize tree-sitter parser."""
        self._parser = Parser()
        self._language = self._language_registry.get_language(self.language_id)
        self._parser.set_language(self._language)
        self._load_patterns()
    
    def _load_patterns(self):
        """Load patterns from central pattern processor."""
        for category in PatternCategory:
            category_name = category.value
            if category_name in self._patterns:
                for pattern in self._patterns[category_name].values():
                    if pattern_processor.validate_pattern(pattern, self.language_id):
                        self._compile_pattern(category_name, pattern)
    
    def _compile_pattern(self, category: str, name: str, pattern_def: Union[str, Dict]):
        """Compile a pattern definition into a Tree-sitter query."""
        try:
            if isinstance(pattern_def, str):
                query_str = pattern_def
                extractor = None
            else:
                query_str = pattern_def['pattern']
                extractor = pattern_def.get('extract')
            
            # Create and configure query
            query = self._language.query(query_str)
            query.set_timeout_micros(self.QUERY_TIMEOUT_MICROS)
            query.set_match_limit(self.QUERY_MATCH_LIMIT)
            
            self._queries[category][name] = {
                'query': query,
                'extract': extractor
            }
            
        except Exception as e:
            log(f"Error compiling pattern {name}: {e}", level="error")
    
    def _process_query_result(self, result: QueryResult) -> Dict[str, Any]:
        """Process a single query result."""
        try:
            node_features = self._extract_node_features(result.node)
            
            # Add capture information
            node_features['captures'] = {
                name: self._extract_node_features(node)
                for name, node in result.captures.items()
            }
            
            # Add metadata
            node_features.update(result.metadata)
            
            return node_features
            
        except Exception as e:
            log(f"Error processing query result: {e}", level="error")
            return {}
    
    def _extract_node_features(self, node: Node) -> Dict[str, Any]:
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
    
    def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """[3.2.1.2] Extract features from Tree-sitter AST."""
        try:
            # [3.2.1.3] Parse Tree and Extract Features
            tree = self._parser.parse(bytes(source_code, "utf8"))
            if not tree:
                raise ValueError("Failed to parse source code")
                
            features = {category: {} for category in PatternCategory}
            root_node = tree.root_node
            
            # [3.2.1.4] Process Patterns by Category
            # USES: [pattern_processor.py] QueryResult
            for category, patterns in self._queries.items():
                category_features = {}
                for pattern_name, pattern_info in patterns.items():
                    query = pattern_info['query']
                    extractor = pattern_info['extract']
                    matches = []
                    
                    # Process matches
                    for match in query.matches(root_node):
                        try:
                            result = QueryResult(
                                pattern_name=pattern_name,
                                node=match.pattern_node,
                                captures={c.name: c.node for c in match.captures}
                            )
                            if extractor:
                                result.metadata = extractor(result)
                            processed = self._process_query_result(result)
                            if processed:
                                matches.append(processed)
                        except Exception as e:
                            continue
                            
                    if matches:
                        category_features[pattern_name] = matches
                        
                features[category] = category_features
            
            # [3.2.1.5] Return Extracted Features
            # RETURNS: [models.py] ExtractedFeatures
            return ExtractedFeatures(
                features=features,
                documentation=self._extract_documentation(features),
                metrics=self._calculate_metrics(features, source_code)
            )
            
        except Exception as e:
            log(f"Error extracting features: {e}", level="error")
            return ExtractedFeatures()

class CustomFeatureExtractor(BaseFeatureExtractor):
    """[3.2.2] Custom parser feature extraction."""
    
    def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """
        Extract features using regex patterns.
        
        USES: [pattern_processor.py] pattern_processor.get_patterns_for_file()
        RETURNS: [models.py] ExtractedFeatures containing:
        - Documentation
        - Complexity metrics
        - Pattern matches
        """
        try:
            # [3.2.2.1] Initialize Feature Categories
            features = {category: {} for category in PatternCategory}
            
            # [3.2.2.2] Process each category
            for category, patterns in self._patterns.items():
                category_features = {}
                
                # [3.2.2.3] Process each regex pattern
                for pattern_name, pattern in patterns.items():
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
                                result.update(pattern.extract(result))
                                
                            matches.append(result)
                            
                        if matches:
                            category_features[pattern_name] = matches
                
                features[category] = category_features
                
            # [3.2.2.5] Return standardized features
            # RETURNS: [models.py] ExtractedFeatures
            return ExtractedFeatures(
                features=features,
                documentation=self._extract_documentation(features),
                metrics=self._calculate_metrics(features, source_code)
            )
            
        except Exception as e:
            log(f"Error extracting features: {e}", level="error")
            return ExtractedFeatures()