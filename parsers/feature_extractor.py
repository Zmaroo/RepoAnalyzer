"""Feature extraction implementations."""

from typing import Dict, Any, List, Optional, Union, Generator, Tuple
from tree_sitter import Node, Query, QueryError, Parser, Language, TreeCursor
from .types import FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics, ExtractedFeatures
from parsers.models import QueryResult, FileClassification
from parsers.language_support import language_registry
from utils.logger import log
from parsers.pattern_processor import PatternProcessor, PatternMatch, PatternCategory, pattern_processor
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
            
            self._queries.setdefault(category, {})[name] = {
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

    def _extract_documentation(self, features: Dict[str, Any]) -> Documentation:
        """Extract documentation features from parsed content.
        
        This extracts docstrings, comments, TODOs, and other documentation elements
        from the parsed features.
        """
        doc_features = features.get(PatternCategory.DOCUMENTATION.value, {})
        
        # Initialize Documentation object
        documentation = Documentation()
        
        # Extract docstrings
        if 'docstring' in doc_features:
            documentation.docstrings = doc_features['docstring']
            
            # Combine docstring content
            for doc in documentation.docstrings:
                if 'text' in doc:
                    documentation.content += doc['text'] + "\n"
        
        # Extract comments
        if 'comment' in doc_features:
            documentation.comments = doc_features['comment']
        
        # Extract TODOs
        for comment_type in ['todo', 'fixme', 'note', 'warning']:
            if comment_type in doc_features:
                documentation.todos.extend(doc_features[comment_type])
        
        # Extract metadata (author, version, etc.)
        if 'metadata' in doc_features:
            documentation.metadata = {
                item.get('key', ''): item.get('value', '')
                for item in doc_features.get('metadata', [])
                if 'key' in item and 'value' in item
            }
            
        return documentation
    
    def _calculate_metrics(self, features: Dict[str, Any], source_code: str) -> ComplexityMetrics:
        """Calculate code complexity metrics based on extracted features.
        
        This includes:
        - Cyclomatic complexity
        - Cognitive complexity
        - Lines of code metrics
        - Basic Halstead metrics
        """
        metrics = ComplexityMetrics()
        
        # Count lines of code
        lines = source_code.splitlines()
        metrics.lines_of_code = {
            'total': len(lines),
            'code': len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'comment': len([l for l in lines if l.strip() and l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'blank': len([l for l in lines if not l.strip()])
        }
        
        # Extract syntax features for complexity calculation
        syntax_features = features.get(PatternCategory.SYNTAX.value, {})
        
        # Calculate cyclomatic complexity (based on branches)
        branch_types = ['if', 'for', 'while', 'case', 'catch', 'switch']
        branch_count = 0
        
        for branch_type in branch_types:
            if branch_type in syntax_features:
                branch_count += len(syntax_features[branch_type])
                
        # Basic cyclomatic complexity: branches + 1
        metrics.cyclomatic = branch_count + 1
        
        # Estimate cognitive complexity (nesting levels * branches)
        nesting_level = 0
        for branch_match in syntax_features.get('if', []) + syntax_features.get('for', []) + syntax_features.get('while', []):
            if 'nesting_level' in branch_match:
                nesting_level = max(nesting_level, branch_match['nesting_level'])
        
        metrics.cognitive = branch_count * (nesting_level + 1)
        
        # Basic Halstead metrics
        halstead = {
            'n1': 0,  # unique operators
            'n2': 0,  # unique operands
            'N1': 0,  # total operators
            'N2': 0,  # total operands
        }
        
        # Extract operators and operands if available
        if 'operator' in syntax_features:
            operator_texts = set()
            for op in syntax_features['operator']:
                if 'text' in op:
                    operator_texts.add(op['text'])
                    halstead['N1'] += 1
            halstead['n1'] = len(operator_texts)
            
        # If we have at least some values, calculate derived metrics
        if halstead['n1'] > 0 and halstead['n2'] > 0:
            vocabulary = halstead['n1'] + halstead['n2']
            length = halstead['N1'] + halstead['N2']
            volume = length * (vocabulary.bit_length() if vocabulary > 0 else 0)
            halstead['volume'] = volume
            
        metrics.halstead = halstead
        
        # Maintainability index (simple estimate)
        if metrics.cyclomatic > 0:
            # Basic MI formula: 171 - 5.2 * ln(volume) - 0.23 * cyclomatic - 16.2 * ln(loc)
            code_lines = metrics.lines_of_code['code']
            if code_lines > 0 and 'volume' in halstead:
                import math
                metrics.maintainability_index = max(0, min(100, 171 - 5.2 * math.log(halstead['volume']) - 
                                                          0.23 * metrics.cyclomatic - 
                                                          16.2 * math.log(code_lines)))
        
        return metrics

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
            features = {category.value: {} for category in PatternCategory}
            
            # [3.2.2.2] Process each category
            for category_enum in PatternCategory:
                category = category_enum.value
                if category not in self._patterns:
                    continue
                    
                category_features = {}
                
                # [3.2.2.3] Process each regex pattern
                for pattern_name, pattern in self._patterns[category].items():
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
                                try:
                                    extracted = pattern.extract(result)
                                    if extracted:
                                        result.update(extracted)
                                except Exception as e:
                                    log(f"Error in pattern extraction: {e}", level="error")
                                
                            matches.append(result)
                            
                        if matches:
                            category_features[pattern_name] = matches
                
                features[category] = category_features
            
            # Extract AST nodes if available
            if ast and 'nodes' in ast:
                self._process_ast_nodes(ast['nodes'], features)
                
            # [3.2.2.5] Return standardized features
            # RETURNS: [models.py] ExtractedFeatures
            documentation = self._extract_documentation(features)
            metrics = self._calculate_metrics(features, source_code)
            
            return ExtractedFeatures(
                features=features,
                documentation=documentation,
                metrics=metrics
            )
            
        except Exception as e:
            log(f"Error extracting features: {e}", level="error")
            return ExtractedFeatures()
            
    def _process_ast_nodes(self, nodes: List[Dict[str, Any]], features: Dict[str, Dict[str, Any]]) -> None:
        """Process AST nodes from a custom parser and add them to features."""
        if not nodes:
            return
            
        # Map node types to feature categories
        for node in nodes:
            node_type = node.get('type')
            if not node_type:
                continue
                
            # Determine which category this node belongs to
            category = self._get_category_for_node_type(node_type)
            if not category:
                continue
                
            # Add node to appropriate category
            if node_type not in features[category]:
                features[category][node_type] = []
                
            features[category][node_type].append(node)
    
    def _get_category_for_node_type(self, node_type: str) -> Optional[str]:
        """Map a node type to a feature category."""
        from parsers.models import PATTERN_CATEGORIES
        
        # Check each category's patterns
        for category in PatternCategory:
            category_value = category.value
            for file_type in PATTERN_CATEGORIES.get(category, {}):
                if node_type in PATTERN_CATEGORIES[category][file_type]:
                    return category_value
        
        # Default categorization based on node type
        if node_type in ['comment', 'docstring', 'javadoc']:
            return PatternCategory.DOCUMENTATION.value
        elif node_type in ['import', 'include', 'namespace', 'module']:
            return PatternCategory.STRUCTURE.value
        elif node_type in ['function', 'class', 'method', 'constructor']:
            return PatternCategory.SYNTAX.value
        elif node_type in ['type', 'variable', 'parameter']:
            return PatternCategory.SEMANTICS.value
            
        return None
            
    def _extract_documentation(self, features: Dict[str, Any]) -> Documentation:
        """Extract documentation features from parsed content."""
        # Reuse same logic as TreeSitterFeatureExtractor
        doc_features = features.get(PatternCategory.DOCUMENTATION.value, {})
        
        # Initialize Documentation object
        documentation = Documentation()
        
        # Extract docstrings
        if 'docstring' in doc_features:
            documentation.docstrings = doc_features['docstring']
            
            # Combine docstring content
            for doc in documentation.docstrings:
                if 'text' in doc:
                    documentation.content += doc['text'] + "\n"
        
        # Extract comments
        if 'comment' in doc_features:
            documentation.comments = doc_features['comment']
        
        # Extract TODOs
        for comment_type in ['todo', 'fixme', 'note', 'warning']:
            if comment_type in doc_features:
                documentation.todos.extend(doc_features[comment_type])
        
        # Extract metadata (author, version, etc.)
        if 'metadata' in doc_features:
            documentation.metadata = {
                item.get('key', ''): item.get('value', '')
                for item in doc_features.get('metadata', [])
                if 'key' in item and 'value' in item
            }
            
        return documentation
    
    def _calculate_metrics(self, features: Dict[str, Any], source_code: str) -> ComplexityMetrics:
        """Calculate code complexity metrics based on extracted features."""
        # Reuse same logic as TreeSitterFeatureExtractor
        metrics = ComplexityMetrics()
        
        # Count lines of code
        lines = source_code.splitlines()
        metrics.lines_of_code = {
            'total': len(lines),
            'code': len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'comment': len([l for l in lines if l.strip() and l.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))]),
            'blank': len([l for l in lines if not l.strip()])
        }
        
        # Basic complexity metrics for custom parsers
        # (more limited than tree-sitter but still useful)
        syntax_features = features.get(PatternCategory.SYNTAX.value, {})
        
        # Count branches
        branch_count = 0
        for branch_type in ['if', 'for', 'while', 'case', 'switch']:
            if branch_type in syntax_features:
                branch_count += len(syntax_features[branch_type])
        
        metrics.cyclomatic = branch_count + 1
        metrics.cognitive = branch_count
        
        return metrics