"""
Custom YAML parser.

This parser processes YAML files using the pyyaml library, extracting
structured data and patterns.
"""
from typing import Dict, List, Any, Optional, Tuple
import yaml
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.yaml import YAML_PATTERNS
from parsers.models import YamlNode, PatternType
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, AsyncErrorBoundary
from collections import Counter
import re


class YamlParser(BaseParser):
    """Parser for YAML files."""

    def __init__(self, language_id: str='yaml', file_type: Optional[
        FileType]=None):
        super().__init__(language_id, file_type or FileType.DATA,
            parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(YAML_PATTERNS)

@handle_errors(error_types=(Exception,))
    def initialize(self) ->bool:
        self._initialized = True
        return True

    def _create_node(self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs) ->YamlNode:
        node_dict = super()._create_node(node_type, start_point, end_point,
            **kwargs)
        return YamlNode(**node_dict)

    def _process_value(self, value: Any, path: List[str], start_point: List
        [int]) ->YamlNode:
        node = self._create_node(type(value).__name__, start_point, [
            start_point[0], start_point[1] + len(str(value))], path='.'.
            join(path))
        if isinstance(value, dict):
            node.type = 'mapping'
            for key, val in value.items():
                child = self._process_value(val, path + [str(key)], [
                    start_point[0], start_point[1] + 1])
                child.key = key
                for pattern_name in ['url', 'path', 'version']:
                    if (pattern_match := self.patterns[pattern_name].match(
                        str(val))):
                        child.metadata['semantics'] = YAML_PATTERNS[
                            PatternCategory.SEMANTICS][pattern_name].extract(
                            pattern_match)
                node.children.append(child)
        elif isinstance(value, list):
            node.type = 'sequence'
            for i, item in enumerate(value):
                child = self._process_value(item, path + [f'[{i}]'], [
                    start_point[0], start_point[1] + 1])
                node.children.append(child)
        else:
            node.type = 'scalar'
            node.value = value
        return node

    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) ->Dict[str, Any]:
        """Parse YAML content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        with ErrorBoundary(operation_name='yaml file parsing'):
            try:
                lines = source_code.splitlines()
                ast = self._create_node('document', [0, 0], [len(lines) - 1,
                    len(lines[-1]) if lines else 0])
                current_comment_block = []
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    if (comment_match := self.patterns['comment'].match(line)):
                        current_comment_block.append(comment_match.group(1)
                            .strip())
                        continue
                    if line.strip() and current_comment_block:
                        node = self._create_node('comment_block', [i - len(
                            current_comment_block), 0], [i - 1, len(
                            current_comment_block[-1])], content='\n'.join(
                            current_comment_block))
                        ast.children.append(node)
                        current_comment_block = []
                try:
                    data = yaml.safe_load(source_code)
                    if data is not None:
                        root_node = self._process_value(data, [], [0, 0])
                        ast.children.append(root_node)
                        for pattern_name in ['description', 'metadata']:
                            if YAML_PATTERNS[PatternCategory.DOCUMENTATION][
                                pattern_name].pattern(root_node.__dict__):
                                ast.metadata['documentation'] = YAML_PATTERNS[
                                    PatternCategory.DOCUMENTATION][pattern_name
                                    ].extract(root_node.__dict__)
                except yaml.YAMLError as e:
                    log(f'Error parsing YAML structure: {e}', level='error')
                    ast.metadata['parse_error'] = str(e)
                if current_comment_block:
                    ast.metadata['trailing_comments'] = current_comment_block
                return ast.__dict__
            except (ValueError, KeyError, TypeError) as e:
                log(f'Error parsing YAML content: {e}', level='error')
                return YamlNode(type='document', start_point=[0, 0],
                    end_point=[0, 0], error=str(e), children=[]).__dict__

    @handle_errors(error_types=(ParsingError, ProcessingError))
    def extract_patterns(self, source_code: str) ->List[Dict[str, Any]]:
        """Extract patterns from YAML files for repository learning.
        
        Args:
            source_code: The content of the YAML file
            
        Returns:
            List of extracted patterns with metadata
        """
        with ErrorBoundary(operation_name='yaml pattern extraction'):
            try:
                patterns = []
                ast = self._parse_source(source_code)
                mapping_patterns = self._extract_mapping_patterns(ast)
                for mapping in mapping_patterns:
                    patterns.append({'name':
                        f"yaml_mapping_{mapping['type']}", 'content':
                        mapping['content'], 'pattern_type': PatternType.
                        CODE_STRUCTURE, 'language': self.language_id,
                        'confidence': 0.8, 'metadata': {'type': 'mapping',
                        'key_pattern': mapping['key_pattern'], 'value_type':
                        mapping['value_type']}})
                sequence_patterns = self._extract_sequence_patterns(ast)
                for sequence in sequence_patterns:
                    patterns.append({'name':
                        f"yaml_sequence_{sequence['type']}", 'content':
                        sequence['content'], 'pattern_type': PatternType.
                        CODE_STRUCTURE, 'language': self.language_id,
                        'confidence': 0.75, 'metadata': {'type': 'sequence',
                        'item_type': sequence['item_type'], 'length':
                        sequence['length']}})
                reference_patterns = self._extract_reference_patterns(ast)
                for reference in reference_patterns:
                    patterns.append({'name':
                        f"yaml_reference_{reference['type']}", 'content':
                        reference['content'], 'pattern_type': PatternType.
                        CODE_REFERENCE, 'language': self.language_id,
                        'confidence': 0.9, 'metadata': {'type': reference[
                        'type'], 'name': reference['name']}})
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({'name':
                        f"yaml_comment_{comment['type']}", 'content':
                        comment['content'], 'pattern_type': PatternType.
                        DOCUMENTATION, 'language': self.language_id,
                        'confidence': 0.7, 'metadata': {'type': 'comment',
                        'style': comment['type']}})
                naming_patterns = self._extract_naming_patterns(source_code)
                for naming in naming_patterns:
                    patterns.append({'name':
                        f"yaml_naming_{naming['type']}", 'content': naming[
                        'content'], 'pattern_type': PatternType.CODE_NAMING,
                        'language': self.language_id, 'confidence': 0.8,
                        'metadata': {'type': 'naming', 'convention': naming
                        ['type'], 'examples': naming['examples']}})
                return patterns
            except (ValueError, KeyError, TypeError, yaml.YAMLError) as e:
                log(f'Error extracting patterns from YAML file: {str(e)}',
                    level='error')
                return []

    def _extract_mapping_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract mapping patterns from the AST."""
        mappings = []
@handle_errors(error_types=(Exception,))

        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'mapping':
                    mappings.append({'path': node.get('path', 'unknown'),
                        'content': str(node), 'key_count': len(node.get(
                        'children', []))})
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return mappings

    def _extract_sequence_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract sequence patterns from the AST."""
@handle_errors(error_types=(Exception,))
        sequences = []

        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'sequence':
                    sequences.append({'path': node.get('path', 'unknown'),
                        'content': str(node), 'item_count': len(node.get(
                        'children', []))})
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return sequences

    def _extract_reference_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract anchor and alias patterns from the AST."""
        references = []
@handle_errors(error_types=(Exception,))
        anchor_pattern = re.compile('&([a-zA-Z0-9_-]+)\\s')
        alias_pattern = re.compile('\\*([a-zA-Z0-9_-]+)')

        def find_references_in_content(content):
            for match in anchor_pattern.finditer(content):
                references.append({'type': 'anchor', 'name': match.group(1),
                    'content': match.group(0)})
@handle_errors(error_types=(Exception,))
            for match in alias_pattern.finditer(content):
                references.append({'type': 'alias', 'name': match.group(1),
                    'content': match.group(0)})

        def process_node(node):
            if isinstance(node, dict):
                node_str = str(node)
                find_references_in_content(node_str)
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return references

@handle_errors(error_types=(Exception,))
    def _extract_comment_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract comment patterns from the AST."""
        comments = []

        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'comment_block':
                    content = node.get('content', '')
                    comments.append({'type': 'block_comment', 'content':
                        content, 'line_count': content.count('\n') + 1})
                if node.get('metadata', {}).get('trailing_comments'):
                    content = '\n'.join(node.get('metadata', {}).get(
                        'trailing_comments', []))
                    comments.append({'type': 'trailing_comment', 'content':
                        content, 'line_count': len(node.get('metadata', {})
                        .get('trailing_comments', []))})
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return comments

    def _extract_naming_patterns(self, source_code: str) ->List[Dict[str, Any]
        ]:
        """Extract naming convention patterns from the source code."""
        patterns = []
        snake_case_keys = 0
        camel_case_keys = 0
        kebab_case_keys = 0
        snake_case_pattern = re.compile('^\\s*([a-z][a-z0-9_]*[a-z0-9]):\\s',
            re.MULTILINE)
        camel_case_pattern = re.compile(
            '^\\s*([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*):\\s', re.MULTILINE)
        kebab_case_pattern = re.compile('^\\s*([a-z][a-z0-9-]*[a-z0-9]):\\s',
            re.MULTILINE)
        for match in snake_case_pattern.finditer(source_code):
            if '_' in match.group(1):
                snake_case_keys += 1
        for match in camel_case_pattern.finditer(source_code):
            if not '_' in match.group(1) and not '-' in match.group(1):
                camel_case_keys += 1
        for match in kebab_case_pattern.finditer(source_code):
            if '-' in match.group(1):
                kebab_case_keys += 1
        total_keys = snake_case_keys + camel_case_keys + kebab_case_keys
        if total_keys > 3:
            if (snake_case_keys >= camel_case_keys and snake_case_keys >=
                kebab_case_keys):
                convention = 'snake_case'
                dom_count = snake_case_keys
            elif camel_case_keys >= snake_case_keys and camel_case_keys >= kebab_case_keys:
                convention = 'camelCase'
                dom_count = camel_case_keys
            else:
                convention = 'kebab-case'
                dom_count = kebab_case_keys
            confidence = 0.5 + 0.3 * (dom_count / total_keys)
            patterns.append({'name': 'yaml_key_naming_convention',
                'content': f'Key naming convention: {convention}',
                'pattern_type': PatternType.NAMING_CONVENTION, 'language':
                self.language_id, 'confidence': confidence, 'metadata': {
                'type': 'naming_convention', 'element_type': 'key',
                'convention': convention, 'snake_case_count':
                snake_case_keys, 'camel_case_count': camel_case_keys,
                'kebab_case_count': kebab_case_keys}})
        return patterns
