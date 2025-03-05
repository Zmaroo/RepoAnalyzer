"""
Custom EditorConfig parser.

This module implements a lightweight parser for EditorConfig files.
It extracts section headers (e.g. [*] or [*.py]) and
key-value property lines beneath each section.
"""

from .base_imports import *
from typing import Dict, List, Any, Optional, Set, Tuple
import asyncio
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.editorconfig import EDITORCONFIG_PATTERNS
from utils.logger import log
from utils.error_handling import handle_errors, ProcessingError, ParsingError, ErrorSeverity, handle_async_errors, AsyncErrorBoundary
from utils.shutdown import register_shutdown_handler
import re
from collections import Counter
import configparser
from parsers.custom_parsers.custom_parser_mixin import CustomParserMixin

class EditorconfigParser(BaseParser, CustomParserMixin):
    """Parser for EditorConfig files."""
    
    def __init__(self, language_id: str = "editorconfig", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self._initialized = False
        self._pending_tasks: set[asyncio.Future] = set()
        self.patterns = self._compile_patterns(EDITORCONFIG_PATTERNS)
        register_shutdown_handler(self.cleanup)
        
        # Compile regex patterns for parsing
        self.section_pattern = re.compile(r'^\s*\[(.*)\]\s*$')
        self.property_pattern = re.compile(r'^\s*([^=]+?)\s*=\s*(.*?)\s*$')
        self.comment_pattern = re.compile(r'^\s*[#;](.*)$')
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("EditorConfig parser initialization"):
                    await self._initialize_cache(self.language_id)
                    self._initialized = True
                    log("EditorConfig parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing EditorConfig parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> EditorconfigNodeDict:
        """Create a standardized EditorConfig AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "properties": kwargs.get("properties", []),
            "sections": kwargs.get("sections", [])
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse EditorConfig content into AST structure."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="EditorConfig parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
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
                
                # Parse EditorConfig structure
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
                    log(f"Error parsing EditorConfig structure: {e}", level="error")
                    ast.metadata["parse_error"] = str(e)
                
                # Handle any remaining comments
                if current_comment_block:
                    ast.metadata["trailing_comments"] = current_comment_block
                
                # Store result in cache
                await self._store_parse_result(source_code, ast.__dict__)
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing EditorConfig content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from EditorConfig files for repository learning.
        
        Args:
            source_code: The content of the EditorConfig file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(operation_name="EditorConfig pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
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
                        'name': f'editorconfig_section_{section["type"]}',
                        'content': section["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'section',
                            'pattern': section["pattern"],
                            'properties': section.get("properties", [])
                        }
                    })
                
                # Extract property patterns
                property_patterns = self._extract_property_patterns(ast)
                for prop in property_patterns:
                    patterns.append({
                        'name': f'editorconfig_property_{prop["type"]}',
                        'content': prop["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'property',
                            'property_type': prop["type"],
                            'examples': prop.get("examples", [])
                        }
                    })
                
                # Extract comment patterns
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({
                        'name': f'editorconfig_comment_{comment["type"]}',
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
                log(f"Error extracting patterns from EditorConfig file: {str(e)}", level="error")
                return []
    
    async def cleanup(self):
        """Clean up EditorConfig parser resources."""
        try:
            await self._cleanup_cache()
            log("EditorConfig parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up EditorConfig parser: {e}", level="error")

    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        sections = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'section':
                pattern = node.get('pattern', '')
                if pattern:
                    # Determine section type based on pattern
                    if pattern == '*':
                        section_type = 'global'
                    elif pattern.startswith('*.'):
                        section_type = 'extension'
                    elif '/' in pattern:
                        section_type = 'path'
                    else:
                        section_type = 'custom'
                        
                    sections.append({
                        'type': section_type,
                        'pattern': pattern,
                        'content': f"[{pattern}]",
                        'properties': node.get('properties', [])
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return sections
        
    def _extract_property_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract property patterns from the AST."""
        properties = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'property':
                key = node.get('key', '').lower()
                value = node.get('value', '')
                
                # Categorize properties
                if key in ['indent_style', 'indent_size', 'tab_width']:
                    property_type = 'indentation'
                elif key in ['end_of_line', 'insert_final_newline', 'trim_trailing_whitespace']:
                    property_type = 'line_ending'
                elif key in ['charset']:
                    property_type = 'encoding'
                elif key.startswith('max_line_length'):
                    property_type = 'formatting'
                else:
                    property_type = 'other'
                    
                properties.append({
                    'type': property_type,
                    'content': f"{key} = {value}",
                    'examples': [{'key': key, 'value': value}]
                })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return properties
        
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