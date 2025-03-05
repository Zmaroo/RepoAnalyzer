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
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, ErrorSeverity
import re
from collections import Counter

class EditorconfigParser(BaseParser):
    """Parser for EditorConfig files."""
    
    def __init__(self, language_id: str = "editorconfig", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        
        # Compile regex patterns for parsing
        self.section_pattern = re.compile(r'^\s*\[(.*)\]\s*$')
        self.property_pattern = re.compile(r'^\s*([^=]+?)\s*=\s*(.*?)\s*$')
        self.comment_pattern = re.compile(r'^\s*[#;](.*)$')
    
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

    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse EditorConfig content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        with ErrorBoundary(operation_name="EditorConfig parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                lines = source_code.splitlines()
                ast = self._create_node(
                    "editorconfig_file",
                    [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0],
                    children=[]
                )
                
                current_section = None
                current_comments = []
                
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    
                    # Skip empty lines but track them
                    if not line.strip():
                        if current_comments:
                            # Create a comment node for accumulated comments
                            ast.children.append(
                                self._create_node(
                                    "comment",
                                    [i - len(current_comments), 0],
                                    [i - 1, len(current_comments[-1])],
                                    content="\n".join(current_comments)
                                )
                            )
                            current_comments = []
                        continue
                    
                    # Process comments
                    if comment_match := self.comment_pattern.match(line):
                        current_comments.append(comment_match.group(1).strip())
                        continue
                    
                    # Process section headers
                    if section_match := self.section_pattern.match(line):
                        pattern = section_match.group(1)
                        
                        # Create the section node
                        current_section = self._create_node(
                            "section",
                            line_start,
                            line_end,
                            pattern=pattern,
                            properties=[],
                            children=[]
                        )
                        
                        # Attach comments to section
                        if current_comments:
                            current_section.metadata["comments"] = current_comments
                            current_comments = []
                            
                        ast.children.append(current_section)
                        continue
                    
                    # Process properties
                    if property_match := self.property_pattern.match(line):
                        key, value = property_match.groups()
                        
                        # Create the property node
                        property_node = self._create_node(
                            "property",
                            line_start,
                            line_end,
                            key=key,
                            value=value
                        )
                        
                        # Attach comments to property
                        if current_comments:
                            property_node.metadata["comments"] = current_comments
                            current_comments = []
                        
                        # Add to current section or to root
                        if current_section:
                            current_section.children.append(property_node)
                        else:
                            ast.children.append(property_node)
                
                # Process any trailing comments
                if current_comments:
                    ast.children.append(
                        self._create_node(
                            "comment",
                            [len(lines) - len(current_comments), 0],
                            [len(lines) - 1, len(current_comments[-1])],
                            content="\n".join(current_comments)
                        )
                    )
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing EditorConfig file: {e}", level="error")
                return self._create_node(
                    "editorconfig_file",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__
            
    @handle_errors(error_types=(ProcessingError,))
    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract configuration patterns from EditorConfig files for repository learning.
        
        Args:
            source_code: The content of the EditorConfig file
            
        Returns:
            List of extracted patterns with metadata
        """
        with ErrorBoundary(operation_name="EditorConfig pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                ast = self._parse_source(source_code)
                
                # Extract section patterns (file patterns)
                section_patterns = self._extract_section_patterns(ast)
                for section in section_patterns:
                    patterns.append({
                        'name': f'editorconfig_section_{section["pattern_type"]}',
                        'content': section["pattern"],
                        'pattern_type': PatternType.CONFIG_PATTERN,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'file_pattern',
                            'pattern': section["pattern"],
                            'pattern_type': section["pattern_type"]
                        }
                    })
                
                # Extract property patterns (settings)
                property_patterns = self._extract_property_patterns(ast)
                for prop in property_patterns:
                    patterns.append({
                        'name': f'editorconfig_property_{prop["key"]}',
                        'content': f'{prop["key"]} = {prop["value"]}',
                        'pattern_type': PatternType.CONFIG_PROPERTY,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'property',
                            'key': prop["key"],
                            'value': prop["value"],
                            'frequency': prop["frequency"]
                        }
                    })
                
                # Extract style convention patterns
                style_patterns = self._extract_style_conventions(ast)
                for style in style_patterns:
                    patterns.append({
                        'name': f'editorconfig_style_{style["type"]}',
                        'content': style["description"],
                        'pattern_type': PatternType.STYLE_CONVENTION,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'style_convention',
                            'convention_type': style["type"],
                            'settings': style["settings"]
                        }
                    })
                
                return patterns
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error extracting EditorConfig patterns: {e}", level="error")
                return []
        
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
                    'pattern': node.get('pattern', ''),
                    'pattern_type': PatternType.CODE_STRUCTURE,
                    'glob': node.get('glob', ''),
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
                        'value': node.get('value', ''),
                        'frequency': Counter(node.get('key', ''))['']
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
        
    def _extract_style_conventions(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract style convention patterns from the AST."""
        style_patterns = []
        
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
            style_patterns.append({
                'type': 'indentation',
                'description': f"indent_style={indent_style or 'not_set'}, indent_size={indent_size or 'not_set'}",
                'settings': {
                    'indent_style': indent_style,
                    'indent_size': indent_size
                }
            })
            
        return style_patterns