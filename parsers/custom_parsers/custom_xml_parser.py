"""Custom parser for XML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.xml import XML_PATTERNS
from parsers.models import XmlNode, PatternType
from utils.logger import log
from collections import Counter
import re

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
            
    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract patterns from XML files for repository learning.
        
        Args:
            source_code: The content of the XML file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        try:
            # Parse the source first to get a structured representation
            ast = self._parse_source(source_code)
            
            # Extract structure patterns (elements, attributes, nesting)
            element_patterns = self._extract_element_patterns(ast)
            for element in element_patterns:
                patterns.append({
                    'name': f'xml_element_{element["tag"]}',
                    'content': element["content"],
                    'pattern_type': PatternType.STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.85,
                    'metadata': {
                        'type': 'element',
                        'tag': element["tag"],
                        'child_count': element["child_count"],
                        'has_attributes': element["has_attributes"]
                    }
                })
            
            # Extract attribute patterns
            attribute_patterns = self._extract_attribute_patterns(ast)
            for attr in attribute_patterns:
                patterns.append({
                    'name': f'xml_attribute_{attr["name"]}',
                    'content': attr["content"],
                    'pattern_type': PatternType.ATTRIBUTE,
                    'language': self.language_id,
                    'confidence': 0.8,
                    'metadata': {
                        'type': 'attribute',
                        'name': attr["name"],
                        'element': attr["element"],
                        'value_type': attr["value_type"]
                    }
                })
                
            # Extract namespace patterns
            namespace_patterns = self._extract_namespace_patterns(ast)
            for ns in namespace_patterns:
                patterns.append({
                    'name': f'xml_namespace_{ns["prefix"] or "default"}',
                    'content': ns["content"],
                    'pattern_type': PatternType.NAMESPACE,
                    'language': self.language_id,
                    'confidence': 0.9,
                    'metadata': {
                        'type': 'namespace',
                        'prefix': ns["prefix"],
                        'uri': ns["uri"]
                    }
                })
                
            # Extract naming convention patterns
            naming_patterns = self._extract_naming_patterns(source_code)
            for pattern in naming_patterns:
                patterns.append(pattern)
                
        except Exception as e:
            log(f"Error extracting XML patterns: {e}", level="error")
            
        return patterns
        
    def _extract_element_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract element patterns from the AST."""
        elements = []
        element_counts = Counter()
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'element':
                    tag = node.get('tag', 'unknown')
                    element_counts[tag] += 1
                    elements.append({
                        'tag': tag,
                        'content': str(node),
                        'child_count': len(node.get('children', [])),
                        'has_attributes': bool(node.get('attributes', {}))
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        
        # Keep only common elements (appearing more than once)
        common_elements = [elem for elem in elements 
                          if element_counts[elem['tag']] > 1]
        
        return common_elements or elements[:5]  # Return at least some elements
        
    def _extract_attribute_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attribute patterns from the AST."""
        attributes = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'element' and node.get('attributes'):
                    for attr_name, attr_value in node.get('attributes', {}).items():
                        # Determine value type (string, number, boolean)
                        value_type = "string"
                        if isinstance(attr_value, (int, float)):
                            value_type = "number"
                        elif attr_value in ("true", "false"):
                            value_type = "boolean"
                            
                        attributes.append({
                            'name': attr_name,
                            'element': node.get('tag', 'unknown'),
                            'content': f'{attr_name}="{attr_value}"',
                            'value_type': value_type
                        })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return attributes
        
    def _extract_namespace_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract namespace patterns from the AST."""
        namespaces = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'element':
                    # Check for namespace in metadata
                    if namespace := node.get('metadata', {}).get('namespace'):
                        namespaces.append({
                            'prefix': None,  # For default namespace
                            'uri': namespace,
                            'content': f'xmlns="{namespace}"'
                        })
                    
                    # Check for xmlns attributes
                    for attr_name, attr_value in node.get('attributes', {}).items():
                        if attr_name == 'xmlns':
                            namespaces.append({
                                'prefix': None,
                                'uri': attr_value,
                                'content': f'xmlns="{attr_value}"'
                            })
                        elif attr_name.startswith('xmlns:'):
                            prefix = attr_name.split(':', 1)[1]
                            namespaces.append({
                                'prefix': prefix,
                                'uri': attr_value,
                                'content': f'{attr_name}="{attr_value}"'
                            })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        
        # Remove duplicates based on prefix and URI
        unique_namespaces = []
        seen = set()
        for ns in namespaces:
            key = (ns['prefix'], ns['uri'])
            if key not in seen:
                seen.add(key)
                unique_namespaces.append(ns)
                
        return unique_namespaces
        
    def _extract_naming_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract naming convention patterns from the source code."""
        patterns = []
        
        # Extract tag naming conventions
        camel_case_tags = 0
        pascal_case_tags = 0
        kebab_case_tags = 0
        
        # Regex patterns for tag styles
        tag_pattern = re.compile(r'<([a-zA-Z][a-zA-Z0-9:-]*)')
        
        for match in tag_pattern.finditer(source_code):
            tag = match.group(1)
            if ':' in tag:
                tag = tag.split(':', 1)[1]  # Remove namespace prefix
                
            if '-' in tag:
                kebab_case_tags += 1
            elif tag and tag[0].isupper() and any(c.islower() for c in tag):
                pascal_case_tags += 1
            elif tag and tag[0].islower() and any(c.isupper() for c in tag):
                camel_case_tags += 1
        
        # Determine the dominant naming convention for tags
        max_count = max(camel_case_tags, pascal_case_tags, kebab_case_tags, 1)
        if max_count > 3:  # Only if we have enough data
            if camel_case_tags == max_count:
                convention = 'camelCase'
            elif pascal_case_tags == max_count:
                convention = 'PascalCase'
            else:
                convention = 'kebab-case'
                
            patterns.append({
                'name': 'xml_tag_naming_convention',
                'content': f"Tag naming convention: {convention}",
                'pattern_type': PatternType.NAMING_CONVENTION,
                'language': self.language_id,
                'confidence': 0.5 + 0.3 * (max_count / (camel_case_tags + pascal_case_tags + kebab_case_tags)),
                'metadata': {
                    'type': 'naming_convention',
                    'element_type': 'tag',
                    'convention': convention,
                    'camel_case_count': camel_case_tags,
                    'pascal_case_count': pascal_case_tags,
                    'kebab_case_count': kebab_case_tags
                }
            })
            
        return patterns 