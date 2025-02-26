"""
Custom parser for the Cobalt programming language.
"""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
from parsers.base_parser import BaseParser
from parsers.models import CobaltNode, PatternType
from parsers.query_patterns.cobalt import COBALT_PATTERNS
from parsers.types import PatternCategory, FileType, ParserType
from utils.logger import log

class CobaltParser(BaseParser):
    """Parser for the Cobalt programming language."""
    
    def __init__(self, language_id: str = "cobalt", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CODE, parser_type=ParserType.CUSTOM)
        # Use the shared helper from BaseParser to compile the regex patterns.
        self.patterns = self._compile_patterns(COBALT_PATTERNS)
    
    def initialize(self) -> bool:
        """Initialize parser resources."""
        self._initialized = True
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> CobaltNode:
        """Create a standardized Cobalt AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return CobaltNode(**node_dict)

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse Cobalt content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "module",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
            current_doc = []
            current_scope = [ast]
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                # Process docstrings.
                if doc_match := self.patterns['docstring'].match(line):
                    current_doc.append(doc_match.group(1))
                    continue
                    
                # Process regular comments.
                if comment_match := self.patterns['comment'].match(line):
                    current_scope[-1].children.append(
                        self._create_node(
                            "comment",
                            line_start,
                            line_end,
                            content=comment_match.group(1)
                        )
                    )
                    continue
                
                # Handle scope openings.
                if line.strip().endswith("{"):
                    # Look for declarations that open new scopes.
                    for pattern_name in ['function', 'class', 'namespace']:
                        if pattern_name in self.patterns and (match := self.patterns[pattern_name].match(line)):
                            node_data = COBALT_PATTERNS[PatternCategory.SYNTAX][pattern_name].extract(match)
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                None,  # End point to be set when scope closes.
                                **node_data
                            )
                            if current_doc:
                                node.metadata["documentation"] = "\n".join(current_doc)
                                current_doc = []
                            current_scope[-1].children.append(node)
                            current_scope.append(node)
                            break
                
                elif line.strip() == "}":
                    if len(current_scope) > 1:
                        current_scope[-1].end_point = line_end
                        current_scope.pop()
                    continue
                
                # Flush accumulated docstrings before declarations.
                if current_doc and not line.strip().startswith("///"):
                    current_scope[-1].children.append(
                        self._create_node(
                            "docstring",
                            [i - len(current_doc), 0],
                            [i - 1, len(current_doc[-1])],
                            content="\n".join(current_doc)
                        )
                    )
                    current_doc = []
                
                # Process other declarations.
                for pattern_name, pattern in self.patterns.items():
                    if pattern_name in ['docstring', 'comment', 'function', 'class', 'namespace']:
                        continue
                    
                    if match := pattern.match(line):
                        category = next(
                            cat for cat, patterns in COBALT_PATTERNS.items()
                            if pattern_name in patterns
                        )
                        node_data = COBALT_PATTERNS[category][pattern_name].extract(match)
                        node = self._create_node(
                            pattern_name,
                            line_start,
                            line_end,
                            **node_data
                        )
                        current_scope[-1].children.append(node)
                        break
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing Cobalt content: {e}", level="error")
            return CobaltNode(
                type="module",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__
            
    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract code patterns from Cobalt files for repository learning.
        
        Args:
            source_code: The content of the Cobalt file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        try:
            # Parse the source first to get a structured representation
            ast_dict = self._parse_source(source_code)
            
            # Extract function patterns
            functions = self._extract_function_patterns(ast_dict)
            for function in functions:
                patterns.append({
                    'name': f'code_function_{function["name"]}',
                    'content': function["content"],
                    'pattern_type': PatternType.CODE_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.8,
                    'metadata': {
                        'type': 'function',
                        'name': function["name"],
                        'parameters': function.get("parameters", [])
                    }
                })
            
            # Extract class patterns
            classes = self._extract_class_patterns(ast_dict)
            for class_pattern in classes:
                patterns.append({
                    'name': f'code_class_{class_pattern["name"]}',
                    'content': class_pattern["content"],
                    'pattern_type': PatternType.CODE_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.85,
                    'metadata': {
                        'type': 'class',
                        'name': class_pattern["name"],
                        'methods': class_pattern.get("methods", [])
                    }
                })
                
            # Extract error handling patterns
            error_patterns = self._extract_error_handling_patterns(ast_dict)
            for error_pattern in error_patterns:
                patterns.append({
                    'name': f'error_handling_{error_pattern["type"]}',
                    'content': error_pattern["content"],
                    'pattern_type': PatternType.ERROR_HANDLING,
                    'language': self.language_id,
                    'confidence': 0.75,
                    'metadata': {
                        'type': 'error_handling',
                        'error_type': error_pattern["type"]
                    }
                })
                
            # Extract naming convention patterns
            naming_patterns = self._extract_naming_patterns(ast_dict)
            for naming_pattern in naming_patterns:
                patterns.append({
                    'name': f'naming_convention_{naming_pattern["category"]}',
                    'content': naming_pattern["examples"],
                    'pattern_type': PatternType.CODE_NAMING,
                    'language': self.language_id,
                    'confidence': 0.7,
                    'metadata': {
                        'type': 'naming_convention',
                        'category': naming_pattern["category"],
                        'pattern': naming_pattern["pattern"]
                    }
                })
                
        except Exception as e:
            log(f"Error extracting Cobalt patterns: {e}", level="error")
            
        return patterns
        
    def _extract_function_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract function patterns from the AST."""
        functions = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'function':
                functions.append({
                    'name': node.get('name', ''),
                    'content': str(node),  # Simplified - could extract actual content
                    'parameters': node.get('parameters', []),
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return functions
        
    def _extract_class_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract class patterns from the AST."""
        classes = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'class':
                # Extract methods within the class
                methods = []
                for child in node.get('children', []):
                    if child.get('type') == 'function':
                        methods.append({
                            'name': child.get('name', ''),
                            'parameters': child.get('parameters', [])
                        })
                
                classes.append({
                    'name': node.get('name', ''),
                    'content': str(node),  # Simplified - could extract actual content
                    'methods': methods,
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return classes
        
    def _extract_error_handling_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract error handling patterns from the AST."""
        error_patterns = []
        
        # In a real implementation, this would scan the AST for try/catch blocks or similar
        # This is a placeholder implementation
        error_patterns.append({
            'type': 'try_catch',
            'content': 'try { ... } catch (Error e) { ... }',  # Placeholder
            'start_point': [0, 0],
            'end_point': [0, 0]
        })
                
        return error_patterns
        
    def _extract_naming_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract naming convention patterns from the AST."""
        naming_patterns = []
        
        # This would analyze function and variable names to detect patterns
        # For now, we'll use a simplified implementation
        naming_patterns.append({
            'category': 'function',
            'pattern': r'[a-z][a-zA-Z0-9]*',  # camelCase
            'examples': 'doSomething, calculateTotal'
        })
        
        naming_patterns.append({
            'category': 'class',
            'pattern': r'[A-Z][a-zA-Z0-9]*',  # PascalCase
            'examples': 'UserAccount, DataProcessor'
        })
                
        return naming_patterns 