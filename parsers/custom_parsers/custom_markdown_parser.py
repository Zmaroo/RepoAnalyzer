"""Custom parser for Markdown with enhanced documentation features."""

from .base_imports import *

class MarkdownParser(BaseParser, CustomParserMixin):
    """Parser for Markdown files."""
    
    def __init__(self, language_id: str = "markdown", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.DOCUMENTATION, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        self.patterns = self._compile_patterns(MARKDOWN_PATTERNS)
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("Markdown parser initialization"):
                    await self._initialize_cache(self.language_id)
                    self._initialized = True
                    log("Markdown parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing Markdown parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> MarkdownNodeDict:
        """Create a standardized Markdown AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "content": kwargs.get("content"),
            "level": kwargs.get("level"),
            "indent": kwargs.get("indent")
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse Markdown content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="Markdown parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                lines = source_code.splitlines()
                ast = self._create_node(
                    "document",
                    [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0]
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
                    if line.startswith('```'):
                        if not in_code_block:
                            in_code_block = True
                            code_block_lang = line[3:].strip()
                            code_block_start = i
                        else:
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
                    if header_match := re.match(r'^(#{1,6})\s+(.+)$', line):
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
                    if list_match := re.match(r'^(\s*)([-*+]|\d+\.)\s+(.+)$', line):
                        indent = len(list_match.group(1))
                        marker = list_match.group(2)
                        content = list_match.group(3)
                        
                        if current_list is None or indent < list_indent:
                            current_list = self._create_node(
                                "list",
                                line_start,
                                line_end,
                                ordered=marker.endswith('.'),
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
                    while link_match := re.search(r'\[([^\]]+)\]\(([^)]+)\)', line[line_pos:]):
                        text = link_match.group(1)
                        url = link_match.group(2)
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
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing Markdown content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from Markdown files for repository learning.
        
        Args:
            source_code: The content of the Markdown file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="Markdown pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
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
                        'name': f'markdown_header_{header["level"]}',
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
                        'name': f'markdown_code_block_{code_block["language"] or "unknown"}',
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
                        'name': f'markdown_link_{link["type"]}',
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
                        'name': f'markdown_list_{list_pattern["type"]}',
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
                log(f"Error extracting patterns from Markdown file: {str(e)}", level="error")
                return []
    
    async def cleanup(self):
        """Clean up parser resources."""
        try:
            await self._cleanup_cache()
            log("Markdown parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up Markdown parser: {e}", level="error")

    def _extract_header_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract header patterns from the AST."""
        headers = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'header':
                headers.append({
                    'level': node.get('level', 1),
                    'content': node.get('content', ''),
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return headers
        
    def _extract_code_block_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract code block patterns from the AST."""
        code_blocks = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'code_block':
                code_blocks.append({
                    'language': node.get('language', ''),
                    'content': node.get('content', ''),
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return code_blocks

    def _extract_link_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract link patterns from the AST."""
        links = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'link':
                links.append({
                    'type': 'url',
                    'content': node.get('text', ''),
                    'url_type': node.get('url', '').split(':')[0]
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return links

    def _extract_list_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract list patterns from the AST."""
        lists = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'list':
                lists.append({
                    'type': 'ordered' if node.get('ordered', False) else 'unordered',
                    'content': node.get('items', []),
                    'depth': self._calculate_depth(node)
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return lists

    def _calculate_depth(self, node: Dict[str, Any]) -> int:
        """Calculate the depth of a list node."""
        depth = 0
        while isinstance(node, dict) and node.get('type') == 'list':
            depth += 1
            node = next((child for child in node.get('children', []) if isinstance(child, dict) and child.get('type') == 'list'), None)
        return depth

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
                        'title': current_section.get('content', ''),
                        'level': current_section.get('level', 1),
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
        
    def _extract_code_block_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract code block patterns from the AST."""
        code_blocks = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'code_block':
                code_blocks.append({
                    'language': node.get('language', ''),
                    'content': node.get('content', ''),
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return code_blocks 