"""Tree-sitter based code parsing."""

from typing import Dict, Set, Optional, Any
import tree_sitter
from tree_sitter import Language, Parser
import os
from utils.logger import log
from parsers.base_parser import BaseParser, ParserResult
from utils.error_handling import (
    handle_errors,
    ProcessingError,
    ErrorBoundary
)
from config import parser_config

class TreeSitterParser(BaseParser):
    """Tree-sitter implementation of the base parser."""
    
    def __init__(self):
        self._parsers: Dict[str, Parser] = {}
        self._languages: Dict[str, Language] = {}
        self._supported_languages: Set[str] = set()
        
        with ErrorBoundary("Tree-sitter initialization"):
            self._initialize_languages()
    
    @handle_errors(error_types=ProcessingError)
    def _initialize_languages(self):
        """Initialize supported languages."""
        languages_dir = os.path.join(os.path.dirname(__file__), 'languages')
        
        with ErrorBoundary("language loading"):
            # Load language definitions
            for lang_file in os.listdir(languages_dir):
                if lang_file.endswith('.so'):
                    lang_name = lang_file.split('.')[0]
                    try:
                        lang_path = os.path.join(languages_dir, lang_file)
                        self._languages[lang_name] = Language(lang_path, lang_name)
                        self._supported_languages.add(lang_name)
                        
                        # Initialize parser
                        parser = Parser()
                        parser.set_language(self._languages[lang_name])
                        self._parsers[lang_name] = parser
                        
                    except Exception as e:
                        log(f"Failed to load language {lang_name}: {e}", level="error")
    
    @handle_errors(error_types=ProcessingError)
    def parse(self, content: str, language: Optional[str] = None) -> Optional[ParserResult]:
        """Parse code content using tree-sitter."""
        if not language or language not in self._supported_languages:
            return None
            
        with ErrorBoundary("code parsing"):
            parser = self._parsers.get(language)
            if not parser:
                return None
            
            tree = parser.parse(bytes(content, 'utf8'))
            ast = self._convert_tree_to_dict(tree.root_node)
            
            return ParserResult(
                language=language,
                ast=ast,
                features=self._extract_features(ast)
            )
    
    @handle_errors(error_types=ProcessingError)
    def _convert_tree_to_dict(self, node) -> Dict[str, Any]:
        """Convert tree-sitter node to dictionary."""
        with ErrorBoundary("AST conversion"):
            result = {
                'type': node.type,
                'start_point': node.start_point,
                'end_point': node.end_point
            }
            
            if len(node.children) == 0:
                result['text'] = node.text.decode('utf8')
            else:
                result['children'] = [
                    self._convert_tree_to_dict(child)
                    for child in node.children
                ]
            
            return result
    
    @handle_errors(error_types=ProcessingError)
    def _extract_features(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Extract code features from AST."""
        with ErrorBoundary("feature extraction"):
            features = {
                'function_count': 0,
                'class_count': 0,
                'import_count': 0,
                'max_depth': 0
            }
            
            def traverse(node: Dict[str, Any], depth: int = 0):
                node_type = node.get('type', '')
                
                if node_type in {'function_definition', 'method_definition'}:
                    features['function_count'] += 1
                elif node_type in {'class_definition'}:
                    features['class_count'] += 1
                elif node_type in {'import_statement'}:
                    features['import_count'] += 1
                
                features['max_depth'] = max(features['max_depth'], depth)
                
                for child in node.get('children', []):
                    traverse(child, depth + 1)
            
            traverse(ast)
            return features
    
    @handle_errors(error_types=ProcessingError)
    def get_supported_languages(self) -> Set[str]:
        """Get set of supported languages."""
        return self._supported_languages.copy() 