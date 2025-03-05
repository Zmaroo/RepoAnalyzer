"""Custom parser for XML files."""

from .base_imports import *
import xml.etree.ElementTree as ET
from collections import Counter
import re

class XmlParser(BaseParser, CustomParserMixin):
    """Parser for XML files."""
    
    def __init__(self, language_id: str = "xml", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.DATA, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("XML parser initialization"):
                    # No special initialization needed yet
                    await self._load_patterns()  # Load patterns through BaseParser mechanism
                    self._initialized = True
                    log("XML parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing XML parser: {e}", level="error")
                raise
        return True
    
    def _create_node(
        self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs
    ) -> XmlNodeDict:
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "tag": kwargs.get("tag"),
            "attributes": kwargs.get("attributes", {}),
            "text": kwargs.get("text")
        }
    
    def _process_element(self, element: ET.Element, path: List[str], start_point: List[int]) -> XmlNodeDict:
        """Process an XML element into a node structure."""
        tag = element.tag
        if '}' in tag:
            # Handle namespaced tags
            tag = tag.split('}', 1)[1]
            
        node = self._create_node(
            "element",
            start_point,
            [start_point[0], start_point[1] + len(str(element))],
            tag=tag,
            path='.'.join(path),
            attributes=dict(element.attrib),
            text=element.text.strip() if element.text else None,
            tail=element.tail.strip() if element.tail else None,
            children=[]
        )
        
        # Process child elements
        for child in element:
            child_path = path + [child.tag]
            child_node = self._process_element(
                child,
                child_path,
                [start_point[0], start_point[1] + 1]
            )
            node["children"].append(child_node)
            
        return node
    
    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse XML content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(
            operation_name="XML parsing",
            error_types=(ParsingError,),
            severity=ErrorSeverity.ERROR
        ):
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
                                    **self.patterns[pattern_name].extract(match)
                                )
                                ast.children.append(node)
                try:
                    task = asyncio.create_task(self._parse_xml(source_code))
                    self._pending_tasks.add(task)
                    try:
                        root = await task
                        root_node = self._process_element(root, [], [0, 0])
                        ast.children.append(root_node)
                    finally:
                        self._pending_tasks.remove(task)
                except ET.ParseError as e:
                    log(f"Error parsing XML structure: {e}", level="error")
                    return self._create_node(
                        "document",
                        [0, 0],
                        [0, 0],
                        error=str(e),
                        children=[]
                    ).__dict__
                return ast.__dict__
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing XML content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__
    
    async def _parse_xml(self, source_code: str) -> ET.Element:
        """Parse XML content asynchronously."""
        return ET.fromstring(source_code)
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from XML files for repository learning.
        
        Args:
            source_code: The content of the XML file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(
            operation_name="XML pattern extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                task = asyncio.create_task(self._parse_source(source_code))
                self._pending_tasks.add(task)
                try:
                    ast = await task
                finally:
                    self._pending_tasks.remove(task)
                
                # Extract element patterns
                element_patterns = self._extract_element_patterns(ast)
                for element in element_patterns:
                    patterns.append({
                        'name': f'xml_element_{element["type"]}',
                        'content': element["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'element',
                            'tag': element["tag"],
                            'attributes': element["attributes"]
                        }
                    })
                
                # Extract attribute patterns
                attribute_patterns = self._extract_attribute_patterns(ast)
                for attribute in attribute_patterns:
                    patterns.append({
                        'name': f'xml_attribute_{attribute["type"]}',
                        'content': attribute["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.75,
                        'metadata': {
                            'type': 'attribute',
                            'name': attribute["name"],
                            'value_type': attribute["value_type"]
                        }
                    })
                
                # Extract namespace patterns
                namespace_patterns = self._extract_namespace_patterns(ast)
                for namespace in namespace_patterns:
                    patterns.append({
                        'name': f'xml_namespace_{namespace["type"]}',
                        'content': namespace["content"],
                        'pattern_type': PatternType.CODE_REFERENCE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'namespace',
                            'prefix': namespace["prefix"],
                            'uri': namespace["uri"]
                        }
                    })
                
                # Extract comment patterns
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({
                        'name': f'xml_comment_{comment["type"]}',
                        'content': comment["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.7,
                        'metadata': {
                            'type': 'comment',
                            'style': comment["type"]
                        }
                    })
                
                return patterns
                
            except (ValueError, KeyError, TypeError, ET.ParseError) as e:
                log(f"Error extracting patterns from XML file: {str(e)}", level="error")
                return []
    
    async def cleanup(self):
        """Clean up XML parser resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("XML parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up XML parser: {e}", level="error")
        
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