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
                async with AsyncErrorBoundary("ENV parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
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

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process ENV file with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("ENV AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse ENV file"
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
                log(f"Error in ENV AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_understanding(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with environment variable understanding capability."""
        understanding = {}
        
        # Analyze variable structure
        understanding["structure"] = {
            "variables": self._extract_variable_patterns(ast)[0],
            "comments": self._extract_comment_patterns(ast)
        }
        
        # Analyze variable patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze variable naming
        understanding["naming"] = await self._analyze_variable_naming(ast)
        
        return understanding

    async def _process_with_generation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Process with environment variable generation capability."""
        suggestions = []
        
        # Generate variable suggestions
        if var_suggestions := await self._generate_variable_suggestions(ast):
            suggestions.extend(var_suggestions)
        
        # Generate documentation suggestions
        if doc_suggestions := await self._generate_documentation_suggestions(ast):
            suggestions.extend(doc_suggestions)
        
        # Generate security suggestions
        if security_suggestions := await self._generate_security_suggestions(ast):
            suggestions.extend(security_suggestions)
        
        return suggestions

    async def _process_with_modification(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with environment variable modification capability."""
        modifications = {}
        
        # Suggest variable improvements
        if improvements := await self._suggest_variable_improvements(ast):
            modifications["variable_improvements"] = improvements
        
        # Suggest security improvements
        if security := await self._suggest_security_improvements(ast):
            modifications["security_improvements"] = security
        
        # Suggest documentation improvements
        if doc_improvements := await self._suggest_documentation_improvements(ast):
            modifications["documentation_improvements"] = doc_improvements
        
        return modifications

    async def _process_with_review(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with environment variable review capability."""
        review = {}
        
        # Review variable usage
        if variable_review := await self._review_variables(ast):
            review["variables"] = variable_review
        
        # Review security
        if security_review := await self._review_security(ast):
            review["security"] = security_review
        
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
        
        # Learn variable patterns
        if variable_patterns := await self._learn_variable_patterns(ast):
            patterns.extend(variable_patterns)
        
        # Learn naming patterns
        if naming_patterns := await self._learn_naming_patterns(ast):
            patterns.extend(naming_patterns)
        
        # Learn documentation patterns
        if doc_patterns := await self._learn_documentation_patterns(ast):
            patterns.extend(doc_patterns)
        
        return patterns

    async def _analyze_patterns(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze patterns in the environment variables."""
        patterns = {}
        
        # Analyze variable patterns
        patterns["variable_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.SYNTAX,
            context
        )
        
        # Analyze naming patterns
        patterns["naming_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.NAMING,
            context
        )
        
        # Analyze documentation patterns
        patterns["documentation_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.DOCUMENTATION,
            context
        )
        
        return patterns

    async def _analyze_variable_naming(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze variable naming conventions."""
        naming = {}
        
        # Analyze variable case style
        naming["case_style"] = self._analyze_case_style(ast)
        
        # Analyze prefix/suffix patterns
        naming["affixes"] = self._analyze_affixes(ast)
        
        # Analyze grouping patterns
        naming["grouping"] = self._analyze_grouping(ast)
        
        return naming