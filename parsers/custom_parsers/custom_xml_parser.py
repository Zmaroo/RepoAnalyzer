"""Custom parser for XML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.xml import XML_PATTERNS, PatternCategory
from utils.logger import log
import xml.etree.ElementTree as ET

@dataclass
class XmlNode:
    """Base class for XML AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class XmlParser(CustomParser):
    """Parser for XML files."""
    
    def __init__(self, language_id: str = "xml", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: pattern.pattern
            for category in XML_PATTERNS.values()
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

    def _process_element(self, element: ET.Element, path: List[str], start_point: List[int]) -> Dict:
        """Process an XML element and extract its features."""
        tag = element.tag
        if '}' in tag:
            namespace, tag = tag.split('}', 1)
            namespace = namespace[1:]  # Remove leading '{'
        else:
            namespace = None

        element_data = self._create_node(
            "element",
            start_point,
            [start_point[0], start_point[1] + len(str(element))],
            tag=tag,
            namespace=namespace,
            attributes=dict(element.attrib),
            path='.'.join(path + [tag])
        )

        for child in element:
            child_node = self._process_element(
                child,
                path + [tag],
                [start_point[0], start_point[1] + len(str(child))]
            )
            element_data["children"].append(child_node)

        return element_data

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse XML content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
            )

            # Process patterns first
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                for category in XML_PATTERNS.values():
                    for pattern_name, pattern in category.items():
                        if match := pattern.pattern(line):
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                line_end,
                                **pattern.extract(match)
                            )
                            ast["children"].append(node)

            # Parse XML structure
            try:
                root = ET.fromstring(source_code)
                root_node = self._process_element(root, [], [0, 0])
                ast["children"].append(root_node)
            except ET.ParseError as e:
                log(f"Error parsing XML structure: {e}", level="error")
                return {
                    "type": "document",
                    "error": str(e),
                    "children": []
                }

            return ast
            
        except Exception as e:
            log(f"Error parsing XML content: {e}", level="error")
            return {
                "type": "document",
                "error": str(e),
                "children": []
            } 