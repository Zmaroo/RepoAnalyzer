"""Custom parser for AsciiDoc files."""

from .base_imports import *
import re

class AsciidocParser(BaseParser, CustomParserMixin):
    """Parser for AsciiDoc files."""
    
    def __init__(self, language_id: str = "asciidoc", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.DOCUMENTATION, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self.capabilities = {
            AICapability.CODE_UNDERSTANDING,
            AICapability.DOCUMENTATION,
            AICapability.LEARNING,
            AICapability.CODE_REVIEW
        }
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("AsciiDoc parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
                    self._initialized = True
                    log("AsciiDoc parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing AsciiDoc parser: {e}", level="error")
                raise
        return True

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process AsciiDoc with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("AsciiDoc AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse AsciiDoc"
                    )
                
                results = AIProcessingResult(success=True)
                
                # Process with understanding capability
                if AICapability.CODE_UNDERSTANDING in self.capabilities:
                    understanding = await self._process_with_understanding(ast, context)
                    results.context_info.update(understanding)
                
                # Process with documentation capability
                if AICapability.DOCUMENTATION in self.capabilities:
                    documentation = await self._process_with_documentation(ast, context)
                    results.ai_insights.update(documentation)
                
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
                log(f"Error in AsciiDoc AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_understanding(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with document understanding capability."""
        understanding = {}
        
        # Analyze document structure
        understanding["structure"] = {
            "sections": self._extract_section_patterns(ast),
            "blocks": self._extract_code_block_patterns(ast),
            "lists": self._extract_list_patterns(ast)
        }
        
        # Analyze document patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze document style
        understanding["style"] = await self._analyze_document_style(ast)
        
        return understanding

    async def _process_with_documentation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with documentation capability."""
        documentation = {}
        
        # Generate section summaries
        if summaries := await self._generate_section_summaries(ast):
            documentation["section_summaries"] = summaries
        
        # Extract code examples
        if examples := await self._extract_code_examples(ast):
            documentation["code_examples"] = examples
        
        # Generate cross-references
        if references := await self._generate_cross_references(ast):
            documentation["cross_references"] = references
        
        return documentation

    async def _process_with_review(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with document review capability."""
        review = {}
        
        # Review document structure
        if structure_review := await self._review_structure(ast):
            review["structure"] = structure_review
        
        # Review document style
        if style_review := await self._review_style(ast):
            review["style"] = style_review
        
        # Review code blocks
        if code_review := await self._review_code_blocks(ast):
            review["code_blocks"] = code_review
        
        return review

    async def _process_with_learning(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Process with learning capability."""
        patterns = []
        
        # Learn document structure patterns
        if structure_patterns := await self._learn_structure_patterns(ast):
            patterns.extend(structure_patterns)
        
        # Learn documentation style patterns
        if style_patterns := await self._learn_style_patterns(ast):
            patterns.extend(style_patterns)
        
        # Learn code block patterns
        if code_patterns := await self._learn_code_block_patterns(ast):
            patterns.extend(code_patterns)
        
        return patterns

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
            log("AsciiDoc parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up AsciiDoc parser: {e}", level="error")

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> AsciidocNodeDict:
        """Create a standardized AsciiDoc AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "sections": kwargs.get("sections", []),
            "blocks": kwargs.get("blocks", [])
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse AsciiDoc content into AST structure."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(
            operation_name="AsciiDoc parsing",
            error_types=(ParsingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Check cache first
                cached_result = await self._check_parse_cache(source_code)
                if cached_result:
                    return cached_result
                    
                lines = source_code.splitlines()
                ast = self._create_node(
                    "document",
                    [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0],
                    children=[]
                )
                
                current_section = None
                in_code_block = False
                code_block_content = []
                code_block_lang = None
                current_list = None
                list_indent = 0
                
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    
                    # Handle code blocks
                    if line.startswith('[source,'):
                        if not in_code_block:
                            in_code_block = True
                            code_block_lang = line[8:].strip().rstrip(']')
                            code_block_start = i
                        continue
                    elif in_code_block and line.startswith('----'):
                        in_code_block = False
                        node = self._create_node(
                            "code_block",
                            [code_block_start, 0],
                            line_end,
                            language=code_block_lang,
                            content='\n'.join(code_block_content)
                        )
                        ast.children.append(node)
                        code_block_content = []
                        code_block_lang = None
                        continue
                    
                    if in_code_block:
                        code_block_content.append(line)
                        continue
                    
                    # Handle headers
                    if header_match := re.match(r'^(=+)\s+(.+)$', line):
                        level = len(header_match.group(1))
                        content = header_match.group(2)
                        node = self._create_node(
                            "header",
                            line_start,
                            line_end,
                            level=level,
                            content=content
                        )
                        ast.children.append(node)
                        continue
                    
                    # Handle lists
                    if list_match := re.match(r'^(\s*)([\*\-]|\d+\.)\s+(.+)$', line):
                        indent = len(list_match.group(1))
                        marker = list_match.group(2)
                        content = list_match.group(3)
                        
                        if current_list is None or indent < list_indent:
                            current_list = self._create_node(
                                "list",
                                line_start,
                                line_end,
                                ordered=marker[-1] == '.',
                                items=[]
                            )
                            ast.children.append(current_list)
                            list_indent = indent
                            
                        item = self._create_node(
                            "list_item",
                            line_start,
                            line_end,
                            content=content,
                            indent=indent
                        )
                        current_list.items.append(item)
                        continue
                    else:
                        current_list = None
                    
                    # Handle links
                    line_pos = 0
                    while link_match := re.search(r'link:([^\[]+)\[(.*?)\]', line[line_pos:]):
                        url = link_match.group(1)
                        text = link_match.group(2)
                        start = line_pos + link_match.start()
                        end = line_pos + link_match.end()
                        
                        node = self._create_node(
                            "link",
                            [i, start],
                            [i, end],
                            text=text,
                            url=url
                        )
                        ast.children.append(node)
                        line_pos = end
                    
                    # Handle emphasis
                    line_pos = 0
                    while emphasis_match := re.search(r'(\*\*|__)(.*?)\1', line[line_pos:]):
                        content = emphasis_match.group(2)
                        start = line_pos + emphasis_match.start()
                        end = line_pos + emphasis_match.end()
                        
                        node = self._create_node(
                            "emphasis",
                            [i, start],
                            [i, end],
                            content=content,
                            strong=True
                        )
                        ast.children.append(node)
                        line_pos = end
                    
                    # Handle paragraphs
                    if line.strip() and not any(child.type == "paragraph" for child in ast.children[-1:]):
                        node = self._create_node(
                            "paragraph",
                            line_start,
                            line_end,
                            content=line.strip()
                        )
                        ast.children.append(node)
                
                # Store result in cache
                await self._store_parse_result(source_code, ast.__dict__)
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing AsciiDoc content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from AsciiDoc files for repository learning.
        
        Args:
            source_code: The content of the AsciiDoc file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(
            operation_name="AsciiDoc pattern extraction",
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
                
                # Extract header patterns
                header_patterns = self._extract_header_patterns(ast)
                for header in header_patterns:
                    patterns.append({
                        'name': f'asciidoc_header_{header["level"]}',
                        'content': header["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'header',
                            'level': header["level"]
                        }
                    })
                
                # Extract code block patterns
                code_block_patterns = self._extract_code_block_patterns(ast)
                for code_block in code_block_patterns:
                    patterns.append({
                        'name': f'asciidoc_code_block_{code_block["language"] or "unknown"}',
                        'content': code_block["content"],
                        'pattern_type': PatternType.CODE_SNIPPET,
                        'language': code_block["language"] or self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'code_block',
                            'language': code_block["language"]
                        }
                    })
                
                # Extract link patterns
                link_patterns = self._extract_link_patterns(ast)
                for link in link_patterns:
                    patterns.append({
                        'name': f'asciidoc_link_{link["type"]}',
                        'content': link["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'link',
                            'url_type': link["url_type"]
                        }
                    })
                
                # Extract list patterns
                list_patterns = self._extract_list_patterns(ast)
                for list_pattern in list_patterns:
                    patterns.append({
                        'name': f'asciidoc_list_{list_pattern["type"]}',
                        'content': list_pattern["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.75,
                        'metadata': {
                            'type': 'list',
                            'ordered': list_pattern["ordered"],
                            'depth': list_pattern["depth"]
                        }
                    })
                
                return patterns
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error extracting patterns from AsciiDoc file: {str(e)}", level="error")
                return []
    
    def _extract_header_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract header patterns from the AST."""
        headers = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'header':
                headers.append({
                    'level': 1,  # Simplified - could extract actual level
                    'content': node.get('title', ''),
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return headers
        
    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        sections = []
        
        def get_content_between(start_point, end_point):
            # Simple method to get content between two points in the document
            # This is a placeholder - in a real implementation, you'd use the actual source code
            return f"Content from {start_point} to {end_point}"
        
        def process_node(node, current_section=None):
            if isinstance(node, dict) and node.get('type') == 'header':
                if current_section:
                    # End the current section
                    sections.append({
                        'title': current_section.get('title', ''),
                        'level': 1,  # Simplified level
                        'content': get_content_between(
                            current_section.get('start_point', [0, 0]),
                            node.get('start_point', [0, 0])
                        )
                    })
                
                # Start a new section
                current_section = node
            
            # Process children with current section context
            for child in node.get('children', []):
                process_node(child, current_section)
                
        process_node(ast)
        return sections
        
    def _extract_list_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract list patterns from the AST."""
        lists = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') in ['list', 'ulist', 'olist']:
                lists.append({
                    'type': node.get('type'),
                    'content': str(node),  # Simplified - could extract actual content
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return lists 

    async def parse_source(self, source: str) -> Dict[str, Any]:
        """Parse AsciiDoc source."""
        async with AsyncErrorBoundary(
            operation_name="AsciiDoc parsing",
            error_types=ParsingError,
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Create a task to parse the content
                async def parse_async():
                    # Parse the content
                    result = {}
                    self.asciidoc.parse(source, result)
                    return result

                task = asyncio.create_task(parse_async())
                self._pending_tasks.add(task)
                try:
                    doc = await task
                finally:
                    self._pending_tasks.remove(task)
                
                # Extract metadata
                metadata = {
                    'title': doc.get('title', ''),
                    'author': doc.get('author', ''),
                    'revision': doc.get('revision', ''),
                    'attributes': doc.get('attributes', {})
                }
                
                # Extract sections
                sections = []
                for section in doc.get('sections', []):
                    sections.append({
                        'title': section.get('title', ''),
                        'level': section.get('level', 0),
                        'content': section.get('content', '')
                    })
                
                # Extract blocks
                blocks = []
                for block in doc.get('blocks', []):
                    blocks.append({
                        'type': block.get('type', ''),
                        'content': block.get('content', ''),
                        'attributes': block.get('attributes', {})
                    })
                
                return {
                    'metadata': metadata,
                    'sections': sections,
                    'blocks': blocks,
                    'content': source
                }
            except Exception as e:
                raise ParsingError(f"Failed to parse AsciiDoc: {str(e)}")

    async def extract_patterns(self, source: str) -> List[Dict[str, Any]]:
        """Extract patterns from AsciiDoc source."""
        async with AsyncErrorBoundary(
            operation_name="AsciiDoc pattern extraction",
            error_types=ProcessingError,
            severity=ErrorSeverity.ERROR
        ):
            try:
                patterns = []
                
                # Parse source first
                parsed = await self.parse_source(source)
                
                # Extract patterns from sections
                for section in parsed['sections']:
                    # Look for code blocks
                    if 'source' in section['content'].lower():
                        pattern = {
                            'type': 'code_block',
                            'language': self._detect_language(section['content']),
                            'content': section['content']
                        }
                        patterns.append(pattern)
                
                # Extract patterns from blocks
                for block in parsed['blocks']:
                    if block['type'] == 'listing' and 'source' in block['attributes']:
                        pattern = {
                            'type': 'code_block',
                            'language': block['attributes']['source'],
                            'content': block['content']
                        }
                        patterns.append(pattern)
                
                return patterns
            except Exception as e:
                raise ProcessingError(f"Failed to extract patterns from AsciiDoc: {str(e)}")

    def _detect_language(self, content: str) -> str:
        """Detect programming language from content."""
        try:
            # Simple language detection based on common markers
            if '[source,python]' in content:
                return 'python'
            elif '[source,java]' in content:
                return 'java'
            elif '[source,javascript]' in content:
                return 'javascript'
            # Add more language detection rules as needed
            return 'unknown'
        except Exception as e:
            log(f"Error detecting language: {e}", level="error")
            return 'unknown' 