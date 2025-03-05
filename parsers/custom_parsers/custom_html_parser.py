"""Custom parser for HTML with enhanced documentation features."""

from .base_imports import *
from xml.etree.ElementTree import Element, fromstring
from bs4 import BeautifulSoup

class HTMLParser(BaseParser, CustomParserMixin):
    """Parser for HTML files."""
    
    def __init__(self, language_id: str = "html", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.MARKUP, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self.patterns = self._compile_patterns(HTML_PATTERNS)
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("HTML parser initialization"):
                    await self._initialize_cache(self.language_id)
                    self._initialized = True
                    log("HTML parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing HTML parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> HtmlNodeDict:
        """Create a standardized HTML AST node using the shared helper."""
        base_node = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **base_node,
            "tag": kwargs.get("tag"),
            "attributes": kwargs.get("attributes", {}),
            "text": kwargs.get("text")
        }

    def _process_element(self, element: Element, path: List[str], start_point: List[int]) -> HtmlNodeDict:
        """Process an HTML element and its children."""
        tag = element.tag.lower()
        
        element_data = self._create_node(
            "element",
            start_point,
            [start_point[0], start_point[1] + len(str(element))],
            tag=tag,
            path='/'.join(path + [tag]),
            depth=len(path),
            attributes=[],
            has_text=bool(element.text and element.text.strip())
        )
        
        # Process attributes.
        for name, value in element.attrib.items():
            attr_data = {
                "name": name.lower(),
                "value": value,
                "element_path": element_data.get('path', ''),
                "line_number": element_data.get('start_point', [0, 0])[0] + 1
            }
            element_data['attributes'].append(attr_data)
            
            # Process semantic attributes (ARIA, data-*, etc.)
            if name.startswith('aria-') or name.startswith('data-'):
                semantic_node = self._create_node(
                    "semantic_attribute",
                    element_data['start_point'],
                    element_data['end_point'],
                    name=name,
                    value=value,
                    category="aria" if name.startswith('aria-') else "data"
                )
                element_data['children'].append(semantic_node)
        
        # Process children.
        for child in element:
            child_data = self._process_element(child, path + [tag], [start_point[0], start_point[1] + 1])
            element_data['children'].append(child_data)
        
        return element_data

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse HTML content into AST structure."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="HTML parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                # Check cache first
                cached_result = await self._check_parse_cache(source_code)
                if cached_result:
                    return cached_result
                    
                lines = source_code.splitlines()
                ast = self._create_node(
                    "html_document",
                    [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0]
                )
                
                # Process comments and doctypes first.
                for pattern_name in ['comment', 'doctype']:
                    for match in self.patterns[pattern_name].finditer(source_code):
                        node = self._create_node(
                            pattern_name,
                            [source_code.count('\n', 0, match.start()), match.start()],
                            [source_code.count('\n', 0, match.end()), match.end()],
                            **HTML_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].extract(match)
                        )
                        ast['children'].append(node)
                
                # Parse HTML structure.
                try:
                    task = asyncio.create_task(fromstring(source_code))
                    self._pending_tasks.add(task)
                    try:
                        root = await task
                        root_node = self._process_element(root, [], [0, 0])
                        ast['children'].append(root_node)
                    finally:
                        self._pending_tasks.remove(task)
                except (ValueError, SyntaxError) as e:
                    log(f"Error parsing HTML structure: {e}", level="error")
                    ast['metadata'] = {"parse_error": str(e)}
                
                # Process scripts and styles.
                for pattern_name in ['script', 'style']:
                    for match in self.patterns[pattern_name].finditer(source_code):
                        node = self._create_node(
                            pattern_name,
                            [source_code.count('\n', 0, match.start()), match.start()],
                            [source_code.count('\n', 0, match.end()), match.end()],
                            **HTML_PATTERNS[PatternCategory.SYNTAX][pattern_name].extract(match)
                        )
                        ast['children'].append(node)
                
                # Store result in cache
                await self._store_parse_result(source_code, ast)
                return ast
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing HTML content: {e}", level="error")
                return self._create_node(
                    "html_document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__

    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract HTML patterns from HTML files for repository learning."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="HTML pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                # Check features cache first
                ast = await self._parse_source(source_code)
                cached_features = await self._check_features_cache(ast, source_code)
                if cached_features:
                    return cached_features
                
                # Extract patterns
                patterns = []
                
                # Extract element structure patterns
                elements = self._extract_element_patterns(ast)
                for element in elements:
                    patterns.append({
                        'name': f'html_element_{element["tag"]}',
                        'content': element["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'html_element',
                            'tag': element["tag"],
                            'attributes': element.get("attributes", []),
                            'depth': element.get("depth", 0)
                        }
                    })
                
                # Extract component patterns (reusable HTML structures)
                components = self._extract_component_patterns(ast)
                for component in components:
                    patterns.append({
                        'name': f'html_component_{component["name"]}',
                        'content': component["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'html_component',
                            'name': component["name"],
                            'elements': component.get("elements", [])
                        }
                    })
                    
                # Extract semantic patterns (accessibility, data attributes)
                semantic_patterns = self._extract_semantic_patterns(ast)
                for semantic in semantic_patterns:
                    patterns.append({
                        'name': f'html_semantic_{semantic["category"]}',
                        'content': semantic["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'html_semantic',
                            'category': semantic["category"],
                            'attributes': semantic.get("attributes", [])
                        }
                    })
                    
                # Extract script and style patterns
                embedded_patterns = self._extract_embedded_patterns(ast)
                for embedded in embedded_patterns:
                    patterns.append({
                        'name': f'html_embedded_{embedded["type"]}',
                        'content': embedded["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'html_embedded',
                            'embedded_type': embedded["type"],
                            'attributes': embedded.get("attributes", [])
                        }
                    })
                
                # Store features in cache
                await self._store_features_in_cache(ast, source_code, patterns)
                return patterns
                
            except Exception as e:
                log(f"Error extracting HTML patterns: {e}", level="error")
                return []
    
    async def cleanup(self):
        """Clean up HTML parser resources."""
        try:
            await self._cleanup_cache()
            log("HTML parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up HTML parser: {e}", level="error")

    def _extract_element_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract element patterns from the AST."""
        elements = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'element':
                tag = node.get('tag', '')
                
                # Only include significant elements
                if tag and tag not in ['div', 'span', 'p', 'br']:
                    elements.append({
                        'tag': tag,
                        'content': str(node),  # Simplified - could extract actual content
                        'attributes': node.get('attributes', []),
                        'depth': node.get('depth', 0)
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return elements
        
    def _extract_component_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract component patterns (reusable HTML structures) from the AST."""
        components = []
        
        # Extract common component structures
        # 1. Navigation component
        nav_component = self._find_navigation_component(ast)
        if nav_component:
            components.append(nav_component)
            
        # 2. Form component
        form_component = self._find_form_component(ast)
        if form_component:
            components.append(form_component)
            
        # 3. Card/panel component
        card_component = self._find_card_component(ast)
        if card_component:
            components.append(card_component)
            
        return components
        
    def _find_navigation_component(self, ast: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find navigation component in AST."""
        def process_node(node):
            if isinstance(node, dict):
                # Look for nav elements or other common navigation structures
                if (node.get('type') == 'element' and 
                    (node.get('tag') == 'nav' or 
                     (node.get('tag') == 'ul' and any('nav' in attr.get('value', '') 
                                                   for attr in node.get('attributes', []) 
                                                   if attr.get('name') == 'class')))):
                    # Found a navigation component
                    elements = []
                    # Extract navigation items
                    for child in node.get('children', []):
                        if isinstance(child, dict) and child.get('type') == 'element':
                            elements.append({
                                'tag': child.get('tag', ''),
                                'attributes': child.get('attributes', [])
                            })
                            
                    return {
                        'name': 'navigation',
                        'content': str(node),  # Simplified - could extract actual content
                        'elements': elements
                    }
                
                # Recursively check children
                for child in node.get('children', []):
                    result = process_node(child)
                    if result:
                        return result
            
            return None
        
        return process_node(ast)
        
    def _find_form_component(self, ast: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find form component in AST."""
        def process_node(node):
            if isinstance(node, dict):
                # Look for form elements
                if node.get('type') == 'element' and node.get('tag') == 'form':
                    # Found a form component
                    elements = []
                    # Extract form fields
                    for child in node.get('children', []):
                        if isinstance(child, dict) and child.get('type') == 'element':
                            if child.get('tag') in ['input', 'textarea', 'select', 'button']:
                                elements.append({
                                    'tag': child.get('tag', ''),
                                    'attributes': child.get('attributes', [])
                                })
                            
                    return {
                        'name': 'form',
                        'content': str(node),  # Simplified - could extract actual content
                        'elements': elements
                    }
                
                # Recursively check children
                for child in node.get('children', []):
                    result = process_node(child)
                    if result:
                        return result
            
            return None
        
        return process_node(ast)
        
    def _find_card_component(self, ast: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find card/panel component in AST."""
        def process_node(node):
            if isinstance(node, dict):
                # Look for card-like elements (common patterns in UI frameworks)
                if (node.get('type') == 'element' and 
                    any('card' in attr.get('value', '') or 
                        'panel' in attr.get('value', '') 
                        for attr in node.get('attributes', []) 
                        if attr.get('name') == 'class')):
                    # Found a card component
                    elements = []
                    # Extract card parts
                    for child in node.get('children', []):
                        if isinstance(child, dict) and child.get('type') == 'element':
                            elements.append({
                                'tag': child.get('tag', ''),
                                'attributes': child.get('attributes', [])
                            })
                            
                    return {
                        'name': 'card',
                        'content': str(node),  # Simplified - could extract actual content
                        'elements': elements
                    }
                
                # Recursively check children
                for child in node.get('children', []):
                    result = process_node(child)
                    if result:
                        return result
            
            return None
        
        return process_node(ast)
        
    def _extract_semantic_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract semantic patterns (accessibility, data attributes) from the AST."""
        semantic_patterns = []
        
        def collect_aria_attributes(node, attributes):
            if isinstance(node, dict):
                # Collect ARIA attributes
                if node.get('type') == 'element':
                    for attr in node.get('attributes', []):
                        if attr.get('name', '').startswith('aria-'):
                            attributes.append(attr)
                
                # Recursively check children
                for child in node.get('children', []):
                    collect_aria_attributes(child, attributes)
        
        def collect_data_attributes(node, attributes):
            if isinstance(node, dict):
                # Collect data attributes
                if node.get('type') == 'element':
                    for attr in node.get('attributes', []):
                        if attr.get('name', '').startswith('data-'):
                            attributes.append(attr)
                
                # Recursively check children
                for child in node.get('children', []):
                    collect_data_attributes(child, attributes)
        
        # Collect ARIA attributes
        aria_attributes = []
        collect_aria_attributes(ast, aria_attributes)
        if aria_attributes:
            semantic_patterns.append({
                'category': 'accessibility',
                'content': ', '.join(attr.get('name', '') + '="' + attr.get('value', '') + '"' 
                                    for attr in aria_attributes[:5]),
                'attributes': aria_attributes
            })
            
        # Collect data attributes
        data_attributes = []
        collect_data_attributes(ast, data_attributes)
        if data_attributes:
            semantic_patterns.append({
                'category': 'data',
                'content': ', '.join(attr.get('name', '') + '="' + attr.get('value', '') + '"'
                                   for attr in data_attributes[:5]),
                'attributes': data_attributes
            })
            
        return semantic_patterns
        
    def _extract_embedded_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract embedded script and style patterns from the AST."""
        embedded_patterns = []
        
        def process_node(node):
            if isinstance(node, dict):
                # Extract script content
                if node.get('type') == 'script':
                    embedded_patterns.append({
                        'type': 'script',
                        'content': node.get('content', ''),
                        'language': 'javascript'
                    })
                
                # Extract style content
                elif node.get('type') == 'style':
                    embedded_patterns.append({
                        'type': 'style',
                        'content': node.get('content', ''),
                        'language': 'css'
                    })
                
                # Recursively check children
                for child in node.get('children', []):
                    process_node(child)
        
        process_node(ast)
        return embedded_patterns 