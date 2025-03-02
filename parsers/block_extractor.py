"""Tree-sitter based code block extraction.

This module provides utilities for extracting code blocks (like function bodies,
class definitions, etc.) from source code using tree-sitter's AST capabilities
rather than heuristic-based approaches.
"""
from typing import Dict, List, Optional, Any, Tuple
import re
from dataclasses import dataclass
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, AsyncErrorBoundary
from tree_sitter_language_pack import get_parser, get_language
from parsers.types import FileType, ParserType
from parsers.models import PatternMatch


@dataclass
class ExtractedBlock:
    """Represents an extracted code block with metadata."""
    content: str
    start_point: Tuple[int, int]
    end_point: Tuple[int, int]
    node_type: str
    metadata: Dict[str, Any] = None
    confidence: float = 1.0


class TreeSitterBlockExtractor:
    """
    Extracts code blocks using tree-sitter's AST capabilities.
    This provides more accurate and language-aware block extraction
    compared to heuristic text-based approaches.
    """

    def __init__(self):
        """Initialize the block extractor."""
        self._language_parsers = {}

    @handle_errors(error_types=(Exception,))
    def extract_block(self, language_id: str, source_code: str,
        node_or_match: Any) ->Optional[ExtractedBlock]:
        """
        Extract a code block from the given node or pattern match.
        
        Args:
            language_id: The language identifier
            source_code: The complete source code
            node_or_match: Either a tree-sitter Node or a PatternMatch
            
        Returns:
            An ExtractedBlock object or None if extraction fails
        """
        with ErrorBoundary(f'extracting block for {language_id}'):
            if isinstance(node_or_match, PatternMatch):
                node = node_or_match.node
                if node is None:
                    return self._extract_block_heuristic(source_code,
                        node_or_match)
                return self._extract_from_node(language_id, source_code, node)
            try:
                return self._extract_from_node(language_id, source_code,
                    node_or_match)
            except Exception as e:
                log(f'Error extracting from node: {e}', level='warning')
                return self._extract_block_heuristic(source_code, node_or_match
                    )

    @handle_errors(error_types=(Exception,))
    def _extract_block_heuristic(self, source_code: str, node_or_match: Any
        ) ->Optional[ExtractedBlock]:
        """
        Fallback method that uses heuristics to extract a block when tree-sitter isn't available.
        
        Args:
            source_code: The source code
            node_or_match: A PatternMatch or node-like object with position information
            
        Returns:
            An ExtractedBlock with the extracted content
        """
        try:
            if isinstance(node_or_match, PatternMatch):
                start_line = node_or_match.line
                start_col = node_or_match.column
                raw_snippet = node_or_match.snippet
                lines = source_code.split('\n')
                context_lines = []
                if 0 <= start_line < len(lines):
                    context_lines.append(lines[start_line])
                    line_index = start_line + 1
                    while line_index < len(lines
                        ) and line_index < start_line + 10:
                        context_lines.append(lines[line_index])
                        line_index += 1
                        if line_index < len(lines) and lines[line_index].strip(
                            ) and len(lines[line_index]) - len(lines[
                            line_index].lstrip()) < len(lines[start_line]
                            ) - len(lines[start_line].lstrip()):
                            break
                extracted_content = '\n'.join(context_lines)
                return ExtractedBlock(content=extracted_content,
                    start_point=(start_line, start_col), end_point=(
                    start_line + len(context_lines) - 1, len(context_lines[
                    -1])), node_type='heuristic_block', metadata={'source':
                    'heuristic'}, confidence=0.6)
            else:
                try:
                    start_point = node_or_match.start_point[0
                        ], node_or_match.start_point[1]
                    end_point = node_or_match.end_point[0
                        ], node_or_match.end_point[1]
                    lines = source_code.split('\n')
                    content_lines = lines[start_point[0]:end_point[0] + 1]
                    if len(content_lines) > 0:
                        content_lines[0] = content_lines[0][start_point[1]:]
                        if len(content_lines) > 1:
                            content_lines[-1] = content_lines[-1][:end_point[1]
                                ]
                    content = '\n'.join(content_lines)
                    return ExtractedBlock(content=content, start_point=
                        start_point, end_point=end_point, node_type=
                        'heuristic_block', metadata={'source': 'heuristic'},
                        confidence=0.7)
                except AttributeError:
                    return None
        except Exception as e:
            log(f'Heuristic extraction failed: {e}', level='warning')
            return None

@handle_errors(error_types=(Exception,))
    def _initialize_parser(self, language_id: str) ->Any:
        """Initialize a tree-sitter parser for the given language."""
        try:
            return get_parser(language_id)
        except Exception as e:
            log(f'Failed to initialize tree-sitter parser for {language_id}: {str(e)}'
                , level='error')
            return None

    @handle_errors(error_types=(Exception,))
    def _extract_from_node(self, language_id: str, source_code: str, node: Any
        ) ->Optional[ExtractedBlock]:
        """Extract a code block from a tree-sitter Node."""
        if not node:
            return None
        try:
            if hasattr(node, 'text') and callable(getattr(node, 'text', None)):
                text = node.text.decode('utf8')
                if language_id == 'python' and node.type in (
                    'function_definition', 'class_definition'):
                    body_node = None
                    for child in node.children:
                        if child.type == 'block' or hasattr(child, 'field'
                            ) and child.field == 'body':
                            body_node = child
                            break
                    if body_node:
                        text = body_node.text.decode('utf8')
                        node = body_node
                return ExtractedBlock(content=text, start_point=node.
                    start_point, end_point=node.end_point, node_type=node.
                    type, metadata={'direct': True})
            start_byte = node.start_byte if hasattr(node, 'start_byte'
                ) else None
            end_byte = node.end_byte if hasattr(node, 'end_byte') else None
            if start_byte is not None and end_byte is not None:
                content = source_code[start_byte:end_byte]
                return ExtractedBlock(content=content, start_point=node.
                    start_point if hasattr(node, 'start_point') else (0, 0),
                    end_point=node.end_point if hasattr(node, 'end_point') else
                    (0, 0), node_type=node.type if hasattr(node, 'type') else
                    'unknown', metadata={'byte_extraction': True})
        except Exception as e:
            log(f'Error extracting block content: {str(e)}', level='error')
        return None

    def get_child_blocks(self, language_id: str, source_code: str,
        parent_node: Any) ->List[ExtractedBlock]:
        """
        Extract all child blocks from a parent node.
        
        Args:
            language_id: The language identifier
            source_code: The complete source code
            parent_node: The parent node to extract children from
            
        Returns:
            List of ExtractedBlock objects
        """
        blocks = []
        with ErrorBoundary(error_types=(Exception,), operation_name=
            'get_child_blocks'):
            if not parent_node or not hasattr(parent_node, 'children'):
                return blocks
            for child in parent_node.children:
                if not child.is_named:
                    continue
                if self._is_block_node(language_id, child):
                    block = self._extract_from_node(language_id,
                        source_code, child)
                    if block:
                        blocks.append(block)
                if self._is_container_node(language_id, child):
                    blocks.extend(self.get_child_blocks(language_id,
                        source_code, child))
        return blocks

    def _is_block_node(self, language_id: str, node: Any) ->bool:
        """Determine if a node represents a code block based on language-specific rules."""
        if not hasattr(node, 'type'):
            return False
        common_block_types = {'block', 'compound_statement',
            'statement_block', 'function_body', 'class_body', 'method_body'}
        language_block_types = {'python': {'block', 'function_definition',
            'class_definition', 'if_statement', 'for_statement',
            'while_statement', 'try_statement'}, 'javascript': {
            'statement_block', 'function_declaration', 'method_definition',
            'class_declaration', 'if_statement', 'for_statement'},
            'typescript': {'statement_block', 'function_declaration',
            'method_definition', 'class_declaration',
            'interface_declaration'}, 'cpp': {'compound_statement',
            'function_definition', 'class_specifier',
            'namespace_definition', 'if_statement', 'for_statement'},
            'java': {'block', 'class_body', 'method_declaration',
            'constructor_declaration', 'if_statement', 'for_statement',
            'try_statement'}, 'go': {'block', 'function_declaration',
            'method_declaration', 'if_statement', 'for_statement'}, 'rust':
            {'block', 'function_item', 'impl_item', 'for_expression',
            'if_expression'}}
        if node.type in common_block_types:
            return True
        if (language_id in language_block_types and node.type in
            language_block_types[language_id]):
            return True
        return False

    def _is_container_node(self, language_id: str, node: Any) ->bool:
        """
        Determine if a node is a container that might have block children.
        This helps with recursive traversal of the AST.
        """
        if not hasattr(node, 'type'):
            return False
        common_container_types = {'program', 'source_file',
            'translation_unit', 'namespace', 'module', 'package'}
        language_container_types = {'python': {'module', 'class_definition',
            'function_definition'}, 'javascript': {'program',
            'class_declaration', 'function_declaration', 'object'},
            'typescript': {'program', 'class_declaration',
            'interface_declaration', 'namespace_declaration'}, 'cpp': {
            'translation_unit', 'namespace_definition', 'class_specifier'},
            'java': {'program', 'class_declaration', 'method_declaration'},
            'go': {'source_file', 'function_declaration',
            'type_declaration'}, 'rust': {'source_file', 'impl_item',
            'trait_item', 'mod_item'}}
        if node.type in common_container_types:
            return True
        if (language_id in language_container_types and node.type in
            language_container_types[language_id]):
            return True
        return False


block_extractor = TreeSitterBlockExtractor()
