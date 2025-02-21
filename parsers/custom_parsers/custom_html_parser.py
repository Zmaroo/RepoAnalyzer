"""Custom parser for HTML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.html import HTML_PATTERNS, PatternCategory
from utils.logger import log
from xml.etree.ElementTree import Element, fromstring
from xml.sax.saxutils import escape, unescape
import re

@dataclass
class HtmlNode:
    """Base class for HTML AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class HtmlParser(CustomParser):
    """Parser for HTML files."""
    
    def __init__(self, language_id: str = "html", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: re.compile(pattern.pattern, re.DOTALL)
            for category in HTML_PATTERNS.values()
            for name, pattern in category.items()
        }
    
    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> Dict:
        """Create a standardized AST node."""
        return {
            "type": node_type,
            "start_point": start_point,
            "end_point": end_point,
            "children": [],
            **kwargs
        }

    def _process_element(self, element: Element, path: List[str], depth: int) -> Dict:
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
                "element_path": element_data["path"],
                "line_number": element_data["start_point"][0] + 1
            }
            element_data["attributes"].append(attr_data)
            
            # Process semantic attributes (ARIA, data-*, etc.)
            if name.startswith('aria-') or name.startswith('data-'):
                semantic_data = {
                    "type": "semantic_attribute",
                    "name": name,
                    "value": value,
                    "category": "aria" if name.startswith('aria-') else "data",
                    "line_number": element_data["start_point"][0] + 1
                }
                element_data["children"].append(semantic_data)
        
        # Process children
        for child in element:
            child_data = self._process_element(child, path + [tag], depth + 1)
            element_data["children"].append(child_data)
        
        return element_data

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse HTML content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "html_document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
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
                    ast["children"].append(node)
            
            # Parse HTML structure
            try:
                root = fromstring(source_code)
                ast["root"] = self._process_element(root, [], 0)
            except Exception as e:
                log(f"Error parsing HTML structure: {e}", level="error")
                ast["parse_error"] = str(e)
            
            # Process scripts and styles
            for pattern_name in ['script', 'style']:
                for match in self.patterns[pattern_name].finditer(source_code):
                    node = self._create_node(
                        pattern_name,
                        [source_code.count('\n', 0, match.start()), match.start()],
                        [source_code.count('\n', 0, match.end()), match.end()],
                        **HTML_PATTERNS[PatternCategory.SYNTAX][pattern_name].extract(match)
                    )
                    ast["children"].append(node)
            
            return ast
            
        except Exception as e:
            log(f"Error parsing HTML content: {e}", level="error")
            return {
                "type": "html_document",
                "error": str(e),
                "children": []
            } 