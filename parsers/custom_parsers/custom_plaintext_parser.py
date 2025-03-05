"""Custom parser for plaintext with enhanced documentation and pattern extraction features."""

from .base_imports import *
from collections import Counter
import re

class PlaintextParser(BaseParser, CustomParserMixin):
    """Parser for plaintext files with enhanced pattern extraction capabilities."""
    
    def __init__(self, language_id: str = "plaintext", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.DOCUMENTATION, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("Plaintext parser initialization"):
                    # No special initialization needed yet
                    await self._load_patterns()  # Load patterns through BaseParser mechanism
                    self._initialized = True
                    log("Plaintext parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing Plaintext parser: {e}", level="error")
                raise
        return True

    async def cleanup(self) -> None:
        """Clean up parser resources."""
        if self._pending_tasks:
            log(f"Cleaning up {len(self._pending_tasks)} pending Plaintext parser tasks", level="info")
            for task in self._pending_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()
        self._initialized = False

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> PlaintextNodeDict:
        """Create a standardized plaintext AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "content": kwargs.get("content")
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse plaintext content into AST structure."""
        if not self._initialized:
            await self.initialize()

        async with AsyncErrorBoundary(operation_name="plaintext parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                task = asyncio.create_task(self._parse_content(source_code))
                self._pending_tasks.add(task)
                try:
                    return await task
                finally:
                    self._pending_tasks.remove(task)
                
            except (ValueError, KeyError, TypeError, IndexError) as e:
                log(f"Error parsing plaintext content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__

    def _parse_content(self, source_code: str) -> Dict[str, Any]:
        """Internal method to parse plaintext content synchronously."""
        lines = source_code.splitlines()
        ast = self._create_node(
            "document",
            [0, 0],
            [len(lines) - 1, len(lines[-1]) if lines else 0]
        )

        current_paragraph = []
        
        for i, line in enumerate(lines):
            line_start = [i, 0]
            line_end = [i, len(line)]
            
            if not line.strip():
                if current_paragraph:
                    node = self._create_node(
                        "paragraph",
                        [i - len(current_paragraph), 0],
                        [i - 1, len(current_paragraph[-1])],
                        content="\n".join(current_paragraph)
                    )
                    ast.children.append(node)
                    current_paragraph = []
                continue

            matched = False
            for category in PLAINTEXT_PATTERNS.values():
                for pattern_name, pattern_obj in category.items():
                    if match := self.patterns[pattern_name].match(line):
                        node = self._create_node(
                            pattern_name,
                            line_start,
                            line_end,
                            **pattern_obj.extract(match)
                        )
                        ast.children.append(node)
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                current_paragraph.append(line)

        if current_paragraph:
            node = self._create_node(
                "paragraph",
                [len(lines) - len(current_paragraph), 0],
                [len(lines) - 1, len(current_paragraph[-1])],
                content="\n".join(current_paragraph)
            )
            ast.children.append(node)

        return ast.__dict__

    @handle_errors(error_types=(ProcessingError,))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract text patterns from plaintext files for repository learning."""
        if not self._initialized:
            await self.initialize()

        patterns = []
        
        async with AsyncErrorBoundary(operation_name="plaintext pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                # Parse the source first to get a structured representation
                ast = await self._parse_source(source_code)
                
                # Extract patterns asynchronously
                task = asyncio.create_task(self._extract_all_patterns(ast, source_code))
                self._pending_tasks.add(task)
                try:
                    patterns = await task
                finally:
                    self._pending_tasks.remove(task)
                    
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                log(f"Error extracting plaintext patterns: {e}", level="error")
                
        return patterns

    def _extract_all_patterns(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Extract all patterns from the AST synchronously."""
        patterns = []
        
        # Extract structural patterns (headers, paragraphs, etc.)
        structure_patterns = self._extract_structure_patterns(ast)
        for struct in structure_patterns:
            patterns.append({
                'name': f'plaintext_structure_{struct["type"]}',
                'content': struct["content"],
                'pattern_type': PatternType.DOCUMENTATION_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.85,
                'metadata': {
                    'type': 'document_structure',
                    'structure_type': struct["type"],
                    'count': struct.get("count", 1)
                }
            })
        
        # Extract list patterns
        list_patterns = self._extract_list_patterns(ast)
        for list_pattern in list_patterns:
            patterns.append({
                'name': f'plaintext_list_{list_pattern["type"]}',
                'content': list_pattern["content"],
                'pattern_type': PatternType.DOCUMENTATION_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.8,
                'metadata': {
                    'type': 'list_structure',
                    'list_type': list_pattern["type"],
                    'items': list_pattern.get("items", [])
                }
            })
            
        # Extract metadata patterns
        metadata_patterns = self._extract_metadata_patterns(ast)
        for meta in metadata_patterns:
            patterns.append({
                'name': f'plaintext_metadata',
                'content': meta["content"],
                'pattern_type': PatternType.DOCUMENTATION_METADATA,
                'language': self.language_id,
                'confidence': 0.9,
                'metadata': {
                    'type': 'document_metadata',
                    'metadata': meta.get("fields", {})
                }
            })
            
        # Extract reference patterns (URLs, emails, etc.)
        reference_patterns = self._extract_reference_patterns(ast)
        for ref in reference_patterns:
            patterns.append({
                'name': f'plaintext_reference_{ref["type"]}',
                'content': ref["content"],
                'pattern_type': PatternType.DOCUMENTATION_REFERENCE,
                'language': self.language_id,
                'confidence': 0.85,
                'metadata': {
                    'type': 'reference',
                    'reference_type': ref["type"],
                    'references': ref.get("references", [])
                }
            })
            
        # Extract writing style patterns
        style_patterns = self._extract_style_patterns(source_code)
        for style in style_patterns:
            patterns.append({
                'name': f'plaintext_style_{style["name"]}',
                'content': style["content"],
                'pattern_type': PatternType.DOCUMENTATION_STYLE,
                'language': self.language_id,
                'confidence': 0.75,
                'metadata': {
                    'type': 'writing_style',
                    'style_name': style["name"],
                    'metrics': style.get("metrics", {})
                }
            })
            
        return patterns
        
    def _extract_structure_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract structure patterns from the AST."""
        structures = []
        
        # Count different node types
        type_counts = Counter()
        
        for child in ast.get('children', []):
            if isinstance(child, dict):
                node_type = child.get('type')
                if node_type:
                    type_counts[node_type] += 1
        
        # Create patterns for significant node types
        for node_type, count in type_counts.items():
            if count >= 2:  # Only include if it appears multiple times
                if node_type == 'header':
                    # Analyze header structure
                    header_structure = self._analyze_headers(ast)
                    if header_structure:
                        structures.append({
                            'type': 'header_hierarchy',
                            'content': f"Document uses {len(header_structure)} header levels",
                            'levels': header_structure,
                            'count': sum(len(headers) for headers in header_structure.values())
                        })
                elif node_type == 'paragraph':
                    # Analyze paragraph structure
                    structures.append({
                        'type': 'paragraph_structure',
                        'content': f"Document contains {count} paragraphs",
                        'count': count
                    })
                elif node_type == 'code_block':
                    structures.append({
                        'type': 'code_block_usage',
                        'content': f"Document contains {count} code blocks",
                        'count': count
                    })
        
        return structures
        
    def _analyze_headers(self, ast: Dict[str, Any]) -> Dict[int, List[str]]:
        """Analyze header structure in the document."""
        headers_by_level = {}
        
        for child in ast.get('children', []):
            if isinstance(child, dict) and child.get('type') == 'header':
                level = child.get('level', 1)
                content = child.get('content', '')
                
                if level not in headers_by_level:
                    headers_by_level[level] = []
                    
                headers_by_level[level].append(content)
        
        return headers_by_level
        
    def _extract_list_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract list patterns from the AST."""
        list_patterns = []
        
        # Collect list items
        bullet_list_items = []
        numbered_list_items = []
        
        for child in ast.get('children', []):
            if isinstance(child, dict):
                if child.get('type') == 'list_item':
                    bullet_list_items.append(child.get('content', ''))
                elif child.get('type') == 'numbered_item':
                    numbered_list_items.append(child.get('content', ''))
        
        # Create patterns for each list type
        if bullet_list_items:
            list_patterns.append({
                'type': 'bullet_list',
                'content': f"Document contains {len(bullet_list_items)} bullet list items",
                'items': bullet_list_items
            })
            
        if numbered_list_items:
            list_patterns.append({
                'type': 'numbered_list',
                'content': f"Document contains {len(numbered_list_items)} numbered list items",
                'items': numbered_list_items
            })
            
        return list_patterns
        
    def _extract_metadata_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract metadata patterns from the AST."""
        metadata_fields = {}
        
        for child in ast.get('children', []):
            if isinstance(child, dict) and child.get('type') == 'metadata':
                key = child.get('key', '')
                value = child.get('value', '')
                
                if key:
                    metadata_fields[key] = value
        
        if metadata_fields:
            return [{
                'content': f"Document contains metadata: {', '.join(metadata_fields.keys())}",
                'fields': metadata_fields
            }]
            
        return []
        
    def _extract_reference_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract reference patterns from the AST."""
        references = {}
        
        # Collect references from all nodes
        def collect_references(node):
            if isinstance(node, dict):
                node_type = node.get('type')
                
                if node_type == 'url':
                    url = node.get('url', '')
                    if url:
                        references.setdefault('url', []).append(url)
                elif node_type == 'email':
                    email = node.get('address', '')
                    if email:
                        references.setdefault('email', []).append(email)
                
                # Process children recursively
                for child in node.get('children', []):
                    collect_references(child)
        
        collect_references(ast)
        
        # Create patterns for each reference type
        patterns = []
        for ref_type, refs in references.items():
            if refs:
                patterns.append({
                    'type': ref_type,
                    'content': f"Document contains {len(refs)} {ref_type} references",
                    'references': refs
                })
                
        return patterns
        
    def _extract_style_patterns(self, text: str) -> List[Dict[str, Any]]:
        """Extract writing style patterns from the text."""
        patterns = []
        
        if not text:
            return patterns
            
        # Calculate basic metrics
        words = re.findall(r'\b\w+\b', text)
        sentences = re.split(r'[.!?]+', text)
        paragraphs = re.split(r'\n\s*\n', text)
        
        word_count = len(words)
        sentence_count = len(sentences)
        paragraph_count = len(paragraphs)
        
        # Only proceed if we have enough text
        if word_count < 10:
            return patterns
            
        # Calculate average sentence length
        avg_sentence_length = word_count / max(1, sentence_count)
        
        # Calculate average paragraph length
        avg_paragraph_length = word_count / max(1, paragraph_count)
        
        # Calculate estimated reading time (words per minute)
        reading_time_minutes = word_count / 200  # Assuming 200 words per minute
        
        # Create a general writing style pattern
        patterns.append({
            'name': 'writing_metrics',
            'content': f"Document has {word_count} words in {sentence_count} sentences and {paragraph_count} paragraphs",
            'metrics': {
                'word_count': word_count,
                'sentence_count': sentence_count,
                'paragraph_count': paragraph_count,
                'avg_sentence_length': avg_sentence_length,
                'avg_paragraph_length': avg_paragraph_length,
                'reading_time_minutes': reading_time_minutes
            }
        })
        
        # Analyze sentence complexity if we have enough sentences
        if sentence_count >= 3:
            long_sentences = sum(1 for s in sentences if len(re.findall(r'\b\w+\b', s)) > 20)
            short_sentences = sum(1 for s in sentences if len(re.findall(r'\b\w+\b', s)) <= 10)
            
            if long_sentences / max(1, sentence_count) > 0.3:
                patterns.append({
                    'name': 'complex_sentences',
                    'content': f"Document uses complex sentences ({long_sentences} long sentences out of {sentence_count})",
                    'metrics': {
                        'long_sentence_ratio': long_sentences / max(1, sentence_count),
                        'long_sentences': long_sentences
                    }
                })
            elif short_sentences / max(1, sentence_count) > 0.5:
                patterns.append({
                    'name': 'simple_sentences',
                    'content': f"Document uses simple sentences ({short_sentences} short sentences out of {sentence_count})",
                    'metrics': {
                        'short_sentence_ratio': short_sentences / max(1, sentence_count),
                        'short_sentences': short_sentences
                    }
                })
        
        return patterns