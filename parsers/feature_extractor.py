"""Unified feature extraction for all parser types."""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from tree_sitter import Node, Tree
from parsers.file_classification import FileType
from parsers.models import (
    Documentation, ComplexityMetrics, 
    ExtractedFeatures, FeatureCategory
)
from utils.logger import log

@dataclass
class FeatureExtractor:
    """Central feature extraction coordinator."""
    
    file_type: FileType
    language_id: str
    _cache: Dict[str, Any] = field(default_factory=dict)
    
    def extract_features(
        self,
        ast: Union[Node, Dict],
        source_code: str,
        patterns: Optional[Dict] = None
    ) -> ExtractedFeatures:
        """Main feature extraction entry point."""
        try:
            features = ExtractedFeatures()
            
            # Extract syntax features
            features.syntax = self._extract_syntax_features(ast, source_code)
            
            # Extract structural features
            features.structure = self._extract_structural_features(ast)
            
            # Extract semantic features
            features.semantics = self._extract_semantic_features(ast, patterns)
            
            # Extract documentation
            features.documentation = self._extract_documentation(ast, source_code)
            
            # Calculate metrics
            features.metrics = self._calculate_metrics(features)
            
            return features
            
        except Exception as e:
            log(f"Error extracting features: {e}", level="error")
            return ExtractedFeatures()
    
    def _extract_syntax_features(self, ast: Any, source_code: str) -> Dict[str, List[Dict]]:
        """Extract syntax-level features."""
        features = {
            'literals': [],
            'operators': [],
            'keywords': [],
            'identifiers': []
        }
        
        if isinstance(ast, dict) and ast.get("type") == "tree-sitter":
            self._process_tree_sitter_syntax(ast["root"], features, source_code)
        else:
            self._process_custom_syntax(ast, features)
            
        return features
    
    def _extract_structural_features(self, ast: Any) -> Dict[str, List[Dict]]:
        """Extract structural features."""
        features = {
            'functions': [],
            'classes': [],
            'modules': [],
            'blocks': []
        }
        
        if isinstance(ast, dict) and ast.get("type") == "tree-sitter":
            self._process_tree_sitter_structure(ast["root"], features)
        else:
            self._process_custom_structure(ast, features)
            
        return features
    
    def _extract_semantic_features(
        self, 
        ast: Any, 
        patterns: Optional[Dict]
    ) -> Dict[str, List[Dict]]:
        """Extract semantic features."""
        features = {
            'imports': [],
            'references': [],
            'dependencies': [],
            'types': []
        }
        
        if patterns:
            self._apply_semantic_patterns(ast, patterns, features)
            
        return features
    
    def _extract_documentation(self, ast: Any, source_code: str) -> Documentation:
        """Extract documentation features."""
        doc = Documentation()
        
        try:
            if isinstance(ast, dict) and ast.get("type") == "tree-sitter":
                self._process_tree_sitter_docs(ast["root"], doc, source_code)
            else:
                self._process_custom_docs(ast, doc)
                
        except Exception as e:
            log(f"Error extracting documentation: {e}", level="error")
            
        return doc
    
    def _calculate_metrics(self, features: ExtractedFeatures) -> ComplexityMetrics:
        """Calculate code complexity metrics."""
        try:
            return ComplexityMetrics(
                cyclomatic=self._calculate_cyclomatic_complexity(features),
                cognitive=self._calculate_cognitive_complexity(features),
                halstead=self._calculate_halstead_metrics(features),
                maintainability_index=self._calculate_maintainability_index(features),
                node_count=self._count_nodes(features),
                depth=self._calculate_max_depth(features)
            )
        except Exception as e:
            log(f"Error calculating metrics: {e}", level="error")
            return ComplexityMetrics()
    
    def _process_tree_sitter_syntax(self, node: Node, features: Dict, source_code: str):
        """Process tree-sitter syntax nodes."""
        if not node:
            return
            
        node_type = node.type
        
        # Process basic syntax elements
        if node_type in ('string_literal', 'number_literal', 'boolean_literal'):
            features['literals'].append({
                'type': node_type,
                'value': source_code[node.start_byte:node.end_byte],
                'start': node.start_point,
                'end': node.end_point
            })
        elif node_type in ('identifier', 'operator', 'keyword'):
            category = node_type + 's'  # pluralize for the feature category
            features[category].append({
                'value': source_code[node.start_byte:node.end_byte],
                'start': node.start_point,
                'end': node.end_point
            })
            
        # Recurse through children
        for child in node.children:
            self._process_tree_sitter_syntax(child, features, source_code)
    
    def _process_custom_syntax(self, node: Dict, features: Dict):
        """Process custom parser syntax nodes."""
        if isinstance(node, dict):
            node_type = node.get('type')
            if node_type in features:
                features[node_type].append(node)
            
            for value in node.values():
                self._process_custom_syntax(value, features)
        elif isinstance(node, list):
            for item in node:
                self._process_custom_syntax(item, features)
    
    def clear_cache(self):
        """Clear the feature extractor cache."""
        self._cache.clear() 