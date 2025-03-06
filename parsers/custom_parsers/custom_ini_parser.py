"""Custom parser for INI files with enhanced documentation features."""

from .base_imports import *
import configparser
import re
from collections import Counter


class IniParser(BaseParser, CustomParserMixin):
    """Parser for INI files."""
    
    def __init__(self, language_id: str = "ini", file_type: Optional[FileType] = None):
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
                async with AsyncErrorBoundary("INI parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
                    self._initialized = True
                    log("INI parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing INI parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> IniNodeDict:
        """Create a standardized INI AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "section": kwargs.get("section"),
            "properties": kwargs.get("properties", [])
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse INI content into AST structure."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="INI parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
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
                
                # Parse INI structure
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
                    log(f"Error parsing INI structure: {e}", level="error")
                    ast.metadata["parse_error"] = str(e)
                
                # Handle any remaining comments
                if current_comment_block:
                    ast.metadata["trailing_comments"] = current_comment_block
                
                # Store result in cache
                await self._store_parse_result(source_code, ast.__dict__)
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing INI content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                )
    
    def _process_config(self, config: configparser.ConfigParser, start_point: List[int]) -> IniNodeDict:
        """Process a ConfigParser object into a node structure."""
        node = self._create_node(
            "root",
            start_point,
            [start_point[0], start_point[1] + 1],
            sections=list(config.sections())
        )
        
        # Process default section first
        if config.defaults():
            default_node = self._create_node(
                "section",
                start_point,
                [start_point[0], start_point[1] + 1],
                name="DEFAULT",
                options=list(config.defaults().keys())
            )
            for key, value in config.defaults().items():
                option_node = self._create_node(
                    "option",
                    [start_point[0], start_point[1] + 1],
                    [start_point[0], start_point[1] + len(key) + len(str(value)) + 3],
                    key=key,
                    value=value
                )
                default_node.children.append(option_node)
            node.children.append(default_node)
        
        # Process other sections
        for section in config.sections():
            section_node = self._create_node(
                "section",
                [start_point[0], start_point[1] + 1],
                [start_point[0], start_point[1] + len(section) + 2],
                name=section,
                options=list(config.options(section))
            )
            
            for key in config.options(section):
                value = config.get(section, key)
                option_node = self._create_node(
                    "option",
                    [start_point[0], start_point[1] + 1],
                    [start_point[0], start_point[1] + len(key) + len(str(value)) + 3],
                    key=key,
                    value=value
                )
                section_node.children.append(option_node)
            
            node.children.append(section_node)
        
        return node
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from INI files for repository learning."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="INI pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
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
                        'name': f'ini_section_{section["type"]}',
                        'content': section["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'section',
                            'name': section["name"],
                            'options': section.get("options", [])
                        }
                    })
                
                # Extract option patterns
                option_patterns = self._extract_option_patterns(ast)
                for option in option_patterns:
                    patterns.append({
                        'name': f'ini_option_{option["type"]}',
                        'content': option["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'option',
                            'value_type': option["value_type"],
                            'examples': option.get("examples", [])
                        }
                    })
                
                # Extract comment patterns
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({
                        'name': f'ini_comment_{comment["type"]}',
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
                log(f"Error extracting patterns from INI file: {str(e)}", level="error")
                return []
    
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process INI file with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("INI AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse INI file"
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
                log(f"Error in INI AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

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
        
        # Analyze naming conventions
        understanding["naming"] = await self._analyze_naming_conventions(ast)
        
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
        """Analyze patterns in the INI configuration."""
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

    async def _analyze_naming_conventions(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze naming conventions in the INI configuration."""
        naming = {}
        
        # Analyze section naming conventions
        naming["section_naming"] = self._analyze_section_naming(ast)
        
        # Analyze property naming conventions
        naming["property_naming"] = self._analyze_property_naming(ast)
        
        # Analyze grouping patterns
        naming["grouping"] = self._analyze_grouping(ast)
        
        return naming

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
            log("INI parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up INI parser: {e}", level="error")

    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        sections = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'section':
                properties = []
                
                # Extract properties from this section
                for child in node.get('children', []):
                    if isinstance(child, dict) and child.get('type') == 'option':
                        properties.append({
                            'key': child.get('key', ''),
                            'value': child.get('value', '')
                        })
                
                section_name = node.get('name', '')
                if section_name:
                    sections.append({
                        'name': section_name,
                        'content': f"[{section_name}]\n" + "\n".join(f"{prop['key']} = {prop['value']}" for prop in properties[:3]),
                        'options': properties
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return sections
        
    def _extract_option_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract common property patterns from the AST."""
        property_categories = {}
        
        def collect_properties(node, categories=None):
            if categories is None:
                categories = {}
                
            if isinstance(node, dict):
                # Check properties directly
                if node.get('type') == 'option':
                    key = node.get('key', '').lower()
                    value = node.get('value', '')
                    
                    # Categorize properties
                    if any(term in key for term in ['host', 'server', 'url', 'endpoint']):
                        category = 'connection'
                    elif any(term in key for term in ['user', 'password', 'auth', 'token', 'key', 'secret']):
                        category = 'authentication'
                    elif any(term in key for term in ['log', 'debug', 'verbose', 'trace']):
                        category = 'logging'
                    elif any(term in key for term in ['dir', 'path', 'file', 'folder']):
                        category = 'filesystem'
                    elif any(term in key for term in ['port', 'timeout', 'retry', 'max', 'min']):
                        category = 'connection_params'
                    elif any(term in key for term in ['enable', 'disable', 'toggle', 'feature']):
                        category = 'feature_flags'
                    else:
                        category = 'other'
                        
                    if category not in categories:
                        categories[category] = []
                        
                    categories[category].append({
                        'key': key,
                        'value': value
                    })
                
                # Process children recursively
                for child in node.get('children', []):
                    collect_properties(child, categories)
                    
            return categories
            
        # Collect properties by category
        property_categories = collect_properties(ast)
        
        # Create patterns for each category
        patterns = []
        for category, properties in property_categories.items():
            if properties:  # Only include non-empty categories
                patterns.append({
                    'category': category,
                    'content': "\n".join(f"{prop['key']} = {prop['value']}" for prop in properties[:3]),
                    'value_type': category,
                    'examples': properties[:3]
                })
                
        return patterns
        
    def _extract_comment_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract comment patterns from the AST."""
        comments = []
        
        def collect_comments(node):
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
                    collect_comments(child)
                    
        collect_comments(ast)
        
        return comments
        
    def _detect_naming_conventions(self, names: List[str]) -> List[str]:
        """Detect naming conventions in a list of names."""
        if not names:
            return []
            
        conventions = []
        
        # Check for camelCase
        if any(re.match(r'^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name) for name in names):
            conventions.append("camelCase")
            
        # Check for snake_case
        if any(re.match(r'^[a-z][a-z0-9_]*$', name) and '_' in name for name in names):
            conventions.append("snake_case")
            
        # Check for kebab-case
        if any(re.match(r'^[a-z][a-z0-9-]*$', name) and '-' in name for name in names):
            conventions.append("kebab-case")
            
        # Check for PascalCase
        if any(re.match(r'^[A-Z][a-zA-Z0-9]*$', name) for name in names):
            conventions.append("PascalCase")
            
        # Check for UPPER_CASE
        if any(re.match(r'^[A-Z][A-Z0-9_]*$', name) and '_' in name for name in names):
            conventions.append("UPPER_CASE")
            
        # Check for lowercase
        if any(re.match(r'^[a-z][a-z0-9]*$', name) for name in names):
            conventions.append("lowercase")
            
        # Determine the most common convention
        if conventions:
            convention_counts = Counter(
                convention for name in names for convention in conventions 
                if self._matches_convention(name, convention)
            )
            
            if convention_counts:
                dominant_convention = convention_counts.most_common(1)[0][0]
                return [dominant_convention]
                
        return conventions
        
    def _matches_convention(self, name: str, convention: str) -> bool:
        """Check if a name matches a specific naming convention."""
        if convention == "camelCase":
            return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name))
        elif convention == "snake_case":
            return bool(re.match(r'^[a-z][a-z0-9_]*$', name) and '_' in name)
        elif convention == "kebab-case":
            return bool(re.match(r'^[a-z][a-z0-9-]*$', name) and '-' in name)
        elif convention == "PascalCase":
            return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))
        elif convention == "UPPER_CASE":
            return bool(re.match(r'^[A-Z][A-Z0-9_]*$', name) and '_' in name)
        elif convention == "lowercase":
            return bool(re.match(r'^[a-z][a-z0-9]*$', name))
        return False 