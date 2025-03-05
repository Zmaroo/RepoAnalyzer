"""
Custom .env file parser.

This parser processes .env files by extracting key=value pairs.
Comments (lines starting with #) are skipped (or can be used as documentation).
"""

from .base_imports import *
import re

class EnvParser(BaseParser, CustomParserMixin):
    """Parser for .env files."""
    
    def __init__(self, language_id: str = "env", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("ENV parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()  # Load patterns through BaseParser mechanism
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
    ) -> EnvNodeDict:
        """Create a standardized ENV AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "name": kwargs.get("name"),
            "value": kwargs.get("value"),
            "value_type": kwargs.get("value_type")
        }

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
            
        async with AsyncErrorBoundary(operation_name="env file parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                # Check cache first
                cached_result = await self._check_parse_cache(source_code)
                if cached_result:
                    return cached_result
                    
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
                
                # Store result in cache
                await self._store_parse_result(source_code, ast.__dict__)
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
        """Extract patterns from env file content."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="env pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                # Check features cache first
                ast = await self._parse_source(source_code)
                cached_features = await self._check_features_cache(ast, source_code)
                if cached_features:
                    return cached_features
                
                # Extract patterns
                patterns = []
                
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
                
                # Store features in cache
                await self._store_features_in_cache(ast, source_code, patterns)
                return patterns
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error extracting patterns from ENV file: {str(e)}", level="error")
                return []
        
    async def cleanup(self):
        """Clean up ENV parser resources."""
        try:
            await self._cleanup_cache()
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