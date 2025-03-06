"""Custom parser for TOML files."""

from .base_imports import *
import tomli
import re
from collections import Counter
from parsers.query_patterns.toml import TOML_PATTERNS

class TomlParser(BaseParser, CustomParserMixin):
    """Parser for TOML files."""
    
    def __init__(self, language_id: str = "toml", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.DATA, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
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
                async with AsyncErrorBoundary("TOML parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
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
    ) -> TomlNodeDict:
        """Create a standardized TOML AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "value": kwargs.get("value"),
            "path": kwargs.get("path")
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse TOML content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="TOML parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
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
                    task = asyncio.create_task(self._parse_toml(source_code))
                    self._pending_tasks.add(task)
                    try:
                        data = await task
                        root_node = self._process_value(data, [], [0, 0])
                        ast.children.append(root_node)
                    finally:
                        self._pending_tasks.remove(task)
                except tomli.TOMLDecodeError as e:
                    log(f"Error parsing TOML structure: {e}", level="error")
                    ast.metadata["parse_error"] = str(e)
                
                # Handle any remaining comments
                if current_comment_block:
                    ast.metadata["trailing_comments"] = current_comment_block
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing TOML content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__
    
    async def _parse_toml(self, source_code: str) -> Dict[str, Any]:
        """Parse TOML content asynchronously."""
        return tomli.loads(source_code)

    def _process_value(self, value: Any, path: List[str], start_point: List[int]) -> TomlNodeDict:
        """Process a TOML value into a node structure."""
        node = self._create_node(
            type(value).__name__,
            start_point,
            [start_point[0], start_point[1] + len(str(value))],
            path='.'.join(path)
        )
        
        if isinstance(value, dict):
            node["type"] = "table"
            for key, val in value.items():
                child = self._process_value(
                    val,
                    path + [str(key)],
                    [start_point[0], start_point[1] + 1]
                )
                child["key"] = key
                node["children"].append(child)
        elif isinstance(value, list):
            node["type"] = "array"
            for i, item in enumerate(value):
                child = self._process_value(
                    item,
                    path + [f"[{i}]"],
                    [start_point[0], start_point[1] + 1]
                )
                node["children"].append(child)
        else:
            node["type"] = "value"
            node["value"] = value
            
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
            
        async with AsyncErrorBoundary(operation_name="TOML pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                task = asyncio.create_task(self._parse_source(source_code))
                self._pending_tasks.add(task)
                try:
                    ast = await task
                finally:
                    self._pending_tasks.remove(task)
                
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

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process TOML with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("TOML AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse TOML"
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
                log(f"Error in TOML AI processing: {e}", level="error")
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
            "tables": self._extract_table_patterns(ast),
            "arrays": self._extract_array_patterns(ast),
            "comments": self._extract_comment_patterns(ast)
        }
        
        # Analyze configuration patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze configuration style
        understanding["style"] = await self._analyze_config_style(ast)
        
        return understanding

    async def _process_with_generation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Process with configuration generation capability."""
        suggestions = []
        
        # Generate table suggestions
        if table_suggestions := await self._generate_table_suggestions(ast):
            suggestions.extend(table_suggestions)
        
        # Generate array suggestions
        if array_suggestions := await self._generate_array_suggestions(ast):
            suggestions.extend(array_suggestions)
        
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
        
        # Suggest formatting improvements
        if formatting := await self._suggest_formatting_improvements(ast):
            modifications["formatting_improvements"] = formatting
        
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
        
        # Review configuration formatting
        if format_review := await self._review_formatting(ast):
            review["formatting"] = format_review
        
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
        
        # Learn structure patterns
        if structure_patterns := await self._learn_structure_patterns(ast):
            patterns.extend(structure_patterns)
        
        # Learn formatting patterns
        if format_patterns := await self._learn_formatting_patterns(ast):
            patterns.extend(format_patterns)
        
        # Learn documentation patterns
        if doc_patterns := await self._learn_documentation_patterns(ast):
            patterns.extend(doc_patterns)
        
        return patterns

    async def _analyze_patterns(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze patterns in the TOML configuration."""
        patterns = {}
        
        # Analyze table patterns
        patterns["table_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.STRUCTURE,
            context
        )
        
        # Analyze array patterns
        patterns["array_patterns"] = await self._pattern_processor.analyze_patterns(
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

    async def _analyze_config_style(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze configuration style."""
        style = {}
        
        # Analyze table style
        style["table_style"] = self._analyze_table_style(ast)
        
        # Analyze array style
        style["array_style"] = self._analyze_array_style(ast)
        
        # Analyze documentation style
        style["documentation_style"] = self._analyze_documentation_style(ast)
        
        return style

    async def _generate_table_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate table suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing tables
        tables = self._extract_table_patterns(ast)
        
        # Suggest common missing tables
        common_tables = {
            "package": "Package metadata",
            "dependencies": "Project dependencies",
            "build": "Build configuration",
            "test": "Test configuration",
            "tool": "Tool-specific settings"
        }
        
        for name, description in common_tables.items():
            if not any(t["name"] == name for t in tables):
                suggestions.append(f"Add table '{name}' for {description}")
        
        return suggestions

    async def _generate_array_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate array suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing arrays
        arrays = self._extract_array_patterns(ast)
        
        # Suggest common missing arrays
        common_arrays = {
            "authors": "Project authors",
            "keywords": "Project keywords",
            "classifiers": "Project classifiers",
            "exclude": "Files to exclude",
            "include": "Files to include"
        }
        
        for name, description in common_arrays.items():
            if not any(a["name"] == name for a in arrays):
                suggestions.append(f"Add array '{name}' for {description}")
        
        return suggestions

    async def _generate_documentation_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate documentation suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing documentation
        comments = self._extract_comment_patterns(ast)
        
        # Suggest documentation improvements
        if not comments:
            suggestions.append("Add header comments describing the configuration")
        
        if not any(c["type"] == "section" for c in comments):
            suggestions.append("Add section comments explaining configuration choices")
        
        return suggestions

    async def _suggest_config_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest configuration improvements based on the AST."""
        improvements = {}
        
        # Analyze table structure
        tables = self._extract_table_patterns(ast)
        table_improvements = []
        
        for table in tables:
            if not table.get("key_count", 0):
                table_improvements.append(f"Add keys to empty table '{table['name']}'")
        
        if table_improvements:
            improvements["tables"] = table_improvements
        
        return improvements

    async def _suggest_formatting_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest formatting improvements based on the AST."""
        improvements = {}
        
        # Analyze array formatting
        arrays = self._extract_array_patterns(ast)
        array_improvements = []
        
        for array in arrays:
            if array.get("item_count", 0) > 5 and not array.get("multiline", False):
                array_improvements.append(f"Consider using multiline format for large array '{array['name']}'")
        
        if array_improvements:
            improvements["arrays"] = array_improvements
        
        return improvements

    async def _suggest_documentation_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest documentation improvements based on the AST."""
        improvements = {}
        
        # Analyze documentation completeness
        tables = self._extract_table_patterns(ast)
        doc_improvements = []
        
        for table in tables:
            if not table.get("documentation"):
                doc_improvements.append(f"Add documentation for table '{table['name']}'")
        
        if doc_improvements:
            improvements["documentation"] = doc_improvements
        
        return improvements

    async def _review_structure(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review configuration structure."""
        review = {}
        
        # Review table structure
        tables = self._extract_table_patterns(ast)
        if tables:
            review["tables"] = {
                "count": len(tables),
                "names": [t["name"] for t in tables],
                "key_counts": {t["name"]: t.get("key_count", 0) for t in tables}
            }
        
        # Review array structure
        arrays = self._extract_array_patterns(ast)
        if arrays:
            review["arrays"] = {
                "count": len(arrays),
                "names": [a["name"] for a in arrays],
                "item_counts": {a["name"]: a.get("item_count", 0) for a in arrays}
            }
        
        return review

    async def _review_formatting(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review configuration formatting."""
        review = {}
        
        # Review table formatting
        tables = self._extract_table_patterns(ast)
        if tables:
            review["table_formatting"] = {
                "indentation": all(t.get("indent", 0) >= 2 for t in tables),
                "empty_lines": all(t.get("has_empty_lines", False) for t in tables)
            }
        
        # Review array formatting
        arrays = self._extract_array_patterns(ast)
        if arrays:
            review["array_formatting"] = {
                "multiline": sum(1 for a in arrays if a.get("multiline", False)),
                "inline": sum(1 for a in arrays if not a.get("multiline", False))
            }
        
        return review

    async def _review_documentation(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review documentation quality."""
        review = {}
        
        # Review table documentation
        tables = self._extract_table_patterns(ast)
        if tables:
            review["table_docs"] = {
                "has_docs": sum(1 for t in tables if t.get("documentation")),
                "missing_docs": sum(1 for t in tables if not t.get("documentation"))
            }
        
        # Review comment quality
        comments = self._extract_comment_patterns(ast)
        if comments:
            review["comments"] = {
                "count": len(comments),
                "types": Counter(c["type"] for c in comments)
            }
        
        return review

    async def _learn_structure_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn structure patterns from the AST."""
        patterns = []
        
        # Learn table patterns
        tables = self._extract_table_patterns(ast)
        if tables:
            patterns.append({
                "type": "table_structure",
                "content": f"Configuration uses {len(tables)} tables",
                "examples": [t["name"] for t in tables[:3]]
            })
        
        # Learn array patterns
        arrays = self._extract_array_patterns(ast)
        if arrays:
            patterns.append({
                "type": "array_structure",
                "content": f"Configuration uses {len(arrays)} arrays",
                "examples": [a["name"] for a in arrays[:3]]
            })
        
        return patterns

    async def _learn_formatting_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn formatting patterns from the AST."""
        patterns = []
        
        # Learn table formatting patterns
        tables = self._extract_table_patterns(ast)
        if tables:
            indent_levels = set(t.get("indent", 0) for t in tables)
            patterns.append({
                "type": "table_formatting",
                "content": f"Configuration uses {len(indent_levels)} different table indentation levels",
                "examples": sorted(indent_levels)
            })
        
        # Learn array formatting patterns
        arrays = self._extract_array_patterns(ast)
        if arrays:
            multiline = sum(1 for a in arrays if a.get("multiline", False))
            inline = len(arrays) - multiline
            patterns.append({
                "type": "array_formatting",
                "content": f"Configuration uses {multiline} multiline and {inline} inline arrays",
                "examples": {"multiline": multiline, "inline": inline}
            })
        
        return patterns

    async def _learn_documentation_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn documentation patterns from the AST."""
        patterns = []
        
        # Learn table documentation patterns
        tables = self._extract_table_patterns(ast)
        if tables:
            documented = [t for t in tables if t.get("documentation")]
            patterns.append({
                "type": "table_documentation",
                "content": f"Configuration has {len(documented)} documented tables",
                "examples": [t["name"] for t in documented[:3]]
            })
        
        # Learn comment patterns
        comments = self._extract_comment_patterns(ast)
        if comments:
            comment_types = Counter(c["type"] for c in comments)
            patterns.append({
                "type": "comment_patterns",
                "content": f"Configuration uses {len(comment_types)} different comment types",
                "examples": dict(comment_types.most_common(3))
            })
        
        return patterns 