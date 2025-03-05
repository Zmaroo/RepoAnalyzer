"""Custom parser for AsciiDoc with enhanced documentation features."""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
import asyncio
from parsers.base_parser import BaseParser
from parsers.models import AsciidocNode, PatternType
from parsers.types import FileType, ParserType
from parsers.query_patterns.asciidoc import ASCIIDOC_PATTERNS
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, ErrorSeverity, handle_async_errors, AsyncErrorBoundary
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
import re

class AsciidocParser(BaseParser):
    """Parser for AsciiDoc documents."""
    
    def __init__(self, language_id: str = "asciidoc", file_type: Optional[FileType] = None):
        # Assume AsciiDoc files are documentation files by default
        from parsers.types import FileType
        if file_type is None:
            file_type = FileType.DOC
        # Set parser_type to CUSTOM so that the base class creates a CustomFeatureExtractor
        super().__init__(language_id, file_type or FileType.DOCUMENTATION, parser_type=ParserType.CUSTOM)
        self._initialized = False
        self._pending_tasks: set[asyncio.Future] = set()
        self.patterns = self._compile_patterns(ASCIIDOC_PATTERNS)
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("AsciiDoc parser initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    log("AsciiDoc parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing AsciiDoc parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> AsciidocNode:
        """Create a standardized AsciiDoc AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return AsciidocNode(**node_dict)

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse AsciiDoc source code and produce an AST.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary(operation_name="AsciiDoc parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
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
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing AsciiDoc content: {e}", level="error")
                return AsciidocNode(
                    type="document", start_point=[0, 0], end_point=[0, 0],
                    error=str(e), children=[]
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
            
        with ErrorBoundary(operation_name="AsciiDoc pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                future = submit_async_task(self._parse_source(source_code))
                self._pending_tasks.add(future)
                try:
                    ast = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
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
    
    async def cleanup(self):
        """Clean up AsciiDoc parser resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("AsciiDoc parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up AsciiDoc parser: {e}", level="error")

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