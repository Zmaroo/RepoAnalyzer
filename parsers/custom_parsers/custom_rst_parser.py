"""Custom parser for reStructuredText with enhanced documentation and pattern extraction features."""

from .base_imports import *
import re
from collections import Counter

class RstParser(BaseParser, CustomParserMixin):
    """Parser for reStructuredText files with enhanced pattern extraction capabilities."""
    
    def __init__(self, language_id: str = "rst", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.DOCUMENTATION, parser_type=ParserType.CUSTOM)
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
                async with AsyncErrorBoundary("RST parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
                    self._initialized = True
                    log("RST parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing RST parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> Dict[str, Any]:
        """Create a standardized RST AST node using the shared helper."""
        return super()._create_node(node_type, start_point, end_point, **kwargs)

    def _get_section_level(self, char: str) -> int:
        """Determine section level based on underline character."""
        levels = {
            '=': 1, '-': 2, '~': 3,
            '^': 4, '"': 5, '+': 6
        }
        return levels.get(char, 99)

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse RST content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="RST parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                lines = source_code.splitlines()
                ast = self._create_node(
                    "document",
                    [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0]
                )

                current_content = []
                section_stack = []
                in_code_block = False
                code_block_content = []
                code_block_lang = None
                current_list = None
                list_indent = 0
                
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    
                    # Handle code blocks
                    if line.startswith('.. code-block::'):
                        if not in_code_block:
                            in_code_block = True
                            code_block_lang = line.split('::')[1].strip()
                            code_block_start = i
                        continue
                    elif in_code_block and not line.strip():
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
                        if line.startswith('    '):
                            code_block_content.append(line[4:])
                        continue
                    
                    # Handle sections
                    if i > 0 and line and all(c == line[0] for c in line):
                        prev_line = lines[i - 1].strip()
                        if prev_line and len(line) >= len(prev_line):
                            level = self._get_section_level(line[0])
                            while section_stack and section_stack[-1]['level'] >= level:
                                section_stack.pop()
                            
                            section = self._create_node(
                                "section",
                                [i - 1, 0],
                                line_end,
                                title=prev_line,
                                level=level,
                                children=[]
                            )
                            
                            if section_stack:
                                section_stack[-1]['node'].children.append(section)
                            else:
                                ast.children.append(section)
                            
                            section_stack.append({'level': level, 'node': section})
                            continue
                    
                    # Handle directives
                    if line.startswith('.. '):
                        directive_match = re.match(r'^\.\. ([^:]+):: (.*)$', line)
                        if directive_match:
                            directive_type = directive_match.group(1)
                            directive_content = directive_match.group(2)
                            node = self._create_node(
                                "directive",
                                line_start,
                                line_end,
                                directive_type=directive_type,
                                content=directive_content
                            )
                            ast.children.append(node)
                            continue
                    
                    # Handle lists
                    list_match = re.match(r'^(\s*)([\*\-\+]|\d+\.)\s+(.+)$', line)
                    if list_match:
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
                    
                    # Handle paragraphs
                    if line.strip():
                        if not current_content:
                            current_content = [line]
                        else:
                            current_content.append(line)
                    elif current_content:
                        node = self._create_node(
                            "paragraph",
                            [i - len(current_content), 0],
                            [i - 1, len(current_content[-1])],
                            content='\n'.join(current_content)
                        )
                        ast.children.append(node)
                        current_content = []
                
                # Handle any remaining content
                if current_content:
                    node = self._create_node(
                        "paragraph",
                        [len(lines) - len(current_content), 0],
                        [len(lines) - 1, len(current_content[-1])],
                        content='\n'.join(current_content)
                    )
                    ast.children.append(node)
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing RST content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from RST files for repository learning.
        
        Args:
            source_code: The content of the RST file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="RST pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                task = asyncio.create_task(self._parse_source(source_code))
                self._pending_tasks.add(task)
                try:
                    ast = await task
                finally:
                    self._pending_tasks.remove(task)
                
                # Extract section patterns
                section_patterns = self._extract_section_patterns(ast)
                for section in section_patterns:
                    patterns.append({
                        'name': f'rst_section_{section["level"]}',
                        'content': section["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'section',
                            'level': section["level"],
                            'title': section["title"]
                        }
                    })
                
                # Extract directive patterns
                directive_patterns = self._extract_directive_patterns(ast)
                for directive in directive_patterns:
                    patterns.append({
                        'name': f'rst_directive_{directive["type"]}',
                        'content': directive["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'directive',
                            'directive_type': directive["type"]
                        }
                    })
                
                # Extract code block patterns
                code_block_patterns = self._extract_code_block_patterns(ast)
                for code_block in code_block_patterns:
                    patterns.append({
                        'name': f'rst_code_block_{code_block["language"] or "unknown"}',
                        'content': code_block["content"],
                        'pattern_type': PatternType.CODE_SNIPPET,
                        'language': code_block["language"] or self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'code_block',
                            'language': code_block["language"]
                        }
                    })
                
                # Extract list patterns
                list_patterns = self._extract_list_patterns(ast)
                for list_pattern in list_patterns:
                    patterns.append({
                        'name': f'rst_list_{list_pattern["type"]}',
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
                log(f"Error extracting patterns from RST file: {str(e)}", level="error")
                return []
    
    async def cleanup(self):
        """Clean up RST parser resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("RST parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up RST parser: {e}", level="error")

    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        # Count sections by level
        section_levels = Counter()
        section_titles = {}
        
        def process_node(node, level=0):
            if isinstance(node, dict):
                if node.get('type') == 'section':
                    section_level = node.get('level', 1)
                    section_title = node.get('title', '')
                    section_levels[section_level] += 1
                    
                    if section_level not in section_titles:
                        section_titles[section_level] = []
                    
                    if section_title:
                        section_titles[section_level].append(section_title)
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child, level + 1)
        
        process_node(ast)
        
        # Create patterns based on section hierarchy
        patterns = []
        
        if section_levels:
            # Pattern for section hierarchy
            patterns.append({
                'name': 'section_hierarchy',
                'content': f"Document has {sum(section_levels.values())} sections across {len(section_levels)} levels",
                'level': len(section_levels),
                'count': sum(section_levels.values())
            })
            
            # Patterns for each section level
            for level, count in section_levels.items():
                if count >= 2:  # Only include levels with multiple sections
                    patterns.append({
                        'name': f'level_{level}_sections',
                        'content': f"Document has {count} level {level} sections",
                        'level': level,
                        'count': count,
                        'examples': section_titles.get(level, [])[:3]  # Include up to 3 examples
                    })
        
        return patterns
        
    def _extract_directive_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract directive patterns from the AST."""
        # Count directives by type
        directive_types = Counter()
        directive_examples = {}
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'directive':
                    directive_type = node.get('name', 'unknown')
                    directive_content = node.get('content', '')
                    directive_types[directive_type] += 1
                    
                    if directive_type not in directive_examples:
                        directive_examples[directive_type] = []
                    
                    if directive_content:
                        directive_examples[directive_type].append(directive_content)
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)
        
        process_node(ast)
        
        # Create patterns for each directive type
        patterns = []
        
        for directive_type, count in directive_types.items():
            patterns.append({
                'type': directive_type,
                'content': f"Document uses {count} '{directive_type}' directives",
                'items': directive_examples.get(directive_type, [])[:3]  # Include up to 3 examples
            })
        
        return patterns
        
    def _extract_code_block_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract code block patterns from the AST."""
        # Count code blocks by language
        code_block_languages = Counter()
        code_block_contents = {}
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'code_block':
                    language = node.get('language', 'unknown')
                    content = node.get('content', '')
                    code_block_languages[language] += 1
                    
                    if language not in code_block_contents:
                        code_block_contents[language] = []
                    
                    if content:
                        code_block_contents[language].append(content)
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)
        
        process_node(ast)
        
        # Create patterns for each code block language
        patterns = []
        
        for language, count in code_block_languages.items():
            patterns.append({
                'language': language,
                'content': f"Document uses {count} code blocks in {language}",
                'count': count,
                'items': code_block_contents.get(language, [])[:3]  # Include up to 3 examples
            })
        
        return patterns
        
    def _extract_list_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract list patterns from the AST."""
        # Count lists by type and depth
        list_types = Counter()
        list_depths = Counter()
        list_contents = {}
        
        def process_node(node, depth=0):
            if isinstance(node, dict):
                if node.get('type') == 'list':
                    list_type = 'ordered' if node.get('ordered', False) else 'unordered'
                    list_types[list_type] += 1
                    list_depths[depth] += 1
                    
                    if list_type not in list_contents:
                        list_contents[list_type] = []
                    
                    for item in node.get('items', []):
                        if isinstance(item, dict) and item.get('type') == 'list_item':
                            content = item.get('content', '')
                            if content:
                                list_contents[list_type].append(content)
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child, depth + 1)
        
        process_node(ast)
        
        # Create patterns for each list type and depth
        patterns = []
        
        for list_type, count in list_types.items():
            patterns.append({
                'type': list_type,
                'content': f"Document uses {count} {list_type} lists",
                'count': count
            })
        
        for depth, count in list_depths.items():
            patterns.append({
                'type': f'depth_{depth}',
                'content': f"Document uses {count} lists at depth {depth}",
                'count': count
            })
        
        return patterns

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process RST with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("RST AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse RST"
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
                log(f"Error in RST AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_understanding(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with document understanding capability."""
        understanding = {}
        
        # Analyze document structure
        understanding["structure"] = {
            "sections": self._extract_section_patterns(ast),
            "directives": self._extract_directive_patterns(ast),
            "code_blocks": self._extract_code_block_patterns(ast),
            "lists": self._extract_list_patterns(ast)
        }
        
        # Analyze document patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze document style
        understanding["style"] = await self._analyze_document_style(ast)
        
        return understanding

    async def _process_with_generation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Process with document generation capability."""
        suggestions = []
        
        # Generate section suggestions
        if section_suggestions := await self._generate_section_suggestions(ast):
            suggestions.extend(section_suggestions)
        
        # Generate directive suggestions
        if directive_suggestions := await self._generate_directive_suggestions(ast):
            suggestions.extend(directive_suggestions)
        
        # Generate documentation suggestions
        if doc_suggestions := await self._generate_documentation_suggestions(ast):
            suggestions.extend(doc_suggestions)
        
        return suggestions

    async def _process_with_modification(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with document modification capability."""
        modifications = {}
        
        # Suggest structure improvements
        if improvements := await self._suggest_structure_improvements(ast):
            modifications["structure_improvements"] = improvements
        
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
        """Process with document review capability."""
        review = {}
        
        # Review document structure
        if structure_review := await self._review_structure(ast):
            review["structure"] = structure_review
        
        # Review document formatting
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
        """Analyze patterns in the RST document."""
        patterns = {}
        
        # Analyze section patterns
        patterns["section_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.STRUCTURE,
            context
        )
        
        # Analyze directive patterns
        patterns["directive_patterns"] = await self._pattern_processor.analyze_patterns(
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

    async def _analyze_document_style(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze document style."""
        style = {}
        
        # Analyze section style
        style["section_style"] = self._analyze_section_style(ast)
        
        # Analyze directive style
        style["directive_style"] = self._analyze_directive_style(ast)
        
        # Analyze list style
        style["list_style"] = self._analyze_list_style(ast)
        
        return style

    async def _generate_section_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate section suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing sections
        sections = self._extract_section_patterns(ast)
        
        # Suggest common missing sections
        common_sections = {
            "Introduction": "Document introduction",
            "Installation": "Installation instructions",
            "Usage": "Usage instructions",
            "API": "API documentation",
            "Contributing": "Contributing guidelines"
        }
        
        for name, description in common_sections.items():
            if not any(s["title"] == name for s in sections):
                suggestions.append(f"Add section '{name}' for {description}")
        
        return suggestions

    async def _generate_directive_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate directive suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing directives
        directives = self._extract_directive_patterns(ast)
        
        # Suggest common missing directives
        common_directives = {
            "warning": "Important warnings",
            "note": "Additional notes",
            "tip": "Helpful tips",
            "code-block": "Code examples",
            "image": "Visual documentation"
        }
        
        for name, description in common_directives.items():
            if not any(d["type"] == name for d in directives):
                suggestions.append(f"Add directive '{name}' for {description}")
        
        return suggestions

    async def _generate_documentation_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate documentation suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing documentation
        sections = self._extract_section_patterns(ast)
        directives = self._extract_directive_patterns(ast)
        
        # Suggest documentation improvements
        if not any(s["level"] == 1 for s in sections):
            suggestions.append("Add a top-level heading for the document")
        
        if not any(d["type"] == "code-block" for d in directives):
            suggestions.append("Add code examples using code-block directives")
        
        return suggestions

    async def _suggest_structure_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest structure improvements based on the AST."""
        improvements = {}
        
        # Analyze section structure
        sections = self._extract_section_patterns(ast)
        section_improvements = []
        
        # Check section hierarchy
        if sections:
            levels = [s["level"] for s in sections]
            if min(levels) > 1:
                section_improvements.append("Add a top-level section (level 1)")
            if max(levels) - min(levels) > 1:
                section_improvements.append("Fix section hierarchy - some levels are skipped")
        
        if section_improvements:
            improvements["sections"] = section_improvements
        
        return improvements

    async def _suggest_formatting_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest formatting improvements based on the AST."""
        improvements = {}
        
        # Analyze directive formatting
        directives = self._extract_directive_patterns(ast)
        directive_improvements = []
        
        for directive in directives:
            if not directive.get("content", "").strip():
                directive_improvements.append(f"Add content to empty {directive['type']} directive")
        
        if directive_improvements:
            improvements["directives"] = directive_improvements
        
        return improvements

    async def _suggest_documentation_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest documentation improvements based on the AST."""
        improvements = {}
        
        # Analyze documentation completeness
        sections = self._extract_section_patterns(ast)
        doc_improvements = []
        
        for section in sections:
            if not section.get("content", "").strip():
                doc_improvements.append(f"Add content to empty section '{section['title']}'")
        
        if doc_improvements:
            improvements["documentation"] = doc_improvements
        
        return improvements

    async def _review_structure(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review document structure."""
        review = {}
        
        # Review section structure
        sections = self._extract_section_patterns(ast)
        if sections:
            review["sections"] = {
                "count": len(sections),
                "levels": sorted(set(s["level"] for s in sections)),
                "titles": [s["title"] for s in sections]
            }
        
        # Review directive structure
        directives = self._extract_directive_patterns(ast)
        if directives:
            review["directives"] = {
                "count": len(directives),
                "types": sorted(set(d["type"] for d in directives))
            }
        
        return review

    async def _review_formatting(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review document formatting."""
        review = {}
        
        # Review section formatting
        sections = self._extract_section_patterns(ast)
        if sections:
            review["section_formatting"] = {
                "underline_chars": sorted(set(s.get("underline_char", "") for s in sections)),
                "title_case": all(s["title"].istitle() for s in sections)
            }
        
        # Review directive formatting
        directives = self._extract_directive_patterns(ast)
        if directives:
            review["directive_formatting"] = {
                "indentation": all(d.get("indent", 0) >= 3 for d in directives),
                "empty_lines": all(d.get("has_empty_lines", False) for d in directives)
            }
        
        return review

    async def _review_documentation(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review documentation quality."""
        review = {}
        
        # Review section documentation
        sections = self._extract_section_patterns(ast)
        if sections:
            review["section_docs"] = {
                "has_content": all(bool(s.get("content", "").strip()) for s in sections),
                "avg_length": sum(len(s.get("content", "").split()) for s in sections) / len(sections)
            }
        
        # Review directive documentation
        directives = self._extract_directive_patterns(ast)
        if directives:
            review["directive_docs"] = {
                "has_content": all(bool(d.get("content", "").strip()) for d in directives),
                "avg_length": sum(len(d.get("content", "").split()) for d in directives) / len(directives)
            }
        
        return review

    async def _learn_structure_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn structure patterns from the AST."""
        patterns = []
        
        # Learn section patterns
        sections = self._extract_section_patterns(ast)
        if sections:
            patterns.append({
                "type": "section_structure",
                "content": f"Document uses {len(sections)} sections across {len(set(s['level'] for s in sections))} levels",
                "examples": [s["title"] for s in sections[:3]]
            })
        
        # Learn directive patterns
        directives = self._extract_directive_patterns(ast)
        if directives:
            patterns.append({
                "type": "directive_structure",
                "content": f"Document uses {len(directives)} directives of {len(set(d['type'] for d in directives))} types",
                "examples": [d["type"] for d in directives[:3]]
            })
        
        return patterns

    async def _learn_formatting_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn formatting patterns from the AST."""
        patterns = []
        
        # Learn section formatting patterns
        sections = self._extract_section_patterns(ast)
        if sections:
            underline_chars = set(s.get("underline_char", "") for s in sections)
            patterns.append({
                "type": "section_formatting",
                "content": f"Document uses {len(underline_chars)} different section underline characters",
                "examples": sorted(underline_chars)
            })
        
        # Learn directive formatting patterns
        directives = self._extract_directive_patterns(ast)
        if directives:
            indent_levels = set(d.get("indent", 0) for d in directives)
            patterns.append({
                "type": "directive_formatting",
                "content": f"Document uses {len(indent_levels)} different directive indentation levels",
                "examples": sorted(indent_levels)
            })
        
        return patterns

    async def _learn_documentation_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn documentation patterns from the AST."""
        patterns = []
        
        # Learn section documentation patterns
        sections = self._extract_section_patterns(ast)
        if sections:
            patterns.append({
                "type": "section_documentation",
                "content": f"Document has {len(sections)} documented sections",
                "examples": [s["title"] for s in sections if s.get("content", "").strip()][:3]
            })
        
        # Learn directive documentation patterns
        directives = self._extract_directive_patterns(ast)
        if directives:
            patterns.append({
                "type": "directive_documentation",
                "content": f"Document has {len(directives)} documented directives",
                "examples": [d["type"] for d in directives if d.get("content", "").strip()][:3]
            })
        
        return patterns 