"""Custom parser for AsciiDoc with enhanced documentation features."""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
from parsers.base_parser import BaseParser
from parsers.models import AsciidocNode, PatternType
from parsers.types import FileType, ParserType
from parsers.query_patterns.asciidoc import ASCIIDOC_PATTERNS
from utils.logger import log
import re

class AsciidocParser(BaseParser):
    """Parser for AsciiDoc documents."""
    
    def __init__(self, language_id: str = "asciidoc", file_type: Optional[FileType] = None):
        # Assume AsciiDoc files are documentation files by default
        from parsers.types import FileType
        if file_type is None:
            file_type = FileType.DOC
        # Set parser_type to CUSTOM so that the base class creates a CustomFeatureExtractor
        super().__init__(language_id, file_type or FileType.DOCUMENTATION, parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(ASCIIDOC_PATTERNS)
    
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
    ) -> AsciidocNode:
        """Create a standardized AsciiDoc AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return AsciidocNode(**node_dict)

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse AsciiDoc source code and produce an AST.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        try:
            ast = self._create_node("asciidoc_document", [0, 0], [0, 0], children=[])
            # Your custom parsing logic here...
            # For each line, create nodes as needed.
            lines = source_code.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("="):
                    # Example: treat lines starting with "=" as headers.
                    node = self._create_node("header", [i, 0], [i, len(line)], title=line.strip("="))
                    ast["children"].append(node)
            return ast
        except Exception as e:
            log(f"Error parsing AsciiDoc content: {e}", level="error")
            fallback = self._create_node("asciidoc_document", [0, 0], [0, 0], error=str(e), children=[])
            return fallback
            
    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract documentation patterns from AsciiDoc files for repository learning.
        
        Args:
            source_code: The content of the AsciiDoc file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        try:
            # Parse the source first to get a structured representation
            ast = self._parse_source(source_code)
            
            # Extract header patterns (document structure)
            headers = self._extract_header_patterns(ast)
            for header in headers:
                patterns.append({
                    'name': f'doc_header_{header["level"]}',
                    'content': header["content"],
                    'pattern_type': PatternType.DOCUMENTATION_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.8,
                    'metadata': {
                        'type': 'header',
                        'level': header["level"]
                    }
                })
            
            # Extract section patterns
            sections = self._extract_section_patterns(ast)
            for section in sections:
                patterns.append({
                    'name': f'doc_section_{section["title"]}',
                    'content': section["content"],
                    'pattern_type': PatternType.DOCUMENTATION_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.75,
                    'metadata': {
                        'type': 'section',
                        'title': section["title"]
                    }
                })
                
            # Extract list patterns for structure
            lists = self._extract_list_patterns(ast)
            for list_pattern in lists:
                patterns.append({
                    'name': f'doc_list_{list_pattern["type"]}',
                    'content': list_pattern["content"],
                    'pattern_type': PatternType.DOCUMENTATION_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.7,
                    'metadata': {
                        'type': 'list',
                        'list_type': list_pattern["type"]
                    }
                })
                
        except Exception as e:
            log(f"Error extracting AsciiDoc patterns: {e}", level="error")
            
        return patterns
        
    def _extract_header_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract header patterns from the AST."""
        headers = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'header':
                headers.append({
                    'level': 1,  # Simplified - could extract actual level
                    'content': node.get('title', ''),
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return headers
        
    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        sections = []
        
        def get_content_between(start_point, end_point):
            # Simple method to get content between two points in the document
            # This is a placeholder - in a real implementation, you'd use the actual source code
            return f"Content from {start_point} to {end_point}"
        
        def process_node(node, current_section=None):
            if isinstance(node, dict) and node.get('type') == 'header':
                if current_section:
                    # End the current section
                    sections.append({
                        'title': current_section.get('title', ''),
                        'level': 1,  # Simplified level
                        'content': get_content_between(
                            current_section.get('start_point', [0, 0]),
                            node.get('start_point', [0, 0])
                        )
                    })
                
                # Start a new section
                current_section = node
            
            # Process children with current section context
            for child in node.get('children', []):
                process_node(child, current_section)
                
        process_node(ast)
        return sections
        
    def _extract_list_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract list patterns from the AST."""
        lists = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') in ['list', 'ulist', 'olist']:
                lists.append({
                    'type': node.get('type'),
                    'content': str(node),  # Simplified - could extract actual content
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return lists 