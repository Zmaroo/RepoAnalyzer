"""
Custom EditorConfig parser.

This module implements a lightweight parser for EditorConfig files.
It extracts section headers (e.g. [*] or [*.py]) and
key-value property lines beneath each section.
"""

from .base_imports import *
import configparser
import re


class EditorconfigParser(BaseParser, CustomParserMixin):
    """Parser for EditorConfig files."""
    
    def __init__(self, language_id: str = "editorconfig", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self.capabilities = {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
        register_shutdown_handler(self.cleanup)
        
        # Compile regex patterns for parsing
        self.section_pattern = re.compile(r'^\s*\[(.*)\]\s*$')
        self.property_pattern = re.compile(r'^\s*([^=]+?)\s*=\s*(.*?)\s*$')
        self.comment_pattern = re.compile(r'^\s*[#;](.*)$')
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("EditorConfig parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
                    self._initialized = True
                    log("EditorConfig parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing EditorConfig parser: {e}", level="error")
                raise
        return True

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process EditorConfig with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("EditorConfig AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse EditorConfig"
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
                log(f"Error in EditorConfig AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> EditorconfigNodeDict:
        """Create a standardized EditorConfig AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "properties": kwargs.get("properties", []),
            "sections": kwargs.get("sections", [])
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse EditorConfig content into AST structure."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="EditorConfig parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                # Check cache first
                cached_result = await self._check_parse_cache(source_code)
                if cached_result:
                    return cached_result
                    
                lines = source_code.splitlines()
                ast = self._create_node(
                    "document",
                    [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0]
                )
                
                # Process comments first
                current_comment_block = []
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    if comment_match := re.match(r'^\s*[;#]\s*(.*)$', line):
                        current_comment_block.append(comment_match.group(1).strip())
                        continue
                    if line.strip() and current_comment_block:
                        node = self._create_node(
                            "comment_block",
                            [i - len(current_comment_block), 0],
                            [i - 1, len(current_comment_block[-1])],
                            content="\n".join(current_comment_block)
                        )
                        ast.children.append(node)
                        current_comment_block = []
                
                # Parse EditorConfig structure
                try:
                    config = configparser.ConfigParser(allow_no_value=True)
                    task = asyncio.create_task(config.read_string(source_code))
                    self._pending_tasks.add(task)
                    try:
                        await task
                        root_node = self._process_config(config, [0, 0])
                        ast.children.append(root_node)
                    finally:
                        self._pending_tasks.remove(task)
                except configparser.Error as e:
                    log(f"Error parsing EditorConfig structure: {e}", level="error")
                    ast.metadata["parse_error"] = str(e)
                
                # Handle any remaining comments
                if current_comment_block:
                    ast.metadata["trailing_comments"] = current_comment_block
                
                # Store result in cache
                await self._store_parse_result(source_code, ast.__dict__)
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing EditorConfig content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from EditorConfig files for repository learning.
        
        Args:
            source_code: The content of the EditorConfig file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="EditorConfig pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                # Check features cache first
                ast = await self._parse_source(source_code)
                cached_features = await self._check_features_cache(ast, source_code)
                if cached_features:
                    return cached_features
                
                # Extract patterns
                patterns = []
                
                # Extract section patterns
                section_patterns = self._extract_section_patterns(ast)
                for section in section_patterns:
                    patterns.append({
                        'name': f'editorconfig_section_{section["type"]}',
                        'content': section["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'section',
                            'pattern': section["pattern"],
                            'properties': section.get("properties", [])
                        }
                    })
                
                # Extract property patterns
                property_patterns = self._extract_property_patterns(ast)
                for prop in property_patterns:
                    patterns.append({
                        'name': f'editorconfig_property_{prop["type"]}',
                        'content': prop["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'property',
                            'property_type': prop["type"],
                            'examples': prop.get("examples", [])
                        }
                    })
                
                # Extract comment patterns
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({
                        'name': f'editorconfig_comment_{comment["type"]}',
                        'content': comment["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'comment',
                            'style': comment["type"]
                        }
                    })
                
                # Store features in cache
                await self._store_features_in_cache(ast, source_code, patterns)
                return patterns
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error extracting patterns from EditorConfig file: {str(e)}", level="error")
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
            log("EditorConfig parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up EditorConfig parser: {e}", level="error")

    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        sections = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'section':
                pattern = node.get('pattern', '')
                if pattern:
                    # Determine section type based on pattern
                    if pattern == '*':
                        section_type = 'global'
                    elif pattern.startswith('*.'):
                        section_type = 'extension'
                    elif '/' in pattern:
                        section_type = 'path'
                    else:
                        section_type = 'custom'
                        
                    sections.append({
                        'type': section_type,
                        'pattern': pattern,
                        'content': f"[{pattern}]",
                        'properties': node.get('properties', [])
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return sections
        
    def _extract_property_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract property patterns from the AST."""
        properties = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'property':
                key = node.get('key', '').lower()
                value = node.get('value', '')
                
                # Categorize properties
                if key in ['indent_style', 'indent_size', 'tab_width']:
                    property_type = 'indentation'
                elif key in ['end_of_line', 'insert_final_newline', 'trim_trailing_whitespace']:
                    property_type = 'line_ending'
                elif key in ['charset']:
                    property_type = 'encoding'
                elif key.startswith('max_line_length'):
                    property_type = 'formatting'
                else:
                    property_type = 'other'
                    
                properties.append({
                    'type': property_type,
                    'content': f"{key} = {value}",
                    'examples': [{'key': key, 'value': value}]
                })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return properties
        
    def _extract_comment_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract comment patterns from the AST."""
        comments = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'comment_block':
                    comments.append({
                        'type': 'block',
                        'content': node.get('content', '')
                    })
                elif node.get('type') == 'comment':
                    comments.append({
                        'type': 'inline',
                        'content': node.get('content', '')
                    })
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return comments

    async def _process_with_understanding(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with configuration understanding capability."""
        understanding = {}
        
        # Analyze configuration structure
        understanding["structure"] = {
            "sections": self._extract_section_patterns(ast),
            "properties": self._extract_property_patterns(ast),
            "comments": self._extract_comment_patterns(ast)
        }
        
        # Analyze configuration patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze configuration style
        understanding["style"] = await self._analyze_config_style(ast)
        
        return understanding

    async def _process_with_generation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Process with configuration generation capability."""
        suggestions = []
        
        # Generate section suggestions
        if section_suggestions := await self._generate_section_suggestions(ast):
            suggestions.extend(section_suggestions)
        
        # Generate property suggestions
        if property_suggestions := await self._generate_property_suggestions(ast):
            suggestions.extend(property_suggestions)
        
        # Generate documentation suggestions
        if doc_suggestions := await self._generate_documentation_suggestions(ast):
            suggestions.extend(doc_suggestions)
        
        return suggestions

    async def _process_with_modification(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with configuration modification capability."""
        modifications = {}
        
        # Suggest configuration improvements
        if improvements := await self._suggest_config_improvements(ast):
            modifications["config_improvements"] = improvements
        
        # Suggest property optimizations
        if optimizations := await self._suggest_property_optimizations(ast):
            modifications["property_optimizations"] = optimizations
        
        # Suggest documentation improvements
        if doc_improvements := await self._suggest_documentation_improvements(ast):
            modifications["documentation_improvements"] = doc_improvements
        
        return modifications

    async def _process_with_review(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with configuration review capability."""
        review = {}
        
        # Review configuration structure
        if structure_review := await self._review_structure(ast):
            review["structure"] = structure_review
        
        # Review property usage
        if property_review := await self._review_properties(ast):
            review["properties"] = property_review
        
        # Review documentation
        if doc_review := await self._review_documentation(ast):
            review["documentation"] = doc_review
        
        return review

    async def _process_with_learning(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Process with learning capability."""
        patterns = []
        
        # Learn configuration structure patterns
        if structure_patterns := await self._learn_structure_patterns(ast):
            patterns.extend(structure_patterns)
        
        # Learn property patterns
        if property_patterns := await self._learn_property_patterns(ast):
            patterns.extend(property_patterns)
        
        # Learn documentation patterns
        if doc_patterns := await self._learn_documentation_patterns(ast):
            patterns.extend(doc_patterns)
        
        return patterns

    async def _analyze_patterns(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze patterns in the configuration."""
        patterns = {}
        
        # Analyze section patterns
        patterns["section_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.STRUCTURE,
            context
        )
        
        # Analyze property patterns
        patterns["property_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.SYNTAX,
            context
        )
        
        # Analyze documentation patterns
        patterns["documentation_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.DOCUMENTATION,
            context
        )
        
        return patterns

    async def _analyze_config_style(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze configuration style."""
        style = {}
        
        # Analyze section naming style
        style["section_naming"] = self._analyze_section_naming(ast)
        
        # Analyze property naming style
        style["property_naming"] = self._analyze_property_naming(ast)
        
        # Analyze documentation style
        style["documentation"] = self._analyze_documentation_style(ast)
        
        return style

    async def _generate_section_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate section suggestions."""
        suggestions = []
        
        # Analyze existing sections
        sections = self._extract_section_patterns(ast)
        
        # Suggest common missing sections
        common_sections = {
            "*": "Global settings",
            "*.{js,jsx,ts,tsx}": "JavaScript/TypeScript settings",
            "*.{py,pyi}": "Python settings",
            "*.{md,rst,txt}": "Documentation settings"
        }
        
        for pattern, description in common_sections.items():
            if not any(s["pattern"] == pattern for s in sections):
                suggestions.append(f"Add section [{pattern}] for {description}")
        
        return suggestions

    async def _generate_property_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate property suggestions."""
        suggestions = []
        
        # Analyze existing properties
        properties = self._extract_property_patterns(ast)
        
        # Suggest common missing properties
        common_properties = {
            "indent_style": "Set indentation style (space/tab)",
            "indent_size": "Set indentation size",
            "end_of_line": "Set line ending style",
            "charset": "Set file encoding",
            "trim_trailing_whitespace": "Configure trailing whitespace handling",
            "insert_final_newline": "Configure final newline"
        }
        
        for prop, description in common_properties.items():
            if not any(p["key"] == prop for p in properties):
                suggestions.append(f"Add property {prop} to {description}")
        
        return suggestions

    async def _generate_documentation_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate documentation suggestions."""
        suggestions = []
        
        # Analyze existing documentation
        comments = self._extract_comment_patterns(ast)
        
        # Suggest documentation improvements
        if not any(c["type"] == "header" for c in comments):
            suggestions.append("Add a header comment describing the EditorConfig file")
            
        if not any(c["type"] == "section" for c in comments):
            suggestions.append("Add section comments explaining configuration choices")
            
        return suggestions