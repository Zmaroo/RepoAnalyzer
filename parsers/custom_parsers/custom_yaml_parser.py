"""
Custom YAML parser.

This parser processes YAML files using the pyyaml library, extracting
structured data and patterns.
"""

import yaml
from .base_imports import *
import re
from collections import Counter
from parsers.query_patterns.yaml import YAML_PATTERNS

class YamlParser(BaseParser, CustomParserMixin):
    """Parser for YAML files."""
    
    def __init__(self, language_id: str = "yaml", file_type: Optional[FileType] = None):
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
                async with AsyncErrorBoundary("YAML parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
                    self._initialized = True
                    log("YAML parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing YAML parser: {e}", level="error")
                raise
        return True
    
    def _create_node(
        self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs
    ) -> YamlNodeDict:
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "value": kwargs.get("value"),
            "path": kwargs.get("path")
        }
    
    def _process_value(self, value: Any, path: List[str], start_point: List[int]) -> YamlNodeDict:
        node = self._create_node(
            type(value).__name__, start_point,
            [start_point[0], start_point[1] + len(str(value))],
            path='.'.join(path)
        )
        if isinstance(value, dict):
            node["type"] = "mapping"
            for key, val in value.items():
                child = self._process_value(
                    val, path + [str(key)],
                    [start_point[0], start_point[1] + 1]
                )
                child["key"] = key
                for pattern_name in ['url', 'path', 'version']:
                    if pattern_match := self.patterns[pattern_name].match(str(val)):
                        child["metadata"]["semantics"] = self.patterns[pattern_name].extract(pattern_match)
                node["children"].append(child)
        elif isinstance(value, list):
            node["type"] = "sequence"
            for i, item in enumerate(value):
                child = self._process_value(
                    item, path + [f"[{i}]"],
                    [start_point[0], start_point[1] + 1]
                )
                node["children"].append(child)
        else:
            node["type"] = "scalar"
            node["value"] = value
        return node
    
    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse YAML content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="YAML parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                lines = source_code.splitlines()
                ast = self._create_node(
                    "document", [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0]
                )
                current_comment_block = []
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    if comment_match := self.patterns['comment'].match(line):
                        current_comment_block.append(comment_match.group(1).strip())
                        continue
                    if line.strip() and current_comment_block:
                        node = self._create_node(
                            "comment_block", [i - len(current_comment_block), 0],
                            [i - 1, len(current_comment_block[-1])],
                            content="\n".join(current_comment_block)
                        )
                        ast["children"].append(node)
                        current_comment_block = []
                try:
                    task = asyncio.create_task(self._parse_yaml(source_code))
                    self._pending_tasks.add(task)
                    try:
                        data = await task
                    finally:
                        self._pending_tasks.remove(task)
                        
                    if data is not None:
                        root_node = self._process_value(data, [], [0, 0])
                        ast["children"].append(root_node)
                        for pattern_name in ['description', 'metadata']:
                            if YAML_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].pattern(root_node):
                                ast["metadata"]["documentation"] = YAML_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].extract(root_node)
                except yaml.YAMLError as e:
                    log(f"Error parsing YAML structure: {e}", level="error")
                    ast["metadata"]["parse_error"] = str(e)
                if current_comment_block:
                    ast["metadata"]["trailing_comments"] = current_comment_block
                return ast
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing YAML content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__
            
    async def _parse_yaml(self, source_code: str) -> Any:
        """Parse YAML content asynchronously."""
        return yaml.safe_load(source_code)
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from YAML files for repository learning.
        
        Args:
            source_code: The content of the YAML file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="YAML pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                task = asyncio.create_task(self._parse_source(source_code))
                self._pending_tasks.add(task)
                try:
                    ast = await task
                finally:
                    self._pending_tasks.remove(task)
                
                # Extract mapping patterns
                mapping_patterns = self._extract_mapping_patterns(ast)
                for mapping in mapping_patterns:
                    patterns.append({
                        'name': f'yaml_mapping_{mapping["type"]}',
                        'content': mapping["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'mapping',
                            'key_pattern': mapping["key_pattern"],
                            'value_type': mapping["value_type"]
                        }
                    })
                
                # Extract sequence patterns
                sequence_patterns = self._extract_sequence_patterns(ast)
                for sequence in sequence_patterns:
                    patterns.append({
                        'name': f'yaml_sequence_{sequence["type"]}',
                        'content': sequence["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.75,
                        'metadata': {
                            'type': 'sequence',
                            'item_type': sequence["item_type"],
                            'length': sequence["length"]
                        }
                    })
                
                # Extract reference patterns (anchors and aliases)
                reference_patterns = self._extract_reference_patterns(ast)
                for reference in reference_patterns:
                    patterns.append({
                        'name': f'yaml_reference_{reference["type"]}',
                        'content': reference["content"],
                        'pattern_type': PatternType.CODE_REFERENCE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': reference["type"],
                            'name': reference["name"]
                        }
                    })
                
                # Extract comment patterns
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({
                        'name': f'yaml_comment_{comment["type"]}',
                        'content': comment["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.7,
                        'metadata': {
                            'type': 'comment',
                            'style': comment["type"]
                        }
                    })
                
                # Extract naming patterns
                naming_patterns = self._extract_naming_patterns(source_code)
                for naming in naming_patterns:
                    patterns.append({
                        'name': f'yaml_naming_{naming["type"]}',
                        'content': naming["content"],
                        'pattern_type': PatternType.CODE_NAMING,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'naming',
                            'convention': naming["type"]
                        }
                    })
                
                return patterns
                
            except Exception as e:
                log(f"Error extracting YAML patterns: {e}", level="error")
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
            log("YAML parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up YAML parser: {e}", level="error")
        
    def _extract_mapping_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract mapping patterns from the AST."""
        mappings = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'mapping':
                    mappings.append({
                        'path': node.get('path', 'unknown'),
                        'content': str(node),
                        'key_count': len(node.get('children', []))
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return mappings
        
    def _extract_sequence_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract sequence patterns from the AST."""
        sequences = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'sequence':
                    sequences.append({
                        'path': node.get('path', 'unknown'),
                        'content': str(node),
                        'item_count': len(node.get('children', []))
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return sequences
        
    def _extract_reference_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract anchor and alias patterns from the AST."""
        references = []
        
        # Process through the raw content to find anchors and aliases
        # Since this is a custom parser and might not capture these as nodes
        anchor_pattern = re.compile(r'&([a-zA-Z0-9_-]+)\s')
        alias_pattern = re.compile(r'\*([a-zA-Z0-9_-]+)')
        
        def find_references_in_content(content):
            for match in anchor_pattern.finditer(content):
                references.append({
                    'type': 'anchor',
                    'name': match.group(1),
                    'content': match.group(0)
                })
                
            for match in alias_pattern.finditer(content):
                references.append({
                    'type': 'alias',
                    'name': match.group(1),
                    'content': match.group(0)
                })
                
        # Also check if there are reference nodes in the AST
        def process_node(node):
            if isinstance(node, dict):
                node_str = str(node)
                find_references_in_content(node_str)
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return references
        
    def _extract_comment_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract comment patterns from the AST."""
        comments = []
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'comment_block':
                    content = node.get('content', '')
                    comments.append({
                        'type': 'block_comment',
                        'content': content,
                        'line_count': content.count('\n') + 1
                    })
                    
                # Check for comments in metadata
                if node.get('metadata', {}).get('trailing_comments'):
                    content = '\n'.join(node.get('metadata', {}).get('trailing_comments', []))
                    comments.append({
                        'type': 'trailing_comment',
                        'content': content,
                        'line_count': len(node.get('metadata', {}).get('trailing_comments', []))
                    })
                
                for child in node.get('children', []):
                    process_node(child)
                    
        process_node(ast)
        return comments
        
    def _extract_naming_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract naming convention patterns from the source code."""
        patterns = []
        
        # Extract key naming conventions
        snake_case_keys = 0
        camel_case_keys = 0
        kebab_case_keys = 0
        
        # Regex patterns for different naming styles
        snake_case_pattern = re.compile(r'^\s*([a-z][a-z0-9_]*[a-z0-9]):\s', re.MULTILINE)
        camel_case_pattern = re.compile(r'^\s*([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*):\s', re.MULTILINE)
        kebab_case_pattern = re.compile(r'^\s*([a-z][a-z0-9-]*[a-z0-9]):\s', re.MULTILINE)
        
        for match in snake_case_pattern.finditer(source_code):
            if '_' in match.group(1):
                snake_case_keys += 1
                
        for match in camel_case_pattern.finditer(source_code):
            if not '_' in match.group(1) and not '-' in match.group(1):
                camel_case_keys += 1
                
        for match in kebab_case_pattern.finditer(source_code):
            if '-' in match.group(1):
                kebab_case_keys += 1
        
        # Determine the dominant naming convention
        total_keys = snake_case_keys + camel_case_keys + kebab_case_keys
        if total_keys > 3:  # Only if we have enough data
            if snake_case_keys >= camel_case_keys and snake_case_keys >= kebab_case_keys:
                convention = 'snake_case'
                dom_count = snake_case_keys
            elif camel_case_keys >= snake_case_keys and camel_case_keys >= kebab_case_keys:
                convention = 'camelCase'
                dom_count = camel_case_keys
            else:
                convention = 'kebab-case'
                dom_count = kebab_case_keys
                
            confidence = 0.5 + 0.3 * (dom_count / total_keys)
                
            patterns.append({
                'name': 'yaml_key_naming_convention',
                'content': f"Key naming convention: {convention}",
                'pattern_type': PatternType.NAMING_CONVENTION,
                'language': self.language_id,
                'confidence': confidence,
                'metadata': {
                    'type': 'naming_convention',
                    'element_type': 'key',
                    'convention': convention,
                    'snake_case_count': snake_case_keys,
                    'camel_case_count': camel_case_keys,
                    'kebab_case_count': kebab_case_keys
                }
            })
            
        return patterns

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process YAML with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("YAML AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse YAML"
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
                log(f"Error in YAML AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_understanding(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with YAML understanding capability."""
        understanding = {}
        
        # Analyze YAML structure
        understanding["structure"] = {
            "mappings": self._extract_mapping_patterns(ast),
            "sequences": self._extract_sequence_patterns(ast),
            "scalars": self._extract_scalar_patterns(ast)
        }
        
        # Analyze YAML patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze YAML style
        understanding["style"] = await self._analyze_yaml_style(ast)
        
        return understanding

    async def _process_with_generation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Process with YAML generation capability."""
        suggestions = []
        
        # Generate mapping suggestions
        if mapping_suggestions := await self._generate_mapping_suggestions(ast):
            suggestions.extend(mapping_suggestions)
        
        # Generate sequence suggestions
        if sequence_suggestions := await self._generate_sequence_suggestions(ast):
            suggestions.extend(sequence_suggestions)
        
        # Generate documentation suggestions
        if doc_suggestions := await self._generate_documentation_suggestions(ast):
            suggestions.extend(doc_suggestions)
        
        return suggestions

    async def _process_with_modification(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with YAML modification capability."""
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
        """Process with YAML review capability."""
        review = {}
        
        # Review YAML structure
        if structure_review := await self._review_structure(ast):
            review["structure"] = structure_review
        
        # Review YAML formatting
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
        """Analyze patterns in the YAML document."""
        patterns = {}
        
        # Analyze mapping patterns
        patterns["mapping_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.STRUCTURE,
            context
        )
        
        # Analyze sequence patterns
        patterns["sequence_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.SYNTAX,
            context
        )
        
        # Analyze scalar patterns
        patterns["scalar_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.SEMANTICS,
            context
        )
        
        return patterns

    async def _analyze_yaml_style(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze YAML style."""
        style = {}
        
        # Analyze mapping style
        style["mapping_style"] = self._analyze_mapping_style(ast)
        
        # Analyze sequence style
        style["sequence_style"] = self._analyze_sequence_style(ast)
        
        # Analyze scalar style
        style["scalar_style"] = self._analyze_scalar_style(ast)
        
        return style

    async def _generate_mapping_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate mapping suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing mappings
        mappings = self._extract_mapping_patterns(ast)
        
        # Suggest common missing mappings
        common_mappings = {
            "metadata": "Document metadata",
            "configuration": "Configuration settings",
            "dependencies": "Project dependencies",
            "environment": "Environment settings",
            "resources": "Resource definitions"
        }
        
        for name, description in common_mappings.items():
            if not any(m["name"] == name for m in mappings):
                suggestions.append(f"Add mapping '{name}' for {description}")
        
        return suggestions

    async def _generate_sequence_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate sequence suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing sequences
        sequences = self._extract_sequence_patterns(ast)
        
        # Suggest common missing sequences
        common_sequences = {
            "items": "List of items",
            "steps": "Process steps",
            "stages": "Pipeline stages",
            "tags": "Resource tags",
            "labels": "Resource labels"
        }
        
        for name, description in common_sequences.items():
            if not any(s["name"] == name for s in sequences):
                suggestions.append(f"Add sequence '{name}' for {description}")
        
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
            suggestions.append("Add header comments describing the YAML document")
        
        if not any(c["type"] == "section" for c in comments):
            suggestions.append("Add section comments explaining configuration choices")
        
        return suggestions

    async def _suggest_structure_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest structure improvements based on the AST."""
        improvements = {}
        
        # Analyze mapping structure
        mappings = self._extract_mapping_patterns(ast)
        mapping_improvements = []
        
        for mapping in mappings:
            if not mapping.get("value"):
                mapping_improvements.append(f"Add value to empty mapping '{mapping['name']}'")
        
        if mapping_improvements:
            improvements["mappings"] = mapping_improvements
        
        return improvements

    async def _suggest_formatting_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest formatting improvements based on the AST."""
        improvements = {}
        
        # Analyze sequence formatting
        sequences = self._extract_sequence_patterns(ast)
        sequence_improvements = []
        
        for sequence in sequences:
            if sequence.get("item_count", 0) > 5 and not sequence.get("multiline", False):
                sequence_improvements.append(f"Consider using multiline format for large sequence '{sequence['name']}'")
        
        if sequence_improvements:
            improvements["sequences"] = sequence_improvements
        
        return improvements

    async def _suggest_documentation_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest documentation improvements based on the AST."""
        improvements = {}
        
        # Analyze documentation completeness
        mappings = self._extract_mapping_patterns(ast)
        doc_improvements = []
        
        for mapping in mappings:
            if not mapping.get("documentation"):
                doc_improvements.append(f"Add documentation for mapping '{mapping['name']}'")
        
        if doc_improvements:
            improvements["documentation"] = doc_improvements
        
        return improvements

    async def _review_structure(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review YAML structure."""
        review = {}
        
        # Review mapping structure
        mappings = self._extract_mapping_patterns(ast)
        if mappings:
            review["mappings"] = {
                "count": len(mappings),
                "names": [m["name"] for m in mappings],
                "empty_mappings": sum(1 for m in mappings if not m.get("value"))
            }
        
        # Review sequence structure
        sequences = self._extract_sequence_patterns(ast)
        if sequences:
            review["sequences"] = {
                "count": len(sequences),
                "names": [s["name"] for s in sequences],
                "item_counts": {s["name"]: s.get("item_count", 0) for s in sequences}
            }
        
        return review

    async def _review_formatting(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review YAML formatting."""
        review = {}
        
        # Review mapping formatting
        mappings = self._extract_mapping_patterns(ast)
        if mappings:
            review["mapping_formatting"] = {
                "indentation": all(m.get("indent", 0) >= 2 for m in mappings),
                "empty_lines": all(m.get("has_empty_lines", False) for m in mappings)
            }
        
        # Review sequence formatting
        sequences = self._extract_sequence_patterns(ast)
        if sequences:
            review["sequence_formatting"] = {
                "multiline": sum(1 for s in sequences if s.get("multiline", False)),
                "inline": sum(1 for s in sequences if not s.get("multiline", False))
            }
        
        return review

    async def _review_documentation(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review documentation quality."""
        review = {}
        
        # Review mapping documentation
        mappings = self._extract_mapping_patterns(ast)
        if mappings:
            review["mapping_docs"] = {
                "has_docs": sum(1 for m in mappings if m.get("documentation")),
                "missing_docs": sum(1 for m in mappings if not m.get("documentation"))
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
        
        # Learn mapping patterns
        mappings = self._extract_mapping_patterns(ast)
        if mappings:
            patterns.append({
                "type": "mapping_structure",
                "content": f"Document uses {len(mappings)} mappings",
                "examples": [m["name"] for m in mappings[:3]]
            })
        
        # Learn sequence patterns
        sequences = self._extract_sequence_patterns(ast)
        if sequences:
            patterns.append({
                "type": "sequence_structure",
                "content": f"Document uses {len(sequences)} sequences",
                "examples": [s["name"] for s in sequences[:3]]
            })
        
        return patterns

    async def _learn_formatting_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn formatting patterns from the AST."""
        patterns = []
        
        # Learn mapping formatting patterns
        mappings = self._extract_mapping_patterns(ast)
        if mappings:
            indent_levels = set(m.get("indent", 0) for m in mappings)
            patterns.append({
                "type": "mapping_formatting",
                "content": f"Document uses {len(indent_levels)} different mapping indentation levels",
                "examples": sorted(indent_levels)
            })
        
        # Learn sequence formatting patterns
        sequences = self._extract_sequence_patterns(ast)
        if sequences:
            multiline = sum(1 for s in sequences if s.get("multiline", False))
            inline = len(sequences) - multiline
            patterns.append({
                "type": "sequence_formatting",
                "content": f"Document uses {multiline} multiline and {inline} inline sequences",
                "examples": {"multiline": multiline, "inline": inline}
            })
        
        return patterns

    async def _learn_documentation_patterns(
        self,
        ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Learn documentation patterns from the AST."""
        patterns = []
        
        # Learn mapping documentation patterns
        mappings = self._extract_mapping_patterns(ast)
        if mappings:
            documented = [m for m in mappings if m.get("documentation")]
            patterns.append({
                "type": "mapping_documentation",
                "content": f"Document has {len(documented)} documented mappings",
                "examples": [m["name"] for m in documented[:3]]
            })
        
        # Learn comment patterns
        comments = self._extract_comment_patterns(ast)
        if comments:
            comment_types = Counter(c["type"] for c in comments)
            patterns.append({
                "type": "comment_patterns",
                "content": f"Document uses {len(comment_types)} different comment types",
                "examples": dict(comment_types.most_common(3))
            })
        
        return patterns