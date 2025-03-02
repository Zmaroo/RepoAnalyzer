"""Custom parser for AsciiDoc with enhanced documentation features."""
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from parsers.base_parser import BaseParser
from parsers.models import AsciidocNode, PatternType
from parsers.types import FileType, ParserType
from parsers.query_patterns.asciidoc import ASCIIDOC_PATTERNS
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, AsyncErrorBoundary
import re


class AsciidocParser(BaseParser):
    """Parser for AsciiDoc documents."""

    def __init__(self, language_id: str='asciidoc', file_type: Optional[
        FileType]=None):
        from parsers.types import FileType
        if file_type is None:
            file_type = FileType.DOC
        super().__init__(language_id, file_type or FileType.DOCUMENTATION,
            parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(ASCIIDOC_PATTERNS)

@handle_errors(error_types=(Exception,))
    def initialize(self) ->bool:
        """Initialize parser resources."""
        self._initialized = True
        return True

    def _create_node(self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs) ->AsciidocNode:
        """Create a standardized AsciiDoc AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point,
            **kwargs)
        return AsciidocNode(**node_dict)

    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) ->Dict[str, Any]:
        """Parse AsciiDoc source code and produce an AST.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        with ErrorBoundary(error_types=(ParsingError,), context=
            'AsciiDoc parsing'):
            try:
                ast = self._create_node('asciidoc_document', [0, 0], [0, 0],
                    children=[])
                lines = source_code.splitlines()
                for i, line in enumerate(lines):
                    if line.startswith('='):
                        node = self._create_node('header', [i, 0], [i, len(
                            line)], title=line.strip('='))
                        ast['children'].append(node)
                return ast
            except (ValueError, KeyError, TypeError) as e:
                log(f'Error parsing AsciiDoc content: {e}', level='error')
                fallback = self._create_node('asciidoc_document', [0, 0], [
                    0, 0], error=str(e), children=[])
                return fallback

    @handle_errors(error_types=(ProcessingError,))
    def extract_patterns(self, source_code: str) ->List[Dict[str, Any]]:
        """
        Extract documentation patterns from AsciiDoc files for repository learning.
        
        Args:
            source_code: The content of the AsciiDoc file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        with ErrorBoundary(error_types=(ProcessingError,), context=
            'AsciiDoc pattern extraction'):
            try:
                ast = self._parse_source(source_code)
                headers = self._extract_header_patterns(ast)
                for header in headers:
                    patterns.append({'name':
                        f"doc_header_{header['level']}", 'content': header[
                        'content'], 'pattern_type': PatternType.
                        DOCUMENTATION_STRUCTURE, 'language': self.
                        language_id, 'confidence': 0.8, 'metadata': {'type':
                        'header', 'level': header['level']}})
                sections = self._extract_section_patterns(ast)
                for section in sections:
                    patterns.append({'name':
                        f"doc_section_{section['title']}", 'content':
                        section['content'], 'pattern_type': PatternType.
                        DOCUMENTATION_STRUCTURE, 'language': self.
                        language_id, 'confidence': 0.75, 'metadata': {
                        'type': 'section', 'title': section['title']}})
                lists = self._extract_list_patterns(ast)
                for list_pattern in lists:
                    patterns.append({'name':
                        f"doc_list_{list_pattern['type']}", 'content':
                        list_pattern['content'], 'pattern_type':
                        PatternType.DOCUMENTATION_STRUCTURE, 'language':
                        self.language_id, 'confidence': 0.7, 'metadata': {
                        'type': 'list', 'list_type': list_pattern['type']}})
            except (ValueError, KeyError, TypeError) as e:
                log(f'Error extracting AsciiDoc patterns: {e}', level='error')
        return patterns

    def _extract_header_patterns(self, ast: Dict[str, Any]) ->List[Dict[str,
        Any]]:
        """Extract header patterns from the AST."""
        headers = []
@handle_errors(error_types=(Exception,))

        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'header':
                headers.append({'level': 1, 'content': node.get('title', ''
                    ), 'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])})
            for child in node.get('children', []):
                process_node(child)
        process_node(ast)
        return headers

    def _extract_section_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract section patterns from the AST."""
@handle_errors(error_types=(Exception,))
        sections = []

@handle_errors(error_types=(Exception,))
        def get_content_between(start_point, end_point):
            return f'Content from {start_point} to {end_point}'

        def process_node(node, current_section=None):
            if isinstance(node, dict) and node.get('type') == 'header':
                if current_section:
                    sections.append({'title': current_section.get('title',
                        ''), 'level': 1, 'content': get_content_between(
                        current_section.get('start_point', [0, 0]), node.
                        get('start_point', [0, 0]))})
                current_section = node
            for child in node.get('children', []):
                process_node(child, current_section)
        process_node(ast)
        return sections

    def _extract_list_patterns(self, ast: Dict[str, Any]) ->List[Dict[str, Any]
@handle_errors(error_types=(Exception,))
        ]:
        """Extract list patterns from the AST."""
        lists = []

        def process_node(node):
            if isinstance(node, dict) and node.get('type') in ['list',
                'ulist', 'olist']:
                lists.append({'type': node.get('type'), 'content': str(node
                    ), 'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])})
            for child in node.get('children', []):
                process_node(child)
        process_node(ast)
        return lists
