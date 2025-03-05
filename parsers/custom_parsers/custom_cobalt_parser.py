"""
Custom parser for the Cobalt programming language.
"""

from .base_imports import *
import re

class CobaltParser(BaseParser, CustomParserMixin):
    """Parser for the Cobalt programming language."""
    
    def __init__(self, language_id: str = "cobalt", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.CODE, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self.patterns = self._compile_patterns(COBALT_PATTERNS)
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("Cobalt parser initialization"):
                    await self._initialize_cache(self.language_id)
                    self._initialized = True
                    log("Cobalt parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing Cobalt parser: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up parser resources."""
        try:
            await self._cleanup_cache()
            log("Cobalt parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up Cobalt parser: {e}", level="error")

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> CobaltNodeDict:
        """Create a standardized Cobalt AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "name": kwargs.get("name"),
            "parameters": kwargs.get("parameters", []),
            "return_type": kwargs.get("return_type")
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse Cobalt content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()

        async with AsyncErrorBoundary(operation_name="Cobalt parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                # Check cache first
                cached_result = await self._check_parse_cache(source_code)
                if cached_result:
                    return cached_result
                    
                task = asyncio.create_task(self._parse_content(source_code))
                self._pending_tasks.add(task)
                try:
                    ast = await task
                    # Store result in cache
                    await self._store_parse_result(source_code, ast)
                    return ast
                finally:
                    self._pending_tasks.remove(task)
                
            except (ValueError, KeyError, TypeError, StopIteration) as e:
                log(f"Error parsing Cobalt content: {e}", level="error")
                return self._create_node(
                    "module",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__

    def _parse_content(self, source_code: str) -> Dict[str, Any]:
        """Internal method to parse Cobalt content synchronously."""
        lines = source_code.splitlines()
        ast = self._create_node(
            "module",
            [0, 0],
            [len(lines) - 1, len(lines[-1]) if lines else 0]
        )
        
        current_doc = []
        current_scope = [ast]
        
        for i, line in enumerate(lines):
            line_start = [i, 0]
            line_end = [i, len(line)]
            
            # Process docstrings.
            if doc_match := self.patterns['docstring'].match(line):
                current_doc.append(doc_match.group(1))
                continue
                
            # Process regular comments.
            if comment_match := self.patterns['comment'].match(line):
                current_scope[-1].children.append(
                    self._create_node(
                        "comment",
                        line_start,
                        line_end,
                        content=comment_match.group(1)
                    )
                )
                continue
            
            # Handle scope openings.
            if line.strip().endswith("{"):
                # Look for declarations that open new scopes.
                for pattern_name in ['function', 'class', 'namespace']:
                    if pattern_name in self.patterns and (match := self.patterns[pattern_name].match(line)):
                        node_data = COBALT_PATTERNS[PatternCategory.SYNTAX][pattern_name].extract(match)
                        node = self._create_node(
                            pattern_name,
                            line_start,
                            None,  # End point to be set when scope closes.
                            **node_data
                        )
                        if current_doc:
                            node.metadata["documentation"] = "\n".join(current_doc)
                            current_doc = []
                        current_scope[-1].children.append(node)
                        current_scope.append(node)
                        break
            
            elif line.strip() == "}":
                if len(current_scope) > 1:
                    current_scope[-1].end_point = line_end
                    current_scope.pop()
                continue
            
            # Flush accumulated docstrings before declarations.
            if current_doc and not line.strip().startswith("///"):
                current_scope[-1].children.append(
                    self._create_node(
                        "docstring",
                        [i - len(current_doc), 0],
                        [i - 1, len(current_doc[-1])],
                        content="\n".join(current_doc)
                    )
                )
                current_doc = []
            
            # Process other declarations.
            for pattern_name, pattern in self.patterns.items():
                if pattern_name in ['docstring', 'comment', 'function', 'class', 'namespace']:
                    continue
                
                if match := pattern.match(line):
                    category = next(
                        cat for cat, patterns in COBALT_PATTERNS.items()
                        if pattern_name in patterns
                    )
                    node_data = COBALT_PATTERNS[category][pattern_name].extract(match)
                    node = self._create_node(
                        pattern_name,
                        line_start,
                        line_end,
                        **node_data
                    )
                    current_scope[-1].children.append(node)
                    break
        
        return ast.__dict__

    @handle_errors(error_types=(ProcessingError,))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract code patterns from Cobalt files for repository learning.
        
        Args:
            source_code: The content of the Cobalt file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()

        async with AsyncErrorBoundary(operation_name="Cobalt pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                # Check features cache first
                ast = await self._parse_source(source_code)
                cached_features = await self._check_features_cache(ast, source_code)
                if cached_features:
                    return cached_features
                
                # Extract patterns asynchronously
                task = asyncio.create_task(self._extract_all_patterns(ast))
                self._pending_tasks.add(task)
                try:
                    patterns = await task
                    # Store features in cache
                    await self._store_features_in_cache(ast, source_code, patterns)
                    return patterns
                finally:
                    self._pending_tasks.remove(task)
                    
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error extracting Cobalt patterns: {e}", level="error")
                
        return []

    def _extract_all_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all patterns from the AST synchronously."""
        patterns = []
        
        # Extract function patterns
        function_patterns = self._extract_function_patterns(ast)
        for function in function_patterns:
            patterns.append({
                'name': f'function_{function["name"]}',
                'content': function["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.85,
                'metadata': {
                    'type': 'function',
                    'name': function["name"],
                    'params': function.get("params", [])
                }
            })
        
        # Extract class patterns
        class_patterns = self._extract_class_patterns(ast)
        for class_pattern in class_patterns:
            patterns.append({
                'name': f'class_{class_pattern["name"]}',
                'content': class_pattern["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.8,
                'metadata': {
                    'type': 'class',
                    'name': class_pattern["name"],
                    'methods': class_pattern.get("methods", [])
                }
            })
            
        # Extract error handling patterns
        error_patterns = self._extract_error_handling_patterns(ast)
        for error_pattern in error_patterns:
            patterns.append(error_pattern)
            
        # Extract naming convention patterns
        naming_patterns = self._extract_naming_patterns(ast)
        for naming in naming_patterns:
            patterns.append(naming)
            
        return patterns
        
    def _extract_function_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract function patterns from the AST."""
        functions = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'function':
                functions.append({
                    'name': node.get('name', ''),
                    'content': str(node),  # Simplified - could extract actual content
                    'parameters': node.get('parameters', []),
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return functions
        
    def _extract_class_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract class patterns from the AST."""
        classes = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'class':
                # Extract methods within the class
                methods = []
                for child in node.get('children', []):
                    if child.get('type') == 'function':
                        methods.append({
                            'name': child.get('name', ''),
                            'parameters': child.get('parameters', [])
                        })
                
                classes.append({
                    'name': node.get('name', ''),
                    'content': str(node),  # Simplified - could extract actual content
                    'methods': methods,
                    'start_point': node.get('start_point', [0, 0]),
                    'end_point': node.get('end_point', [0, 0])
                })
            
            for child in node.get('children', []):
                process_node(child)
                
        process_node(ast)
        return classes
        
    def _extract_error_handling_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract error handling patterns from the AST."""
        error_patterns = []
        
        # In a real implementation, this would scan the AST for try/catch blocks or similar
        # This is a placeholder implementation
        error_patterns.append({
            'type': 'try_catch',
            'content': 'try { ... } catch (Error e) { ... }',  # Placeholder
            'start_point': [0, 0],
            'end_point': [0, 0]
        })
                
        return error_patterns
        
    def _extract_naming_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract naming convention patterns from the AST."""
        naming_patterns = []
        
        # This would analyze function and variable names to detect patterns
        # For now, we'll use a simplified implementation
        naming_patterns.append({
            'category': 'function',
            'pattern': r'[a-z][a-zA-Z0-9]*',  # camelCase
            'examples': 'doSomething, calculateTotal'
        })
        
        naming_patterns.append({
            'category': 'class',
            'pattern': r'[A-Z][a-zA-Z0-9]*',  # PascalCase
            'examples': 'UserAccount, DataProcessor'
        })
                
        return naming_patterns 