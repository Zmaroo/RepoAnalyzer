"""Custom parser for HTML with enhanced documentation features."""

from .base_imports import *
from xml.etree.ElementTree import Element, fromstring
from bs4 import BeautifulSoup

class HTMLParser(BaseParser, CustomParserMixin):
    """Parser for HTML files."""
    
    def __init__(self, language_id: str = "html", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.MARKUP, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
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
                async with AsyncErrorBoundary("HTML parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
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
                            **self.patterns[pattern_name].extract(match)
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
                            **self.patterns[pattern_name].extract(match)
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
        """Clean up parser resources."""
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

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process HTML with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("HTML AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse HTML"
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
                log(f"Error in HTML AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_understanding(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with HTML understanding capability."""
        understanding = {}
        
        # Analyze document structure
        understanding["structure"] = {
            "elements": self._extract_element_patterns(ast),
            "attributes": self._extract_attribute_patterns(ast),
            "semantic": self._extract_semantic_patterns(ast)
        }
        
        # Analyze document patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze accessibility
        understanding["accessibility"] = await self._analyze_accessibility(ast)
        
        return understanding

    async def _process_with_generation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Process with HTML generation capability."""
        suggestions = []
        
        # Generate element suggestions
        if element_suggestions := await self._generate_element_suggestions(ast):
            suggestions.extend(element_suggestions)
        
        # Generate attribute suggestions
        if attr_suggestions := await self._generate_attribute_suggestions(ast):
            suggestions.extend(attr_suggestions)
        
        # Generate accessibility suggestions
        if a11y_suggestions := await self._generate_accessibility_suggestions(ast):
            suggestions.extend(a11y_suggestions)
        
        return suggestions

    async def _process_with_modification(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with HTML modification capability."""
        modifications = {}
        
        # Suggest structure improvements
        if improvements := await self._suggest_structure_improvements(ast):
            modifications["structure_improvements"] = improvements
        
        # Suggest semantic improvements
        if semantic := await self._suggest_semantic_improvements(ast):
            modifications["semantic_improvements"] = semantic
        
        # Suggest accessibility improvements
        if a11y := await self._suggest_accessibility_improvements(ast):
            modifications["accessibility_improvements"] = a11y
        
        return modifications

    async def _process_with_review(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with HTML review capability."""
        review = {}
        
        # Review document structure
        if structure_review := await self._review_structure(ast):
            review["structure"] = structure_review
        
        # Review semantic markup
        if semantic_review := await self._review_semantics(ast):
            review["semantics"] = semantic_review
        
        # Review accessibility
        if a11y_review := await self._review_accessibility(ast):
            review["accessibility"] = a11y_review
        
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
        
        # Learn semantic patterns
        if semantic_patterns := await self._learn_semantic_patterns(ast):
            patterns.extend(semantic_patterns)
        
        # Learn accessibility patterns
        if a11y_patterns := await self._learn_accessibility_patterns(ast):
            patterns.extend(a11y_patterns)
        
        return patterns

    async def _analyze_patterns(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze patterns in the HTML document."""
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
        
        # Analyze semantic patterns
        patterns["semantic_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.SEMANTICS,
            context
        )
        
        return patterns

    async def _analyze_accessibility(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze accessibility of the HTML document."""
        accessibility = {}
        
        # Analyze ARIA roles and properties
        accessibility["aria"] = self._analyze_aria_usage(ast)
        
        # Analyze semantic structure
        accessibility["semantic_structure"] = self._analyze_semantic_structure(ast)
        
        # Analyze keyboard navigation
        accessibility["keyboard_navigation"] = self._analyze_keyboard_navigation(ast)
        
        return accessibility

    async def _analyze_aria_usage(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze ARIA usage in the HTML document."""
        aria_usage = {}
        
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
        
        # Collect ARIA attributes
        aria_attributes = []
        collect_aria_attributes(ast, aria_attributes)
        if aria_attributes:
            aria_usage["usage"] = ', '.join(attr.get('name', '') + '="' + attr.get('value', '') + '"' 
                                            for attr in aria_attributes[:5])
            aria_usage["attributes"] = aria_attributes
        
        return aria_usage

    async def _analyze_semantic_structure(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze semantic structure in the HTML document."""
        semantic_structure = {}
        
        def collect_semantic_elements(node, elements):
            if isinstance(node, dict):
                # Collect semantic elements
                if node.get('type') == 'element':
                    for attr in node.get('attributes', []):
                        if attr.get('name', '').startswith('aria-') or attr.get('name', '').startswith('data-'):
                            elements.append(attr)
                
                # Recursively check children
                for child in node.get('children', []):
                    collect_semantic_elements(child, elements)
        
        # Collect semantic elements
        semantic_elements = []
        collect_semantic_elements(ast, semantic_elements)
        if semantic_elements:
            semantic_structure["elements"] = ', '.join(attr.get('name', '') + '="' + attr.get('value', '') + '"' 
                                                    for attr in semantic_elements[:5])
            semantic_structure["attributes"] = semantic_elements
        
        return semantic_structure

    async def _analyze_keyboard_navigation(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze keyboard navigation in the HTML document."""
        keyboard_navigation = {}
        
        def collect_tabindex_attributes(node, attributes):
            if isinstance(node, dict):
                # Collect tabindex attributes
                if node.get('type') == 'element':
                    for attr in node.get('attributes', []):
                        if attr.get('name', '').startswith('tabindex'):
                            attributes.append(attr)
                
                # Recursively check children
                for child in node.get('children', []):
                    collect_tabindex_attributes(child, attributes)
        
        # Collect tabindex attributes
        tabindex_attributes = []
        collect_tabindex_attributes(ast, tabindex_attributes)
        if tabindex_attributes:
            keyboard_navigation["tabindex"] = ', '.join(attr.get('name', '') + '="' + attr.get('value', '') + '"' 
                                                    for attr in tabindex_attributes[:5])
            keyboard_navigation["attributes"] = tabindex_attributes
        
        return keyboard_navigation

    async def _generate_element_suggestions(self, ast: Dict[str, Any]) -> List[str]:
        """Generate element suggestions based on the HTML document."""
        suggestions = []
        
        # Generate element suggestions based on structure patterns
        elements = self._extract_element_patterns(ast)
        for element in elements:
            suggestions.append(f"Consider replacing {element['tag']} with a more semantic element")
        
        # Generate element suggestions based on component patterns
        components = self._extract_component_patterns(ast)
        for component in components:
            suggestions.append(f"Consider replacing {component['name']} with a more reusable component")
        
        return suggestions

    async def _generate_attribute_suggestions(self, ast: Dict[str, Any]) -> List[str]:
        """Generate attribute suggestions based on the HTML document."""
        suggestions = []
        
        # Generate attribute suggestions based on attribute patterns
        attributes = self._extract_attribute_patterns(ast)
        for attr in attributes:
            suggestions.append(f"Consider adding {attr['name']} attribute to {attr['element_path']}")
        
        return suggestions

    async def _generate_accessibility_suggestions(self, ast: Dict[str, Any]) -> List[str]:
        """Generate accessibility suggestions based on the HTML document."""
        suggestions = []
        
        # Generate accessibility suggestions based on semantic patterns
        semantic_patterns = self._extract_semantic_patterns(ast)
        for semantic in semantic_patterns:
            suggestions.append(f"Consider adding {semantic['category']} accessibility attributes")
        
        return suggestions

    async def _review_structure(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Review HTML structure in the HTML document."""
        review = {}
        
        # Review element structure
        elements = self._extract_element_patterns(ast)
        for element in elements:
            review[f"element_{element['tag']}"] = {
                "depth": element['depth'],
                "attributes": element['attributes']
            }
        
        # Review component structure
        components = self._extract_component_patterns(ast)
        for component in components:
            review[f"component_{component['name']}"] = {
                "elements": component['elements']
            }
        
        return review

    async def _review_semantics(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Review semantic markup in the HTML document."""
        review = {}
        
        # Review semantic elements
        elements = self._extract_element_patterns(ast)
        for element in elements:
            review[f"element_{element['tag']}"] = {
                "attributes": element['attributes']
            }
        
        # Review semantic patterns
        patterns = self._extract_semantic_patterns(ast)
        for pattern in patterns:
            review[f"pattern_{pattern['category']}"] = {
                "content": pattern['content'],
                "attributes": pattern['attributes']
            }
        
        return review

    async def _review_accessibility(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Review accessibility in the HTML document."""
        review = {}
        
        # Review accessibility attributes
        attributes = self._extract_attribute_patterns(ast)
        for attr in attributes:
            review[f"attribute_{attr['name']}"] = {
                "value": attr['value'],
                "element_path": attr['element_path']
            }
        
        # Review accessibility patterns
        patterns = self._extract_semantic_patterns(ast)
        for pattern in patterns:
            review[f"pattern_{pattern['category']}"] = {
                "content": pattern['content'],
                "attributes": pattern['attributes']
            }
        
        return review

    async def _learn_structure_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Learn structure patterns from the HTML document."""
        patterns = []
        
        # Learn element structure patterns
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
        
        # Learn component structure patterns
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
        
        return patterns

    async def _learn_semantic_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Learn semantic patterns from the HTML document."""
        patterns = []
        
        # Learn semantic element patterns
        elements = self._extract_element_patterns(ast)
        for element in elements:
            patterns.append({
                'name': f'html_semantic_{element["tag"]}',
                'content': element["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.8,
                'metadata': {
                    'type': 'html_semantic',
                    'tag': element["tag"],
                    'attributes': element.get("attributes", [])
                }
            })
        
        # Learn semantic pattern patterns
        patterns.extend(self._extract_semantic_patterns(ast))
        
        return patterns

    async def _learn_accessibility_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Learn accessibility patterns from the HTML document."""
        patterns = []
        
        # Learn accessibility element patterns
        elements = self._extract_element_patterns(ast)
        for element in elements:
            patterns.append({
                'name': f'html_accessibility_{element["tag"]}',
                'content': element["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.8,
                'metadata': {
                    'type': 'html_accessibility',
                    'tag': element["tag"],
                    'attributes': element.get("attributes", [])
                }
            })
        
        # Learn accessibility pattern patterns
        patterns.extend(self._extract_semantic_patterns(ast))
        
        return patterns

    async def _extract_attribute_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attribute patterns from the AST."""
        attributes = []
        
        def collect_attributes(node, attributes):
            if isinstance(node, dict):
                # Collect attributes
                if node.get('type') == 'element':
                    for attr in node.get('attributes', []):
                        attributes.append({
                            'name': attr.get('name', ''),
                            'value': attr.get('value', ''),
                            'element_path': node.get('path', ''),
                            'line_number': node.get('start_point', [0, 0])[0] + 1
                        })
                
                # Recursively check children
                for child in node.get('children', []):
                    collect_attributes(child, attributes)
        
        collect_attributes(ast, attributes)
        return attributes

    async def _suggest_structure_improvements(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest structure improvements for the HTML document."""
        improvements = {}
        
        # Suggest element improvements
        elements = self._extract_element_patterns(ast)
        for element in elements:
            improvements[f"element_{element['tag']}"] = {
                "depth": element['depth'],
                "attributes": element['attributes']
            }
        
        # Suggest component improvements
        components = self._extract_component_patterns(ast)
        for component in components:
            improvements[f"component_{component['name']}"] = {
                "elements": component['elements']
            }
        
        return improvements

    async def _suggest_semantic_improvements(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest semantic improvements for the HTML document."""
        improvements = {}
        
        # Suggest semantic element improvements
        elements = self._extract_element_patterns(ast)
        for element in elements:
            improvements[f"element_{element['tag']}"] = {
                "attributes": element['attributes']
            }
        
        # Suggest semantic pattern improvements
        patterns = self._extract_semantic_patterns(ast)
        for pattern in patterns:
            improvements[f"pattern_{pattern['category']}"] = {
                "content": pattern['content'],
                "attributes": pattern['attributes']
            }
        
        return improvements

    async def _suggest_accessibility_improvements(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest accessibility improvements for the HTML document."""
        improvements = {}
        
        # Suggest accessibility attribute improvements
        attributes = self._extract_attribute_patterns(ast)
        for attr in attributes:
            improvements[f"attribute_{attr['name']}"] = {
                "value": attr['value'],
                "element_path": attr['element_path']
            }
        
        # Suggest accessibility pattern improvements
        patterns = self._extract_semantic_patterns(ast)
        for pattern in patterns:
            improvements[f"pattern_{pattern['category']}"] = {
                "content": pattern['content'],
                "attributes": pattern['attributes']
            }
        
        return improvements

    async def _learn_structure_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Learn structure patterns from the HTML document."""
        patterns = []
        
        # Learn element structure patterns
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
        
        # Learn component structure patterns
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
        
        return patterns

    async def _learn_semantic_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Learn semantic patterns from the HTML document."""
        patterns = []
        
        # Learn semantic element patterns
        elements = self._extract_element_patterns(ast)
        for element in elements:
            patterns.append({
                'name': f'html_semantic_{element["tag"]}',
                'content': element["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.8,
                'metadata': {
                    'type': 'html_semantic',
                    'tag': element["tag"],
                    'attributes': element.get("attributes", [])
                }
            })
        
        # Learn semantic pattern patterns
        patterns.extend(self._extract_semantic_patterns(ast))
        
        return patterns

    async def _learn_accessibility_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Learn accessibility patterns from the HTML document."""
        patterns = []
        
        # Learn accessibility element patterns
        elements = self._extract_element_patterns(ast)
        for element in elements:
            patterns.append({
                'name': f'html_accessibility_{element["tag"]}',
                'content': element["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.8,
                'metadata': {
                    'type': 'html_accessibility',
                    'tag': element["tag"],
                    'attributes': element.get("attributes", [])
                }
            })
        
        # Learn accessibility pattern patterns
        patterns.extend(self._extract_semantic_patterns(ast))
        
        return patterns 