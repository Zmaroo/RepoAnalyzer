"""Custom parser for TOML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
import asyncio
import tomli
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.toml import TOML_PATTERNS
from parsers.models import TomlNode, PatternType
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, ErrorSeverity, handle_async_errors, AsyncErrorBoundary
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
import re

class TomlParser(BaseParser):
    """Parser for TOML files."""
    
    def __init__(self, language_id: str = "toml", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        self._initialized = False
        self._pending_tasks: set[asyncio.Future] = set()
        self.patterns = self._compile_patterns(TOML_PATTERNS)
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("TOML parser initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    log("TOML parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing TOML parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> TomlNode:
        """Create a standardized TOML AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return TomlNode(**node_dict)

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse TOML content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary(operation_name="TOML parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
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
                    if comment_match := re.match(r'^\s*#\s*(.*)$', line):
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
                
                # Parse TOML structure
                try:
                    future = submit_async_task(tomli.loads(source_code))
                    self._pending_tasks.add(future)
                    try:
                        data = await asyncio.wrap_future(future)
                        root_node = self._process_value(data, [], [0, 0])
                        ast.children.append(root_node)
                    finally:
                        self._pending_tasks.remove(future)
                except tomli.TOMLDecodeError as e:
                    log(f"Error parsing TOML structure: {e}", level="error")
                    ast.metadata["parse_error"] = str(e)
                
                # Handle any remaining comments
                if current_comment_block:
                    ast.metadata["trailing_comments"] = current_comment_block
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing TOML content: {e}", level="error")
                return TomlNode(
                    type="document", start_point=[0, 0], end_point=[0, 0],
                    error=str(e), children=[]
                ).__dict__
    
    def _process_value(self, value: Any, path: List[str], start_point: List[int]) -> TomlNode:
        """Process a TOML value into a node structure."""
        node = self._create_node(
            type(value).__name__,
            start_point,
            [start_point[0], start_point[1] + len(str(value))],
            path='.'.join(path)
        )
        
        if isinstance(value, dict):
            node.type = "table"
            for key, val in value.items():
                child = self._process_value(
                    val,
                    path + [str(key)],
                    [start_point[0], start_point[1] + 1]
                )
                child.key = key
                node.children.append(child)
        elif isinstance(value, list):
            node.type = "array"
            for i, item in enumerate(value):
                child = self._process_value(
                    item,
                    path + [f"[{i}]"],
                    [start_point[0], start_point[1] + 1]
                )
                node.children.append(child)
        else:
            node.type = "value"
            node.value = value
            
        return node
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from TOML files for repository learning.
        
        Args:
            source_code: The content of the TOML file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary(operation_name="TOML pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                future = submit_async_task(self._parse_source(source_code))
                self._pending_tasks.add(future)
                try:
                    ast = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                # Extract table patterns
                table_patterns = self._extract_table_patterns(ast)
                for table in table_patterns:
                    patterns.append({
                        'name': f'toml_table_{table["name"]}',
                        'content': table["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'table',
                            'name': table["name"],
                            'keys': table.get("keys", [])
                        }
                    })
                
                # Extract array patterns
                array_patterns = self._extract_array_patterns(ast)
                for array in array_patterns:
                    patterns.append({
                        'name': f'toml_array_{array["type"]}',
                        'content': array["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'array',
                            'item_type': array["item_type"],
                            'length': array["length"]
                        }
                    })
                
                # Extract value patterns
                value_patterns = self._extract_value_patterns(ast)
                for value in value_patterns:
                    patterns.append({
                        'name': f'toml_value_{value["type"]}',
                        'content': value["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'value',
                            'value_type': value["type"],
                            'examples': value.get("examples", [])
                        }
                    })
                
                # Extract comment patterns
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({
                        'name': f'toml_comment_{comment["type"]}',
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
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error extracting patterns from TOML file: {str(e)}", level="error")
                return []
    
    async def cleanup(self):
        """Clean up TOML parser resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("TOML parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up TOML parser: {e}", level="error")

    def _extract_table_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract table patterns from the AST."""
        tables = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'table':
                    tables.append({
                        'name': node.get('path', 'unknown'),
                        'content': str(node),
                        'key_count': len(node.get('metadata', {}).get('keys', [])) if node.get('metadata') else 0
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return tables
        
    def _extract_array_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract array patterns from the AST."""
        arrays = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'array':
                    arrays.append({
                        'name': node.get('path', 'unknown'),
                        'content': str(node),
                        'item_count': node.get('metadata', {}).get('length', 0) if node.get('metadata') else 0
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return arrays
        
    def _extract_value_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract value patterns from the AST."""
        values = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'value':
                    values.append({
                        'type': node.get('path', 'unknown'),
                        'content': f"{node.get('path', '')} = {node.get('value', '')}",
                        'examples': []
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return values
        
    def _extract_comment_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract comment patterns from the AST."""
        comments = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'comment_block':
                    comments.append({
                        'type': 'block',
                        'content': node.get('content', ''),
                        'examples': []
                    })
                elif node.get('type') == 'comment':
                    comments.append({
                        'type': 'inline',
                        'content': node.get('content', ''),
                        'examples': []
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return comments 