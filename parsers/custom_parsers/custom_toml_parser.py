"""Custom parser for TOML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.toml import TOML_PATTERNS
from parsers.models import TomlNode, PatternType
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, ErrorSeverity
import tomli
from collections import Counter

class TomlParser(BaseParser):
    """Parser for TOML files."""
    
    def __init__(self, language_id: str = "toml", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(TOML_PATTERNS)
    
    def initialize(self) -> bool:
        self._initialized = True
        return True
    
    def _create_node(
        self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs
    ) -> TomlNode:
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return TomlNode(**node_dict)
    
    def _process_value(self, value: Any, path: List[str], start_point: List[int]) -> TomlNode:
        value_data = self._create_node(
            "value", start_point,
            [start_point[0], start_point[1] + len(str(value))],
            path='.'.join(path),
            value_type=type(value).__name__,
            value=value
        )
        if isinstance(value, dict):
            value_data.type = "table"
            value_data.metadata["keys"] = list(value.keys())
            for key, val in value.items():
                child = self._process_value(
                    val, path + [key],
                    [start_point[0], start_point[1] + len(key) + 1]
                )
                value_data.children.append(child)
        elif isinstance(value, list):
            value_data.type = "array"
            value_data.metadata["length"] = len(value)
            for i, item in enumerate(value):
                child = self._process_value(
                    item, path + [f"[{i}]"],
                    [start_point[0], start_point[1] + i]
                )
                value_data.children.append(child)
        return value_data
    
    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse TOML content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        with ErrorBoundary(operation_name="TOML parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                lines = source_code.splitlines()
                ast = self._create_node(
                    "document", [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0]
                )
                current_comments = []
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    matched = False
                    for category in TOML_PATTERNS.values():
                        for pattern_name, pattern_obj in category.items():
                            if match := self.patterns[pattern_name].match(line):
                                node = self._create_node(
                                    pattern_name, line_start, line_end,
                                    **pattern_obj.extract(match)
                                )
                                if current_comments:
                                    node.metadata["comments"] = current_comments
                                    current_comments = []
                                ast.children.append(node)
                                matched = True
                                break
                        if matched:
                            break
                    if not matched and line.strip():
                        current_comments.append(line)
                try:
                    data = tomli.loads(source_code)
                    root_value = self._process_value(data, [], [0, 0])
                    ast.children.append(root_value)
                except (tomli.TOMLDecodeError, ValueError) as e:
                    log(f"Error parsing TOML content: {e}", level="error")
                    return TomlNode(
                        type="document", start_point=[0, 0], end_point=[0, 0],
                        error=str(e), children=[]
                    ).__dict__
                return ast.__dict__
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing TOML content: {e}", level="error")
                return TomlNode(
                    type="document", start_point=[0, 0], end_point=[0, 0],
                    error=str(e), children=[]
                ).__dict__
            
    @handle_errors(error_types=(ProcessingError,))
    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract configuration patterns from TOML files for repository learning.
        
        Args:
            source_code: The content of the TOML file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        with ErrorBoundary(operation_name="TOML pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                # Parse the source to get a structured representation
                ast = self._parse_source(source_code)
                
                # Extract table structure patterns
                table_patterns = self._extract_table_patterns(ast)
                for table in table_patterns:
                    patterns.append({
                        'name': f'toml_table_{table["name"]}',
                        'content': table["content"],
                        'pattern_type': PatternType.CONFIGURATION,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'table',
                            'name': table["name"],
                            'key_count': table.get("key_count", 0)
                        }
                    })
                
                # Extract key-value patterns
                kv_patterns = self._extract_key_value_patterns(ast)
                for kv in kv_patterns:
                    patterns.append({
                        'name': f'toml_key_value_{kv["key"]}',
                        'content': kv["content"],
                        'pattern_type': PatternType.CONFIGURATION,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'key_value',
                            'key': kv["key"],
                            'value_type': kv.get("value_type", "unknown")
                        }
                    })
                    
                # Extract array patterns
                array_patterns = self._extract_array_patterns(ast)
                for array in array_patterns:
                    patterns.append({
                        'name': f'toml_array_{array["name"]}',
                        'content': array["content"],
                        'pattern_type': PatternType.CONFIGURATION,
                        'language': self.language_id,
                        'confidence': 0.75,
                        'metadata': {
                            'type': 'array',
                            'name': array["name"],
                            'item_count': array.get("item_count", 0)
                        }
                    })
                    
                # Extract naming convention patterns
                naming_patterns = self._extract_naming_patterns(source_code)
                for pattern in naming_patterns:
                    patterns.append(pattern)
                    
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error extracting TOML patterns: {e}", level="error")
                
        return patterns
        
    def _extract_table_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract table patterns from the AST."""
        tables = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'table':
                    tables.append({
                        'name': node.get('path', 'unknown'),
                        'content': str(node),
                        'key_count': len(node.get('metadata', {}).get('keys', [])) if node.get('metadata') else 0
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return tables
        
    def _extract_key_value_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key-value patterns from the AST."""
        key_values = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'key_value':
                    key_values.append({
                        'key': node.get('key', 'unknown'),
                        'content': f"{node.get('key', '')} = {node.get('value', '')}",
                        'value_type': type(node.get('value', '')).__name__
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return key_values
        
    def _extract_array_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract array patterns from the AST."""
        arrays = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'array':
                    arrays.append({
                        'name': node.get('path', 'unknown'),
                        'content': str(node),
                        'item_count': node.get('metadata', {}).get('length', 0) if node.get('metadata') else 0
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return arrays
        
    def _extract_naming_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract naming convention patterns from the source code."""
        patterns = []
        
        # Extract snake_case vs camelCase naming convention
        snake_case_keys = 0
        camel_case_keys = 0
        
        import re
        snake_case_pattern = re.compile(r'^\s*([a-z][a-z0-9_]*[a-z0-9])\s*=')
        camel_case_pattern = re.compile(r'^\s*([a-z][a-zA-Z0-9]*[a-zA-Z0-9])\s*=')
        
        for line in source_code.splitlines():
            if snake_match := snake_case_pattern.match(line):
                if '_' in snake_match.group(1):
                    snake_case_keys += 1
            if camel_match := camel_case_pattern.match(line):
                if not '_' in camel_match.group(1) and any(c.isupper() for c in camel_match.group(1)):
                    camel_case_keys += 1
        
        # Determine the dominant naming convention
        if snake_case_keys > 0 or camel_case_keys > 0:
            dominant_style = 'snake_case' if snake_case_keys >= camel_case_keys else 'camelCase'
            confidence = 0.5 + 0.3 * (max(snake_case_keys, camel_case_keys) / max(1, snake_case_keys + camel_case_keys))
            
            patterns.append({
                'name': f'toml_naming_convention',
                'content': f"Naming convention: {dominant_style}",
                'pattern_type': PatternType.NAMING_CONVENTION,
                'language': self.language_id,
                'confidence': confidence,
                'metadata': {
                    'type': 'naming_convention',
                    'convention': dominant_style,
                    'snake_case_count': snake_case_keys,
                    'camel_case_count': camel_case_keys
                }
            })
            
        return patterns 