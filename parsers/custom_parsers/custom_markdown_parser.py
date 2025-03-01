"""Custom parser for Markdown with enhanced documentation features."""
from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.models import MarkdownNode, PatternType
from parsers.query_patterns.markdown import MARKDOWN_PATTERNS
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, AsyncErrorBoundary
import re


class MarkdownParser(BaseParser):
    """Parser for Markdown files."""

    def __init__(self, language_id: str='markdown', file_type: Optional[
        FileType]=None):
        super().__init__(language_id, file_type or FileType.DOCUMENTATION,
            parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(MARKDOWN_PATTERNS)

    def initialize(self) ->bool:
        """Initialize parser resources."""
        self._initialized = True
        return True

    def _create_node(self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs) ->MarkdownNode:
        """Create a standardized Markdown AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point,
            **kwargs)
        return MarkdownNode(**node_dict)

    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) ->Dict[str, Any]:
        """Parse Markdown content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        with ErrorBoundary(error_types=(ParsingError,), context=
            'Markdown parsing'):
            try:
                lines = source_code.splitlines()
                ast = self._create_node('document', [0, 0], [len(lines) - 1,
                    len(lines[-1]) if lines else 0])
                current_section = None
                in_code_block = False
                code_block_content = []
                code_block_lang = None
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    if not in_code_block and (header_match := self.patterns
                        ['header'].match(line)):
                        level, content = header_match.groups()
                        node = self._create_node('header', line_start,
                            line_end, level=len(level), content=content)
                        ast.children.append(node)
                        current_section = node
                        continue
                    if (code_match := self.patterns['code_block'].match(line)):
                        if not in_code_block:
                            in_code_block = True
                            code_block_lang = code_match.group(1)
                            code_block_content = []
                            code_block_start = line_start
                        else:
                            node = self._create_node('code_block',
                                code_block_start, line_end, language=
                                code_block_lang, content='\n'.join(
                                code_block_content))
                            if current_section:
                                current_section.children.append(node)
                            else:
                                ast.children.append(node)
                            in_code_block = False
                        continue
                    if in_code_block:
                        code_block_content.append(line)
                        continue
                    if (list_match := self.patterns['list_item'].match(line)):
                        indent, content = list_match.groups()
                        node = self._create_node('list_item', line_start,
                            line_end, content=content, indent=len(indent))
                        if current_section:
                            current_section.children.append(node)
                        else:
                            ast.children.append(node)
                        continue
                return ast.__dict__
            except (ValueError, KeyError, TypeError) as e:
                log(f'Error parsing Markdown content: {e}', level='error')
                return MarkdownNode(type='document', start_point=[0, 0],
                    end_point=[0, 0], error=str(e), children=[]).__dict__

    @handle_errors(error_types=(ProcessingError,))
    def extract_patterns(self, source_code: str) ->List[Dict[str, Any]]:
        """
        Extract documentation patterns from Markdown files for repository learning.
        
        Args:
            source_code: The content of the Markdown file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        with ErrorBoundary(error_types=(ProcessingError,), context=
            'Markdown pattern extraction'):
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
                code_blocks = self._extract_code_block_patterns(ast)
                for code_block in code_blocks:
                    patterns.append({'name':
                        f"doc_code_example_{code_block['language'] or 'unknown'}"
                        , 'content': code_block['content'], 'pattern_type':
                        PatternType.DOCUMENTATION_STRUCTURE, 'language': 
                        code_block['language'] or self.language_id,
                        'confidence': 0.7, 'metadata': {'type':
                        'code_example', 'language': code_block['language']}})
            except (ValueError, KeyError, TypeError) as e:
                log(f'Error extracting Markdown patterns: {e}', level='error')
        return patterns

    def _extract_header_patterns(self, ast: Dict[str, Any]) ->List[Dict[str,
        Any]]:
        """Extract header patterns from the AST."""
        headers = []

        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'header':
                headers.append({'level': node.get('level', 1), 'content':
                    node.get('content', ''), 'start_point': node.get(
                    'start_point', [0, 0]), 'end_point': node.get(
                    'end_point', [0, 0])})
            for child in node.get('children', []):
                process_node(child)
        process_node(ast)
        return headers

    def _extract_section_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract section patterns from the AST."""
        sections = []

        def get_content_between(start_point, end_point):
            return f'Content from {start_point} to {end_point}'

        def process_node(node, current_section=None):
            if isinstance(node, dict) and node.get('type') == 'header':
                if current_section:
                    sections.append({'title': current_section.get('content',
                        ''), 'level': current_section.get('level', 1),
                        'content': get_content_between(current_section.get(
                        'start_point', [0, 0]), node.get('start_point', [0,
                        0]))})
                current_section = node
            for child in node.get('children', []):
                process_node(child, current_section)
        process_node(ast)
        return sections

    def _extract_code_block_patterns(self, ast: Dict[str, Any]) ->List[Dict
        [str, Any]]:
        """Extract code block patterns from the AST."""
        code_blocks = []

        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'code_block':
                code_blocks.append({'language': node.get('language', ''),
                    'content': node.get('content', ''), 'start_point': node
                    .get('start_point', [0, 0]), 'end_point': node.get(
                    'end_point', [0, 0])})
            for child in node.get('children', []):
                process_node(child)
        process_node(ast)
        return code_blocks
