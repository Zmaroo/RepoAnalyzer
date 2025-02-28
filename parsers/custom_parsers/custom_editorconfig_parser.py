"""
Custom EditorConfig parser.

This module implements a lightweight parser for EditorConfig files.
It extracts section headers (e.g. [*] or [*.py]) and
key-value property lines beneath each section.
"""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType
from parsers.models import EditorconfigNode, PatternType
from parsers.query_patterns.editorconfig import EDITORCONFIG_PATTERNS
from utils.logger import log

class EditorconfigParser(BaseParser):
    """Parser for EditorConfig files."""
    
    def __init__(self, language_id: str = "editorconfig", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        # Use the shared helper from BaseParser to compile the regex patterns.
        self.patterns = self._compile_patterns(EDITORCONFIG_PATTERNS)
    
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
    ) -> EditorconfigNode:
        """Create a standardized EditorConfig AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return EditorconfigNode(**node_dict)

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse EditorConfig content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "editorconfig",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
            current_section = None
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Process comments.
                if comment_match := self.patterns['comment'].match(line):
                    node = self._create_node(
                        "comment",
                        line_start,
                        line_end,
                        content=comment_match.group(1).strip()
                    )
                    if current_section:
                        current_section.children.append(node)
                    else:
                        ast.children.append(node)
                    continue
                
                # Process sections.
                if section_match := self.patterns['section'].match(line):
                    current_section = self._create_node(
                        "section",
                        line_start,
                        line_end,
                        glob=section_match.group(1).strip(),
                        properties=[]
                    )
                    ast.children.append(current_section)
                    continue
                
                # Process properties.
                if current_section and (property_match := self.patterns['property'].match(line)):
                    node = self._create_node(
                        "property",
                        line_start,
                        line_end,
                        key=property_match.group(1).strip(),
                        value=property_match.group(2).strip()
                    )
                    current_section.properties.append(node)
                    current_section.children.append(node)
                    continue
                
                # Process semantic patterns.
                for pattern_name, pattern in self.patterns.items():
                    if pattern_name in ['comment', 'section', 'property']:
                        continue
                    
                    if match := pattern.match(line):
                        category = next(
                            cat for cat, patterns in EDITORCONFIG_PATTERNS.items()
                            if pattern_name in patterns
                        )
                        node_data = EDITORCONFIG_PATTERNS[category][pattern_name].extract(match)
                        node = self._create_node(
                            pattern_name,
                            line_start,
                            line_end,
                            **node_data
                        )
                        if current_section:
                            current_section.children.append(node)
                        else:
                            ast.children.append(node)
                        break
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing EditorConfig content: {e}", level="error")
            return EditorconfigNode(
                type="editorconfig",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__
            
    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract configuration patterns from EditorConfig files for repository learning.
        
        Args:
            source_code: The content of the EditorConfig file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        try:
            # Parse the source first to get a structured representation
            ast_dict = self._parse_source(source_code)
            
            # Extract section patterns
            sections = self._extract_section_patterns(ast_dict)
            for section in sections:
                patterns.append({
                    'name': f'config_section_{section["glob"]}',
                    'content': section["content"],
                    'pattern_type': PatternType.CODE_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.85,
                    'metadata': {
                        'type': 'config_section',
                        'glob': section["glob"],
                        'properties': section["properties"]
                    }
                })
            
            # Extract property patterns
            property_patterns = self._extract_property_patterns(ast_dict)
            for prop in property_patterns:
                patterns.append({
                    'name': f'config_property_{prop["key"]}',
                    'content': f'{prop["key"]}={prop["value"]}',
                    'pattern_type': PatternType.CODE_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.8,
                    'metadata': {
                        'type': 'config_property',
                        'key': prop["key"],
                        'value': prop["value"],
                        'section': prop.get("section", "*")
                    }
                })
                
            # Extract common configuration patterns
            common_patterns = self._extract_common_patterns(ast_dict)
            for common in common_patterns:
                patterns.append({
                    'name': f'config_pattern_{common["name"]}',
                    'content': common["content"],
                    'pattern_type': PatternType.CODE_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.9,
                    'metadata': {
                        'type': 'common_config',
                        'name': common["name"],
                        'properties': common["properties"]
                    }
                })
                
        except Exception as e:
            log(f"Error extracting EditorConfig patterns: {e}", level="error")
            
        return patterns
        
    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        sections = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'section':
                properties = []
                for prop in node.get('properties', []):
                    properties.append({
                        'key': prop.get('key', ''),
                        'value': prop.get('value', '')
                    })
                
                sections.append({
                    'glob': node.get('glob', ''),
                    'content': str(node),  # Simplified - could extract actual content
                    'properties': properties
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return sections
        
    def _extract_property_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract property patterns from the AST."""
        properties = []
        
        def process_node(node, current_section=None):
            if isinstance(node, dict):
                if node.get('type') == 'property':
                    prop = {
                        'key': node.get('key', ''),
                        'value': node.get('value', '')
                    }
                    if current_section:
                        prop['section'] = current_section
                    properties.append(prop)
                elif node.get('type') == 'section':
                    # Process properties in this section context
                    for child in node.get('children', []):
                        process_node(child, node.get('glob', ''))
                    return
            
            # Process children
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child, current_section)
                
        process_node(ast)
        return properties
        
    def _extract_common_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract common configuration patterns from the AST."""
        common_patterns = []
        
        # Check for common indent style configuration
        indent_style = None
        indent_size = None
        
        def find_indent_config(node):
            nonlocal indent_style, indent_size
            
            if isinstance(node, dict):
                if node.get('type') == 'property':
                    if node.get('key') == 'indent_style':
                        indent_style = node.get('value')
                    elif node.get('key') == 'indent_size':
                        indent_size = node.get('value')
                
                # Check children
                for child in node.get('children', []):
                    find_indent_config(child)
        
        # Find indent configuration
        find_indent_config(ast)
        
        # Create indent pattern if found
        if indent_style or indent_size:
            properties = []
            if indent_style:
                properties.append({'key': 'indent_style', 'value': indent_style})
            if indent_size:
                properties.append({'key': 'indent_size', 'value': indent_size})
                
            common_patterns.append({
                'name': 'indentation',
                'content': f"indent_style={indent_style or 'not_set'}, indent_size={indent_size or 'not_set'}",
                'properties': properties
            })
            
        return common_patterns