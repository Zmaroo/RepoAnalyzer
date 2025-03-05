"""
Custom GraphQL parser.

This parser uses regexes to capture common GraphQL definitions such as type, interface,
enum, or schema definitions from a GraphQL file.
"""

from typing import Dict, List, Any, Optional
import asyncio
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.graphql import GRAPHQL_PATTERNS
from parsers.models import GraphqlNode, PatternType
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, ErrorSeverity, handle_async_errors, AsyncErrorBoundary
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
import re

class GraphqlParser(BaseParser):
    """Parser for GraphQL files."""
    
    def __init__(self, language_id: str = "graphql", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.SCHEMA, parser_type=ParserType.CUSTOM)
        self._initialized = False
        self._pending_tasks: set[asyncio.Future] = set()
        self.patterns = self._compile_patterns(GRAPHQL_PATTERNS)
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("GraphQL parser initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    log("GraphQL parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing GraphQL parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> GraphqlNode:
        """Create a standardized GraphQL AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return GraphqlNode(**node_dict)

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse GraphQL content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary(operation_name="GraphQL parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
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
                
                # Process GraphQL structure
                current_type = None
                current_field = None
                
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    
                    # Skip empty lines and comments
                    if not line.strip() or line.strip().startswith('#'):
                        continue
                    
                    # Handle type definitions
                    if type_match := re.match(r'^\s*(type|interface|enum|union|input|scalar)\s+(\w+)', line):
                        if current_type:
                            ast.children.append(current_type)
                        
                        type_kind = type_match.group(1)
                        type_name = type_match.group(2)
                        current_type = self._create_node(
                            "type_definition",
                            line_start,
                            line_end,
                            kind=type_kind,
                            name=type_name,
                            fields=[]
                        )
                        continue
                    
                    # Handle field definitions
                    if current_type and (field_match := re.match(r'^\s*(\w+)(?:\(([^)]*)\))?\s*:\s*(\w+)(?:!|\[|\s|$)', line)):
                        field_name = field_match.group(1)
                        field_args = field_match.group(2)
                        field_type = field_match.group(3)
                        
                        field = self._create_node(
                            "field_definition",
                            line_start,
                            line_end,
                            name=field_name,
                            type=field_type,
                            arguments=self._parse_arguments(field_args) if field_args else []
                        )
                        current_type.fields.append(field)
                        continue
                    
                    # Handle enum values
                    if current_type and current_type.kind == 'enum' and (enum_match := re.match(r'^\s*(\w+)\s*$', line)):
                        enum_value = enum_match.group(1)
                        field = self._create_node(
                            "enum_value",
                            line_start,
                            line_end,
                            value=enum_value
                        )
                        current_type.fields.append(field)
                        continue
                
                # Add the last type definition if any
                if current_type:
                    ast.children.append(current_type)
                
                # Handle any remaining comments
                if current_comment_block:
                    ast.metadata["trailing_comments"] = current_comment_block
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing GraphQL content: {e}", level="error")
                return GraphqlNode(
                    type="document", start_point=[0, 0], end_point=[0, 0],
                    error=str(e), children=[]
                ).__dict__
    
    def _parse_arguments(self, args_str: str) -> List[Dict[str, Any]]:
        """Parse GraphQL field arguments."""
        args = []
        if not args_str:
            return args
            
        # Split on commas, but handle nested structures
        parts = []
        current = []
        depth = 0
        
        for char in args_str:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ',' and depth == 0:
                parts.append(''.join(current).strip())
                current = []
                continue
            current.append(char)
            
        if current:
            parts.append(''.join(current).strip())
        
        # Parse each argument
        for part in parts:
            if arg_match := re.match(r'(\w+)\s*:\s*(\w+)(?:!|\[|\s|$)', part):
                args.append({
                    'name': arg_match.group(1),
                    'type': arg_match.group(2)
                })
        
        return args
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from GraphQL files for repository learning.
        
        Args:
            source_code: The content of the GraphQL file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary(operation_name="GraphQL pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                future = submit_async_task(self._parse_source(source_code))
                self._pending_tasks.add(future)
                try:
                    ast = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                # Extract type patterns
                type_patterns = self._extract_type_patterns(ast)
                for type_pattern in type_patterns:
                    patterns.append({
                        'name': f'graphql_type_{type_pattern["kind"]}',
                        'content': type_pattern["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'type_definition',
                            'kind': type_pattern["kind"],
                            'fields': type_pattern.get("fields", [])
                        }
                    })
                
                # Extract field patterns
                field_patterns = self._extract_field_patterns(ast)
                for field_pattern in field_patterns:
                    patterns.append({
                        'name': f'graphql_field_{field_pattern["type"]}',
                        'content': field_pattern["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'field_definition',
                            'field_type': field_pattern["type"],
                            'examples': field_pattern.get("examples", [])
                        }
                    })
                
                # Extract argument patterns
                arg_patterns = self._extract_argument_patterns(ast)
                for arg_pattern in arg_patterns:
                    patterns.append({
                        'name': f'graphql_argument_{arg_pattern["type"]}',
                        'content': arg_pattern["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'argument_definition',
                            'arg_type': arg_pattern["type"],
                            'examples': arg_pattern.get("examples", [])
                        }
                    })
                
                # Extract comment patterns
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({
                        'name': f'graphql_comment_{comment["type"]}',
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
                log(f"Error extracting patterns from GraphQL file: {str(e)}", level="error")
                return []
    
    async def cleanup(self):
        """Clean up GraphQL parser resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("GraphQL parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up GraphQL parser: {e}", level="error")

    def _extract_type_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract type patterns from the AST."""
        types = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'type':
                fields = []
                
                # Extract fields from this type
                for child in node.get('children', []):
                    if child.get('type') == 'field':
                        fields.append({
                            'name': child.get('name', ''),
                            'field_type': child.get('field_type', '')
                        })
                
                types.append({
                    'name': node.get('name', ''),
                    'content': str(node),  # Simplified - could extract actual content
                    'fields': fields
                })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return types
        
    def _extract_field_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract field patterns from the AST."""
        fields = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'field':
                fields.append({
                    'name': node.get('name', ''),
                    'type': node.get('type', ''),
                    'arguments': node.get('arguments', []),
                    'examples': []
                })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return fields
        
    def _extract_argument_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract argument patterns from the AST."""
        arguments = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'field':
                for arg in node.get('arguments', []):
                    arguments.append({
                        'name': arg.get('name', ''),
                        'type': arg.get('type', ''),
                        'examples': []
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return arguments
        
    def _extract_comment_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract comment patterns from the AST."""
        comments = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'comment':
                comments.append({
                    'type': node.get('style', ''),
                    'content': node.get('content', '')
                })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return comments