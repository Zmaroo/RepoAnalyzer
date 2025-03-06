"""Custom parser for XML files."""

from .base_imports import *
import xml.etree.ElementTree as ET
from collections import Counter
import re
from parsers.query_patterns.xml import XML_PATTERNS

class XmlParser(BaseParser, CustomParserMixin):
    """Parser for XML files."""
    
    def __init__(self, language_id: str = "xml", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.DATA, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        self.capabilities = {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("XML parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
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
            # Clean up base resources
            await self._cleanup_cache()
            
            # Clean up AI processor
            if self._ai_processor:
                await self._ai_processor.cleanup()
                self._ai_processor = None
            
            # Clean up pattern processor
            if self._pattern_processor:
                await self._pattern_processor.cleanup()
                self._pattern_processor = None
            
            # Cancel pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("XML parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up XML parser: {e}", level="error")
        
    def _extract_element_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract element patterns from the AST."""
        elements = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'element':
                tag = node.get('tag', '')
                if tag:
                    elements.append({
                        'tag': tag,
                        'attributes': node.get('attributes', {}),
                        'has_text': bool(node.get('text', '').strip())
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return elements
        
    def _extract_attribute_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attribute patterns from the AST."""
        attributes = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'element':
                for name, value in node.get('attributes', {}).items():
                    attributes.append({
                        'name': name,
                        'value': value,
                        'element_tag': node.get('tag', '')
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return attributes
        
    def _extract_namespace_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract namespace patterns from the AST."""
        namespaces = {}
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'element':
                tag = node.get('tag', '')
                if ':' in tag:
                    prefix = tag.split(':')[0]
                    if prefix not in namespaces:
                        namespaces[prefix] = {
                            'prefix': prefix,
                            'elements': [],
                            'attributes': []
                        }
                    namespaces[prefix]['elements'].append(tag)
                
                # Check attributes for namespaces
                for name in node.get('attributes', {}):
                    if ':' in name:
                        prefix = name.split(':')[0]
                        if prefix not in namespaces:
                            namespaces[prefix] = {
                                'prefix': prefix,
                                'elements': [],
                                'attributes': []
                            }
                        namespaces[prefix]['attributes'].append(name)
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return list(namespaces.values())
    
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process XML with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("XML AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse XML"
                    )
                
                results = AIProcessingResult(success=True)
                
                # Process with understanding capability
                if AICapability.CODE_UNDERSTANDING in self.capabilities:
                    understanding = await self._process_with_understanding(ast, context)
                    results.context_info.update(understanding)
                
                # Process with generation capability
                if AICapability.CODE_GENERATION in self.capabilities:
                    generation = await self._process_with_generation(ast, context)
                    results.suggestions.extend(generation)
                
                # Process with modification capability
                if AICapability.CODE_MODIFICATION in self.capabilities:
                    modification = await self._process_with_modification(ast, context)
                    results.ai_insights.update(modification)
                
                # Process with review capability
                if AICapability.CODE_REVIEW in self.capabilities:
                    review = await self._process_with_review(ast, context)
                    results.ai_insights.update(review)
                
                # Process with learning capability
                if AICapability.LEARNING in self.capabilities:
                    learning = await self._process_with_learning(ast, context)
                    results.learned_patterns.extend(learning)
                
                return results
            except Exception as e:
                log(f"Error in XML AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_understanding(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with XML understanding capability."""
        understanding = {}
        
        # Analyze XML structure
        understanding["structure"] = {
            "elements": self._extract_element_patterns(ast),
            "attributes": self._extract_attribute_patterns(ast),
            "namespaces": self._extract_namespace_patterns(ast)
        }
        
        # Analyze XML patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze XML style
        understanding["style"] = await self._analyze_xml_style(ast)
        
        return understanding

    async def _process_with_generation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Process with XML generation capability."""
        suggestions = []
        
        # Generate element suggestions
        if element_suggestions := await self._generate_element_suggestions(ast):
            suggestions.extend(element_suggestions)
        
        # Generate attribute suggestions
        if attr_suggestions := await self._generate_attribute_suggestions(ast):
            suggestions.extend(attr_suggestions)
        
        # Generate namespace suggestions
        if ns_suggestions := await self._generate_namespace_suggestions(ast):
            suggestions.extend(ns_suggestions)
        
        return suggestions

    async def _process_with_modification(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with XML modification capability."""
        modifications = {}
        
        # Suggest structure improvements
        if improvements := await self._suggest_structure_improvements(ast):
            modifications["structure_improvements"] = improvements
        
        # Suggest formatting improvements
        if formatting := await self._suggest_formatting_improvements(ast):
            modifications["formatting_improvements"] = formatting
        
        # Suggest namespace improvements
        if ns_improvements := await self._suggest_namespace_improvements(ast):
            modifications["namespace_improvements"] = ns_improvements
        
        return modifications

    async def _process_with_review(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with XML review capability."""
        review = {}
        
        # Review XML structure
        if structure_review := await self._review_structure(ast):
            review["structure"] = structure_review
        
        # Review XML formatting
        if format_review := await self._review_formatting(ast):
            review["formatting"] = format_review
        
        # Review XML namespaces
        if ns_review := await self._review_namespaces(ast):
            review["namespaces"] = ns_review
        
        return review

    async def _process_with_learning(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Process with learning capability."""
        patterns = []
        
        # Learn structure patterns
        if structure_patterns := await self._learn_structure_patterns(ast):
            patterns.extend(structure_patterns)
        
        # Learn formatting patterns
        if format_patterns := await self._learn_formatting_patterns(ast):
            patterns.extend(format_patterns)
        
        # Learn namespace patterns
        if ns_patterns := await self._learn_namespace_patterns(ast):
            patterns.extend(ns_patterns)
        
        return patterns

    async def _analyze_patterns(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze patterns in the XML document."""
        patterns = {}
        
        # Analyze element patterns
        patterns["element_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.STRUCTURE,
            context
        )
        
        # Analyze attribute patterns
        patterns["attribute_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.SYNTAX,
            context
        )
        
        # Analyze namespace patterns
        patterns["namespace_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.SEMANTICS,
            context
        )
        
        return patterns

    async def _analyze_xml_style(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze XML style."""
        style = {}
        
        # Analyze element style
        style["element_style"] = self._analyze_element_style(ast)
        
        # Analyze attribute style
        style["attribute_style"] = self._analyze_attribute_style(ast)
        
        # Analyze namespace style
        style["namespace_style"] = self._analyze_namespace_style(ast)
        
        return style

    async def _generate_element_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate element suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing elements
        elements = self._extract_element_patterns(ast)
        
        # Suggest common missing elements
        common_elements = {
            "header": "Document header section",
            "footer": "Document footer section",
            "metadata": "Document metadata",
            "content": "Main content section",
            "description": "Description section"
        }
        
        for name, description in common_elements.items():
            if not any(e["tag"] == name for e in elements):
                suggestions.append(f"Add element '{name}' for {description}")
        
        return suggestions

    async def _generate_attribute_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate attribute suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing attributes
        attributes = self._extract_attribute_patterns(ast)
        
        # Suggest common missing attributes
        common_attributes = {
            "id": "Unique identifier",
            "class": "CSS class",
            "lang": "Language code",
            "title": "Element title",
            "description": "Element description"
        }
        
        for name, description in common_attributes.items():
            if not any(a["name"] == name for a in attributes):
                suggestions.append(f"Add attribute '{name}' for {description}")
        
        return suggestions

    async def _generate_namespace_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate namespace suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing namespaces
        namespaces = self._extract_namespace_patterns(ast)
        
        # Suggest common missing namespaces
        common_namespaces = {
            "xsi": "XML Schema Instance",
            "xsd": "XML Schema Definition",
            "xhtml": "XHTML namespace",
            "svg": "SVG namespace",
            "math": "MathML namespace"
        }
        
        for prefix, description in common_namespaces.items():
            if not any(ns["prefix"] == prefix for ns in namespaces):
                suggestions.append(f"Add namespace '{prefix}' for {description}")
        
        return suggestions

    async def _suggest_structure_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest structure improvements based on the AST."""
        improvements = {}
        
        # Analyze element structure
        elements = self._extract_element_patterns(ast)
        element_improvements = []
        
        # Check for empty elements
        for element in elements:
            if not element.get("attributes") and not element.get("has_text"):
                element_improvements.append(f"Add content or attributes to empty element '{element['tag']}'")
        
        if element_improvements:
            improvements["elements"] = element_improvements
        
        return improvements

    async def _suggest_formatting_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest formatting improvements based on the AST."""
        improvements = {}
        
        # Analyze attribute formatting
        attributes = self._extract_attribute_patterns(ast)
        attr_improvements = []
        
        # Check attribute value formatting
        for attr in attributes:
            if not attr.get("value", "").strip():
                attr_improvements.append(f"Add value to empty attribute '{attr['name']}'")
        
        if attr_improvements:
            improvements["attributes"] = attr_improvements
        
        return improvements

    async def _suggest_namespace_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest namespace improvements based on the AST."""
        improvements = {}
        
        # Analyze namespace usage
        namespaces = self._extract_namespace_patterns(ast)
        ns_improvements = []
        
        # Check namespace declarations
        for ns in namespaces:
            if not ns.get("elements") and not ns.get("attributes"):
                ns_improvements.append(f"Remove unused namespace '{ns['prefix']}'")
        
        if ns_improvements:
            improvements["namespaces"] = ns_improvements
        
        return improvements

    async def _review_structure(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review XML structure."""
        review = {}
        
        # Review element structure
        elements = self._extract_element_patterns(ast)
        if elements:
            review["elements"] = {
                "count": len(elements),
                "unique_tags": len(set(e["tag"] for e in elements)),
                "empty_elements": sum(1 for e in elements if not e.get("has_text"))
            }
        
        # Review attribute structure
        attributes = self._extract_attribute_patterns(ast)
        if attributes:
            review["attributes"] = {
                "count": len(attributes),
                "unique_names": len(set(a["name"] for a in attributes))
            }
        
        return review

    async def _review_formatting(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review XML formatting."""
        review = {}
        
        # Review element formatting
        elements = self._extract_element_patterns(ast)
        if elements:
            review["element_formatting"] = {
                "has_text": sum(1 for e in elements if e.get("has_text")),
                "has_attributes": sum(1 for e in elements if e.get("attributes"))
            }
        
        # Review attribute formatting
        attributes = self._extract_attribute_patterns(ast)
        if attributes:
            review["attribute_formatting"] = {
                "empty_values": sum(1 for a in attributes if not a.get("value", "").strip())
            }
        
        return review

    async def _review_namespaces(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review XML namespaces."""
        review = {}
        
        # Review namespace usage
        namespaces = self._extract_namespace_patterns(ast)
        if namespaces:
            review["namespace_usage"] = {
                "count": len(namespaces),
                "element_usage": {ns["prefix"]: len(ns.get("elements", [])) for ns in namespaces},
                "attribute_usage": {ns["prefix"]: len(ns.get("attributes", [])) for ns in namespaces}
            }
        
        return review

    async def _learn_structure_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn structure patterns from the AST."""
        patterns = []
        
        # Learn element patterns
        elements = self._extract_element_patterns(ast)
        if elements:
            patterns.append({
                "type": "element_structure",
                "content": f"Document uses {len(elements)} elements with {len(set(e['tag'] for e in elements))} unique tags",
                "examples": [e["tag"] for e in elements[:3]]
            })
        
        # Learn attribute patterns
        attributes = self._extract_attribute_patterns(ast)
        if attributes:
            patterns.append({
                "type": "attribute_structure",
                "content": f"Document uses {len(attributes)} attributes with {len(set(a['name'] for a in attributes))} unique names",
                "examples": [a["name"] for a in attributes[:3]]
            })
        
        return patterns

    async def _learn_formatting_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn formatting patterns from the AST."""
        patterns = []
        
        # Learn element formatting patterns
        elements = self._extract_element_patterns(ast)
        if elements:
            text_elements = sum(1 for e in elements if e.get("has_text"))
            attr_elements = sum(1 for e in elements if e.get("attributes"))
            patterns.append({
                "type": "element_formatting",
                "content": f"Document has {text_elements} elements with text and {attr_elements} with attributes",
                "examples": {"text_elements": text_elements, "attr_elements": attr_elements}
            })
        
        return patterns

    async def _learn_namespace_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn namespace patterns from the AST."""
        patterns = []
        
        # Learn namespace usage patterns
        namespaces = self._extract_namespace_patterns(ast)
        if namespaces:
            patterns.append({
                "type": "namespace_usage",
                "content": f"Document uses {len(namespaces)} namespaces",
                "examples": [ns["prefix"] for ns in namespaces]
            })
        
        return patterns 