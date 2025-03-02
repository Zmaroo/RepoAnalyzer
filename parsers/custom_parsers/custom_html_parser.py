"""Custom parser for HTML with enhanced documentation features."""
from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.html import HTML_PATTERNS
from parsers.models import HtmlNode, PatternType
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, AsyncErrorBoundary
from xml.etree.ElementTree import Element, fromstring
from xml.sax.saxutils import escape, unescape
import re


class HtmlParser(BaseParser):
    """Parser for HTML files."""

    def __init__(self, language_id: str='html', file_type: Optional[
        FileType]=None):
        super().__init__(language_id, file_type or FileType.MARKUP,
            parser_type=ParserType.CUSTOM)
        base_patterns = self._compile_patterns(HTML_PATTERNS)
        self.patterns = {name: re.compile(pattern.pattern, re.DOTALL) for 
            name, pattern in base_patterns.items()}

@handle_errors(error_types=(Exception,))
    def initialize(self) ->bool:
        """Initialize parser resources."""
        self._initialized = True
        return True

    def _create_node(self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs) ->HtmlNode:
        """Create a standardized HTML AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point,
            **kwargs)
        return HtmlNode(**node_dict)

    def _process_element(self, element: Element, path: List[str], depth: int
        ) ->HtmlNode:
        """Process an HTML element and its children."""
        tag = element.tag.lower()
        element_data = self._create_node('element', [0, 0], [0, 0], tag=tag,
            path='/'.join(path + [tag]), depth=depth, attributes=[],
            has_text=bool(element.text and element.text.strip()))
        for name, value in element.attrib.items():
            attr_data = {'name': name.lower(), 'value': value,
                'element_path': element_data.path, 'line_number': 
                element_data.start_point[0] + 1}
            element_data.attributes.append(attr_data)
            if name.startswith('aria-') or name.startswith('data-'):
                semantic_node = self._create_node('semantic_attribute',
                    element_data.start_point, element_data.end_point, name=
                    name, value=value, category='aria' if name.startswith(
                    'aria-') else 'data')
                element_data.children.append(semantic_node)
        for child in element:
            child_data = self._process_element(child, path + [tag], depth + 1)
            element_data.children.append(child_data)
        return element_data

    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) ->Dict[str, Any]:
        """Parse HTML content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        with ErrorBoundary(error_types=(ParsingError,), context='HTML parsing'
            ):
            try:
                lines = source_code.splitlines()
                ast = self._create_node('html_document', [0, 0], [len(lines
                    ) - 1, len(lines[-1]) if lines else 0])
                for pattern_name in ['comment', 'doctype']:
                    for match in self.patterns[pattern_name].finditer(
                        source_code):
                        node = self._create_node(pattern_name, [source_code
                            .count('\n', 0, match.start()), match.start()],
                            [source_code.count('\n', 0, match.end()), match
                            .end()], **HTML_PATTERNS[PatternCategory.
                            DOCUMENTATION][pattern_name].extract(match))
                        ast.children.append(node)
                try:
                    root = fromstring(source_code)
                    root_node = self._process_element(root, [], 0)
                    ast.children.append(root_node)
                except (ValueError, SyntaxError) as e:
                    log(f'Error parsing HTML structure: {e}', level='error')
                    ast.metadata['parse_error'] = str(e)
                for pattern_name in ['script', 'style']:
                    for match in self.patterns[pattern_name].finditer(
                        source_code):
                        node = self._create_node(pattern_name, [source_code
                            .count('\n', 0, match.start()), match.start()],
                            [source_code.count('\n', 0, match.end()), match
                            .end()], **HTML_PATTERNS[PatternCategory.SYNTAX
                            ][pattern_name].extract(match))
                        ast.children.append(node)
                return ast.__dict__
            except (ValueError, KeyError, TypeError) as e:
                log(f'Error parsing HTML content: {e}', level='error')
                return HtmlNode(type='html_document', start_point=[0, 0],
                    end_point=[0, 0], error=str(e), children=[]).__dict__

    @handle_errors(error_types=(ProcessingError,))
    def extract_patterns(self, source_code: str) ->List[Dict[str, Any]]:
        """
        Extract HTML patterns from HTML files for repository learning.
        
        Args:
            source_code: The content of the HTML file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        with ErrorBoundary(error_types=(ProcessingError,), context=
            'HTML pattern extraction'):
            try:
                ast_dict = self._parse_source(source_code)
                elements = self._extract_element_patterns(ast_dict)
                for element in elements:
                    patterns.append({'name':
                        f"html_element_{element['tag']}", 'content':
                        element['content'], 'pattern_type': PatternType.
                        CODE_STRUCTURE, 'language': self.language_id,
                        'confidence': 0.85, 'metadata': {'type':
                        'html_element', 'tag': element['tag'], 'attributes':
                        element.get('attributes', []), 'depth': element.get
                        ('depth', 0)}})
                components = self._extract_component_patterns(ast_dict)
                for component in components:
                    patterns.append({'name':
                        f"html_component_{component['name']}", 'content':
                        component['content'], 'pattern_type': PatternType.
                        CODE_STRUCTURE, 'language': self.language_id,
                        'confidence': 0.9, 'metadata': {'type':
                        'html_component', 'name': component['name'],
                        'elements': component.get('elements', [])}})
                semantic_patterns = self._extract_semantic_patterns(ast_dict)
                for semantic in semantic_patterns:
                    patterns.append({'name':
                        f"html_semantic_{semantic['category']}", 'content':
                        semantic['content'], 'pattern_type': PatternType.
                        CODE_STRUCTURE, 'language': self.language_id,
                        'confidence': 0.8, 'metadata': {'type':
                        'html_semantic', 'category': semantic['category'],
                        'attributes': semantic.get('attributes', [])}})
                embedded_patterns = self._extract_embedded_patterns(ast_dict)
                for embedded in embedded_patterns:
                    patterns.append({'name':
                        f"html_embedded_{embedded['type']}", 'content':
                        embedded['content'], 'pattern_type': PatternType.
                        CODE_STRUCTURE, 'language': embedded.get('language',
                        self.language_id), 'confidence': 0.75, 'metadata':
                        {'type': 'html_embedded', 'embedded_type': embedded
                        ['type'], 'language': embedded.get('language')}})
            except (ValueError, KeyError, TypeError) as e:
                log(f'Error extracting HTML patterns: {e}', level='error')
        return patterns

    def _extract_element_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract element patterns from the AST."""
        elements = []
@handle_errors(error_types=(Exception,))

        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'element':
                tag = node.get('tag', '')
                if tag and tag not in ['div', 'span', 'p', 'br']:
                    elements.append({'tag': tag, 'content': str(node),
                        'attributes': node.get('attributes', []), 'depth':
                        node.get('depth', 0)})
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return elements

    def _extract_component_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract component patterns (reusable HTML structures) from the AST."""
        components = []
        nav_component = self._find_navigation_component(ast)
        if nav_component:
            components.append(nav_component)
        form_component = self._find_form_component(ast)
        if form_component:
            components.append(form_component)
        card_component = self._find_card_component(ast)
        if card_component:
            components.append(card_component)
        return components

    def _find_navigation_component(self, ast: Dict[str, Any]) ->Optional[Dict
        [str, Any]]:
@handle_errors(error_types=(Exception,))
        """Find navigation component in AST."""

        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'element' and (node.get('tag') ==
                    'nav' or node.get('tag') == 'ul' and any('nav' in attr.
                    get('value', '') for attr in node.get('attributes', []) if
                    attr.get('name') == 'class')):
                    elements = []
                    for child in node.get('children', []):
                        if isinstance(child, dict) and child.get('type'
                            ) == 'element':
                            elements.append({'tag': child.get('tag', ''),
                                'attributes': child.get('attributes', [])})
                    return {'name': 'navigation', 'content': str(node),
                        'elements': elements}
                for child in node.get('children', []):
                    result = process_node(child)
                    if result:
                        return result
            return None
        return process_node(ast)

    def _find_form_component(self, ast: Dict[str, Any]) ->Optional[Dict[str,
@handle_errors(error_types=(Exception,))
        Any]]:
        """Find form component in AST."""

        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'element' and node.get('tag') == 'form':
                    elements = []
                    for child in node.get('children', []):
                        if isinstance(child, dict) and child.get('type'
                            ) == 'element':
                            if child.get('tag') in ['input', 'textarea',
                                'select', 'button']:
                                elements.append({'tag': child.get('tag', ''
                                    ), 'attributes': child.get('attributes',
                                    [])})
                    return {'name': 'form', 'content': str(node),
                        'elements': elements}
                for child in node.get('children', []):
                    result = process_node(child)
                    if result:
                        return result
            return None
        return process_node(ast)

@handle_errors(error_types=(Exception,))
    def _find_card_component(self, ast: Dict[str, Any]) ->Optional[Dict[str,
        Any]]:
        """Find card/panel component in AST."""

        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'element' and any('card' in attr.get
                    ('value', '') or 'panel' in attr.get('value', '') for
                    attr in node.get('attributes', []) if attr.get('name') ==
                    'class'):
                    elements = []
                    for child in node.get('children', []):
                        if isinstance(child, dict) and child.get('type'
                            ) == 'element':
                            elements.append({'tag': child.get('tag', ''),
                                'attributes': child.get('attributes', [])})
                    return {'name': 'card', 'content': str(node),
                        'elements': elements}
                for child in node.get('children', []):
                    result = process_node(child)
                    if result:
                        return result
            return None
        return process_node(ast)

@handle_errors(error_types=(Exception,))
    def _extract_semantic_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract semantic patterns (accessibility, data attributes) from the AST."""
        semantic_patterns = []

        def collect_aria_attributes(node, attributes):
            if isinstance(node, dict):
                if node.get('type') == 'element':
@handle_errors(error_types=(Exception,))
                    for attr in node.get('attributes', []):
                        if attr.get('name', '').startswith('aria-'):
                            attributes.append(attr)
                for child in node.get('children', []):
                    collect_aria_attributes(child, attributes)

        def collect_data_attributes(node, attributes):
            if isinstance(node, dict):
                if node.get('type') == 'element':
                    for attr in node.get('attributes', []):
                        if attr.get('name', '').startswith('data-'):
                            attributes.append(attr)
                for child in node.get('children', []):
                    collect_data_attributes(child, attributes)
        aria_attributes = []
        collect_aria_attributes(ast, aria_attributes)
        if aria_attributes:
            semantic_patterns.append({'category': 'accessibility',
                'content': ', '.join(attr.get('name', '') + '="' + attr.get
                ('value', '') + '"' for attr in aria_attributes[:5]),
                'attributes': aria_attributes})
        data_attributes = []
        collect_data_attributes(ast, data_attributes)
        if data_attributes:
            semantic_patterns.append({'category': 'data', 'content': ', '.
                join(attr.get('name', '') + '="' + attr.get('value', '') +
                '"' for attr in data_attributes[:5]), 'attributes':
                data_attributes})
@handle_errors(error_types=(Exception,))
        return semantic_patterns

    def _extract_embedded_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract embedded script and style patterns from the AST."""
        embedded_patterns = []

        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'script':
                    embedded_patterns.append({'type': 'script', 'content':
                        node.get('content', ''), 'language': 'javascript'})
                elif node.get('type') == 'style':
                    embedded_patterns.append({'type': 'style', 'content':
                        node.get('content', ''), 'language': 'css'})
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return embedded_patterns
