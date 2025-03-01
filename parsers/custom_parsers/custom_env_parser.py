"""
Custom .env file parser.

This parser processes .env files by extracting key=value pairs.
Comments (lines starting with #) are skipped (or can be used as documentation).
"""

from typing import Dict, List, Any, Optional, Tuple
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.models import EnvNode, PatternType
from parsers.query_patterns.env import ENV_PATTERNS
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError
import re

class EnvParser(BaseParser):
    """Parser for .env files."""
    
    def __init__(self, language_id: str = "env", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        # Use the shared helper to compile regex patterns.
        self.patterns = self._compile_patterns(ENV_PATTERNS)
    
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
    ) -> EnvNode:
        """Create a standardized ENV AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return EnvNode(**node_dict)

    def _process_value(self, value: str) -> Tuple[str, str]:
        """Process a value that might be quoted or multiline."""
        if value.startswith('"') or value.startswith("'"):
            quote = value[0]
            if value.endswith(quote) and len(value) > 1:
                return value[1:-1], "quoted"
        elif value.startswith('`') and value.endswith('`'):
            return value[1:-1], "multiline"
        return value, "raw"

    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse env content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        with ErrorBoundary("env file parsing"):
            try:
                lines = source_code.splitlines()
                ast = self._create_node(
                    "env_file",
                    [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0],
                    children=[]
                )
                
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    
                    # Skip empty lines
                    if not line.strip():
                        continue
                    
                    # Process comments
                    if comment_match := self.patterns['comment'].match(line):
                        node = self._create_node(
                            "comment",
                            line_start,
                            line_end,
                            content=comment_match.group(1).strip()
                        )
                        ast.children.append(node)
                        continue
                    
                    # Process exports
                    if export_match := self.patterns['export'].match(line):
                        name, raw_value = export_match.groups()
                        value, value_type = self._process_value(raw_value)
                        
                        node = self._create_node(
                            "export",
                            line_start,
                            line_end,
                            name=name,
                            value=value,
                            value_type=value_type
                        )
                        ast.children.append(node)
                        continue
                    
                    # Process variables
                    if var_match := self.patterns['variable'].match(line):
                        name, raw_value = var_match.groups()
                        value, value_type = self._process_value(raw_value)
                        
                        node = self._create_node(
                            "variable",
                            line_start,
                            line_end,
                            name=name,
                            value=value,
                            value_type=value_type
                        )
                        ast.children.append(node)
                        
                        # Process semantic patterns
                        for pattern_name in ['url', 'path']:
                            if pattern_match := self.patterns[pattern_name].search(raw_value):
                                semantic_data = ENV_PATTERNS[PatternCategory.SEMANTICS][pattern_name].extract(pattern_match)
                                node.metadata["semantics"] = semantic_data
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:  # Use specific error types instead of broad Exception
                log(f"Error parsing ENV file: {str(e)}", level="error")
                # Return a minimal valid AST structure on error
                return self._create_node(
                    "env_file",
                    [0, 0],
                    [0, 0],
                    variables=[]
                )
            
    @handle_errors(error_types=(ParsingError, ProcessingError))
    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from env file content.
        
        Args:
            source_code: The content of the env file
            
        Returns:
            List of extracted pattern dictionaries
        """
        with ErrorBoundary("env pattern extraction"):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                ast_dict = self._parse_source(source_code)
                
                # Extract variable patterns
                variables = self._extract_variable_patterns(ast_dict)
                for variable in variables:
                    patterns.append({
                        'name': f'env_variable_{variable["name"]}',
                        'content': f'{variable["name"]}={variable["value"]}',
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'env_variable',
                            'name': variable["name"],
                            'value_type': variable["value_type"],
                            'is_export': variable.get("is_export", False)
                        }
                    })
                
                # Extract naming convention patterns
                naming_patterns = self._extract_naming_patterns(ast_dict)
                for naming in naming_patterns:
                    patterns.append({
                        'name': f'env_naming_{naming["pattern"]}',
                        'content': naming["examples"],
                        'pattern_type': PatternType.CODE_NAMING,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'naming_convention',
                            'pattern': naming["pattern"],
                            'examples': naming["examples"].split(', ')
                        }
                    })
                    
                # Extract common env configurations
                config_patterns = self._extract_config_patterns(ast_dict)
                for config in config_patterns:
                    patterns.append({
                        'name': f'env_config_{config["category"]}',
                        'content': config["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'env_config',
                            'category': config["category"],
                            'variables': config["variables"]
                        }
                    })
                    
                return patterns
                
            except (ValueError, KeyError, TypeError) as e:  # Use specific error types instead of broad Exception
                log(f"Error extracting patterns from ENV file: {str(e)}", level="error")
                return []
        
    def _extract_variable_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract variable patterns from the AST."""
        variables = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') in ('variable', 'export'):
                    variables.append({
                        'name': node.get('name', ''),
                        'value': node.get('value', ''),
                        'value_type': node.get('value_type', 'raw'),
                        'is_export': node.get('type') == 'export'
                    })
            
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return variables
        
    def _extract_naming_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract naming convention patterns from the AST."""
        # Count how many variables follow specific naming conventions
        snake_case = []
        screaming_snake_case = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') in ('variable', 'export'):
                name = node.get('name', '')
                if re.match(r'^[a-z][a-z0-9_]*$', name):
                    snake_case.append(name)
                elif re.match(r'^[A-Z][A-Z0-9_]*$', name):
                    screaming_snake_case.append(name)
            
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        
        patterns = []
        # Add patterns only if we have enough examples
        if len(snake_case) >= 2:
            patterns.append({
                'pattern': 'snake_case',
                'examples': ', '.join(snake_case[:3])
            })
            
        if len(screaming_snake_case) >= 2:
            patterns.append({
                'pattern': 'SCREAMING_SNAKE_CASE',
                'examples': ', '.join(screaming_snake_case[:3])
            })
            
        return patterns
        
    def _extract_config_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract common configuration patterns from the AST."""
        # Look for common groups of environment variables
        database_vars = []
        api_vars = []
        auth_vars = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') in ('variable', 'export'):
                name = node.get('name', '')
                
                # Check for database variables
                if any(keyword in name.upper() for keyword in ['DB', 'DATABASE', 'SQL', 'POSTGRES', 'MONGO']):
                    database_vars.append({'name': name, 'value': node.get('value', '')})
                    
                # Check for API variables
                elif any(keyword in name.upper() for keyword in ['API', 'ENDPOINT', 'URL', 'HOST']):
                    api_vars.append({'name': name, 'value': node.get('value', '')})
                    
                # Check for auth variables
                elif any(keyword in name.upper() for keyword in ['AUTH', 'TOKEN', 'SECRET', 'KEY', 'PASSWORD']):
                    auth_vars.append({'name': name, 'value': node.get('value', '')})
            
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        
        patterns = []
        # Add patterns only if we have enough related variables
        if len(database_vars) >= 2:
            patterns.append({
                'category': 'database',
                'content': ', '.join(v['name'] for v in database_vars),
                'variables': database_vars
            })
            
        if len(api_vars) >= 2:
            patterns.append({
                'category': 'api',
                'content': ', '.join(v['name'] for v in api_vars),
                'variables': api_vars
            })
            
        if len(auth_vars) >= 2:
            patterns.append({
                'category': 'authentication',
                'content': ', '.join(v['name'] for v in auth_vars),
                'variables': auth_vars
            })
            
        return patterns