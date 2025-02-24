"""Custom parser for XML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.xml import XML_PATTERNS
from parsers.models import XmlNode
from utils.logger import log

class XmlParser(BaseParser):
    """Parser for XML files."""
    
    def __init__(self, language_id: str = "xml", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.MARKUP, parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(XML_PATTERNS)
    
    def initialize(self) -> bool:
        self._initialized = True
        return True
    
    def _create_node(
        self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs
    ) -> XmlNode:
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return XmlNode(**node_dict)
    
    def _process_element(self, element: ET.Element, path: List[str], start_point: List[int]) -> XmlNode:
        tag = element.tag
        if '}' in tag:
            namespace, tag = tag.split('}', 1)
            namespace = namespace[1:]
        else:
            namespace = None
        element_data = self._create_node(
            "element", start_point,
            [start_point[0], start_point[1] + len(str(element))],
            tag=tag,
            attributes=dict(element.attrib),
            text=element.text.strip() if element.text else None,
            metadata={"namespace": namespace, "path": '.'.join(path + [tag])}
        )
        for child in element:
            child_node = self._process_element(
                child, path + [tag],
                [start_point[0], start_point[1] + len(str(child))]
            )
            element_data.children.append(child_node)
        return element_data
    
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document", [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                for category in XML_PATTERNS.values():
                    for pattern_name, pattern_obj in category.items():
                        if match := self.patterns[pattern_name].match(line):
                            node = self._create_node(
                                pattern_name, line_start, line_end,
                                **pattern_obj.extract(match)
                            )
                            ast.children.append(node)
            try:
                root = ET.fromstring(source_code)
                root_node = self._process_element(root, [], [0, 0])
                ast.children.append(root_node)
            except ET.ParseError as e:
                log(f"Error parsing XML structure: {e}", level="error")
                return XmlNode(
                    type="document", start_point=[0, 0], end_point=[0, 0],
                    error=str(e), children=[]
                ).__dict__
            return ast.__dict__
        except Exception as e:
            log(f"Error parsing XML content: {e}", level="error")
            return XmlNode(
                type="document", start_point=[0, 0], end_point=[0, 0],
                error=str(e), children=[]
            ).__dict__ 