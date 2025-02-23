"""Custom parser for HTML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.models import FileType
from parsers.query_patterns.html import HTML_PATTERNS, PatternCategory
from parsers.models import HtmlNode
from utils.logger import log
from xml.etree.ElementTree import Element, fromstring
from xml.sax.saxutils import escape, unescape
import re

class HtmlParser(BaseParser):
    """Parser for HTML files."""
    
    def __init__(self, language_id: str = "html", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.MARKUP)
        self.patterns = {
            name: re.compile(pattern.pattern, re.DOTALL)
            for category in HTML_PATTERNS.values()
            for name, pattern in category.items()
        }
    
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
    ) -> HtmlNode:
        """Create a standardized HTML AST node."""
        return HtmlNode(
            type=node_type,
            start_point=start_point,
            end_point=end_point,
            children=[],
            **kwargs
        )

    def _process_element(self, element: Element, path: List[str], depth: int) -> HtmlNode:
        """Process an HTML element and its children."""
        tag = element.tag.lower()
        
        element_data = self._create_node(
            "element",
            [0, 0],  # Will be updated later
            [0, 0],  # Will be updated later
            tag=tag,
            path='/'.join(path + [tag]),
            depth=depth,
            attributes=[],
            has_text=bool(element.text and element.text.strip())
        )
        
        # Process attributes
        for name, value in element.attrib.items():
            attr_data = {
                "name": name.lower(),
                "value": value,
                "element_path": element_data.path,
                "line_number": element_data.start_point[0] + 1
            }
            element_data.attributes.append(attr_data)
            
            # Process semantic attributes (ARIA, data-*, etc.)
            if name.startswith('aria-') or name.startswith('data-'):
                semantic_node = self._create_node(
                    "semantic_attribute",
                    element_data.start_point,
                    element_data.end_point,
                    name=name,
                    value=value,
                    category="aria" if name.startswith('aria-') else "data"
                )
                element_data.children.append(semantic_node)
        
        # Process children
        for child in element:
            child_data = self._process_element(child, path + [tag], depth + 1)
            element_data.children.append(child_data)
        
        return element_data

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse HTML content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "html_document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
            # Process comments and doctypes first
            for pattern_name in ['comment', 'doctype']:
                for match in self.patterns[pattern_name].finditer(source_code):
                    node = self._create_node(
                        pattern_name,
                        [source_code.count('\n', 0, match.start()), match.start()],
                        [source_code.count('\n', 0, match.end()), match.end()],
                        **HTML_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].extract(match)
                    )
                    ast.children.append(node)
            
            # Parse HTML structure
            try:
                root = fromstring(source_code)
                root_node = self._process_element(root, [], 0)
                ast.children.append(root_node)
            except Exception as e:
                log(f"Error parsing HTML structure: {e}", level="error")
                ast.metadata["parse_error"] = str(e)
            
            # Process scripts and styles
            for pattern_name in ['script', 'style']:
                for match in self.patterns[pattern_name].finditer(source_code):
                    node = self._create_node(
                        pattern_name,
                        [source_code.count('\n', 0, match.start()), match.start()],
                        [source_code.count('\n', 0, match.end()), match.end()],
                        **HTML_PATTERNS[PatternCategory.SYNTAX][pattern_name].extract(match)
                    )
                    ast.children.append(node)
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing HTML content: {e}", level="error")
            return HtmlNode(
                type="html_document",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__ 