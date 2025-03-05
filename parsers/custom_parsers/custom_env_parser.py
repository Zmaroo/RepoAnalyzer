"""
Custom .env file parser.

This parser processes .env files by extracting key=value pairs.
Comments (lines starting with #) are skipped (or can be used as documentation).
"""

from typing import Dict, List, Any, Optional, Tuple
import asyncio
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.models import EnvNode, PatternType
from parsers.query_patterns.env import ENV_PATTERNS
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, ErrorSeverity, handle_async_errors, AsyncErrorBoundary
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
import re

class EnvParser(BaseParser):
    """Parser for .env files."""
    
    def __init__(self, language_id: str = "env", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        self._initialized = False
        self._pending_tasks: set[asyncio.Future] = set()
        self.patterns = self._compile_patterns(ENV_PATTERNS)
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("ENV parser initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    log("ENV parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing ENV parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> EnvNode:
        """Create a standardized ENV AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return EnvNode(**node_dict)

    def _process_value(self, value: str) -> Tuple[str, str]:
        """Process a value that might be quoted or multiline."""
        if value.startswith('"') or value.startswith("'"):
            quote = value[0]
            if value.endswith(quote) and len(value) > 1:
                return value[1:-1], "quoted"
        elif value.startswith('`') and value.endswith('`'):
            return value[1:-1], "multiline"
        return value, "raw"

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse env content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary(operation_name="env file parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                lines = source_code.splitlines()
                ast = self._create_node(
                    "env_file",
                    [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0],
                    children=[]
                )
                
                # Process comments first
                current_comment_block = []
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    
                    # Skip empty lines
                    if not line.strip():
                        continue
                    
                    # Handle comments
                    if comment_match := re.match(r'^\s*#\s*(.*)$', line):
                        current_comment_block.append(comment_match.group(1).strip())
                        continue
                    
                    # Process any pending comments
                    if current_comment_block:
                        node = self._create_node(
                            "comment_block",
                            [i - len(current_comment_block), 0],
                            [i - 1, len(current_comment_block[-1])],
                            content="\n".join(current_comment_block)
                        )
                        ast.children.append(node)
                        current_comment_block = []
                    
                    # Handle variable assignments
                    if var_match := re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line):
                        key = var_match.group(1)
                        value = var_match.group(2).strip()
                        
                        # Remove quotes if present
                        if (value.startswith('"') and value.endswith('"')) or \
                           (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                        
                        node = self._create_node(
                            "variable",
                            line_start,
                            line_end,
                            key=key,
                            value=value
                        )
                        ast.children.append(node)
                
                # Handle any remaining comments
                if current_comment_block:
                    ast.metadata["trailing_comments"] = current_comment_block
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing ENV file: {str(e)}", level="error")
                # Return a minimal valid AST structure on error
                return self._create_node(
                    "env_file",
                    [0, 0],
                    [0, 0],
                    variables=[]
                )
            
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from env file content.
        
        Args:
            source_code: The content of the env file
            
        Returns:
            List of extracted pattern dictionaries
        """
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary(operation_name="env pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                future = submit_async_task(self._parse_source(source_code))
                self._pending_tasks.add(future)
                try:
                    ast = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                # Extract variable patterns
                var_patterns = self._extract_variable_patterns(ast)
                for var in var_patterns:
                    patterns.append({
                        'name': f'env_variable_{var["type"]}',
                        'content': var["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'variable',
                            'variable_type': var["type"],
                            'examples': var.get("examples", [])
                        }
                    })
                
                # Extract comment patterns
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({
                        'name': f'env_comment_{comment["type"]}',
                        'content': comment["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'comment',
                            'style': comment["type"]
                        }
                    })
                    
                return patterns
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error extracting patterns from ENV file: {str(e)}", level="error")
                return []
        
    async def cleanup(self):
        """Clean up ENV parser resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("ENV parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up ENV parser: {e}", level="error")

    def _extract_variable_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract variable patterns from the AST."""
        variables = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'variable':
                key = node.get('key', '').upper()
                value = node.get('value', '')
                
                # Categorize variables
                if any(term in key for term in ['HOST', 'URL', 'ENDPOINT', 'API']):
                    var_type = 'connection'
                elif any(term in key for term in ['USER', 'PASS', 'AUTH', 'TOKEN', 'KEY', 'SECRET']):
                    var_type = 'authentication'
                elif any(term in key for term in ['LOG', 'DEBUG', 'VERBOSE', 'TRACE']):
                    var_type = 'logging'
                elif any(term in key for term in ['DIR', 'PATH', 'FILE', 'FOLDER']):
                    var_type = 'filesystem'
                elif any(term in key for term in ['PORT', 'TIMEOUT', 'RETRY', 'MAX', 'MIN']):
                    var_type = 'connection_params'
                elif any(term in key for term in ['ENABLE', 'DISABLE', 'TOGGLE', 'FEATURE']):
                    var_type = 'feature_flags'
                else:
                    var_type = 'other'
                    
                variables.append({
                    'type': var_type,
                    'content': f"{key}={value}",
                    'examples': [{'key': key, 'value': value}]
                })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return variables
        
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