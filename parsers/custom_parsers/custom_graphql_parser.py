"""
Custom GraphQL parser.

This parser uses regexes to capture common GraphQL definitions such as type, interface,
enum, or schema definitions from a GraphQL file.
"""
from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.graphql import GRAPHQL_PATTERNS
from parsers.models import GraphQLNode, PatternType
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, AsyncErrorBoundary
import re


class GraphqlParser(BaseParser):
    """Parser for GraphQL schema files."""

    def __init__(self, language_id: str='graphql', file_type: Optional[
        FileType]=None):
        super().__init__(language_id, file_type or FileType.CODE,
            parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(GRAPHQL_PATTERNS)

@handle_errors(error_types=(Exception,))
    def initialize(self) ->bool:
        """Initialize parser resources."""
        self._initialized = True
        return True

    def _create_node(self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs) ->GraphQLNode:
        """Create a standardized GraphQL AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point,
            **kwargs)
        return GraphQLNode(**node_dict)

    def _process_arguments(self, args_str: str) ->List[Dict]:
        """Process field arguments into structured nodes."""
        if not args_str:
            return []
        arg_nodes = []
        args = [arg.strip() for arg in args_str.split(',')]
        for arg in args:
            if (match := self.patterns['argument'].match(arg)):
                arg_data = GRAPHQL_PATTERNS[PatternCategory.SEMANTICS][
                    'argument'].extract(match)
                arg_data['line_number'] = match.string.count('\n', 0, match
                    .start()) + 1
                arg_nodes.append(arg_data)
        return arg_nodes

    def _process_directives(self, line: str, line_number: int) ->List[Dict]:
        """Extract directives as structured nodes."""
        directives = []
        for match in self.patterns['directive'].finditer(line):
            directive = GRAPHQL_PATTERNS[PatternCategory.SEMANTICS]['directive'
                ].extract(match)
            directive['line_number'] = line_number
            directive['arguments'] = self._process_arguments(directive[
                'arguments'])
            directives.append(directive)
        return directives

    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) ->Dict[str, Any]:
        """Parse GraphQL content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        with ErrorBoundary(error_types=(ParsingError,), context=
            'GraphQL parsing'):
            try:
                lines = source_code.splitlines()
                ast = self._create_node('document', [0, 0], [len(lines) - 1,
                    len(lines[-1]) if lines else 0])
                current_type = None
                current_interface = None
                current_description = None
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    line = line.strip()
                    if not line:
                        continue
                    if (desc_match := self.patterns['description'].match(line)
                        ):
                        node = self._create_node('description', line_start,
                            line_end, **GRAPHQL_PATTERNS[PatternCategory.
                            DOCUMENTATION]['description'].extract(desc_match))
                        ast.children.append(node)
                        current_description = node
                        continue
                    if (comment_match := self.patterns['comment'].match(line)):
                        node = self._create_node('comment', line_start,
                            line_end, **GRAPHQL_PATTERNS[PatternCategory.
                            DOCUMENTATION]['comment'].extract(comment_match))
                        ast.children.append(node)
                        continue
                    if (type_match := self.patterns['type'].match(line)):
                        node = self._create_node('type', line_start,
                            line_end, **GRAPHQL_PATTERNS[PatternCategory.
                            SYNTAX]['type'].extract(type_match))
                        if current_description:
                            node.metadata['description'] = current_description
                            current_description = None
                        ast.children.append(node)
                        current_type = node
                        continue
                    if (interface_match := self.patterns['interface'].match
                        (line)):
                        node = self._create_node('interface', line_start,
                            line_end, **GRAPHQL_PATTERNS[PatternCategory.
                            STRUCTURE]['interface'].extract(interface_match))
                        if current_description:
                            node.metadata['description'] = current_description
                            current_description = None
                        ast.children.append(node)
                        current_interface = node
                        continue
                    if (field_match := self.patterns['field'].match(line)):
                        if not (current_type or current_interface):
                            continue
                        field_data = GRAPHQL_PATTERNS[PatternCategory.SYNTAX][
                            'field'].extract(field_match)
                        field_data['arguments'] = self._process_arguments(
                            field_data['arguments'])
                        field_data['directives'] = self._process_directives(
                            line, i + 1)
                        node = self._create_node('field', line_start,
                            line_end, **field_data)
                        if current_type:
                            current_type.children.append(node)
                        else:
                            current_interface.children.append(node)
                        continue
                    if (fragment_match := self.patterns['fragment'].match(line)
                        ):
                        node = self._create_node('fragment', line_start,
                            line_end, **GRAPHQL_PATTERNS[PatternCategory.
                            STRUCTURE]['fragment'].extract(fragment_match))
                        ast.children.append(node)
                return ast.__dict__
            except Exception as e:
                log(f'Error parsing GraphQL content: {e}', level='error')
                return GraphQLNode(type='document', start_point=[0, 0],
                    end_point=[0, 0], error=str(e), children=[]).__dict__

    @handle_errors(error_types=(ProcessingError,))
    def extract_patterns(self, source_code: str) ->List[Dict[str, Any]]:
        """
        Extract API and schema patterns from GraphQL files for repository learning.
        
        Args:
            source_code: The content of the GraphQL file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        with ErrorBoundary(error_types=(ProcessingError,), context=
            'GraphQL pattern extraction'):
            try:
                ast_dict = self._parse_source(source_code)
                types = self._extract_type_patterns(ast_dict)
                for type_pattern in types:
                    patterns.append({'name':
                        f"graphql_type_{type_pattern['name']}", 'content':
                        type_pattern['content'], 'pattern_type':
                        PatternType.CODE_STRUCTURE, 'language': self.
                        language_id, 'confidence': 0.9, 'metadata': {'type':
                        'graphql_type', 'name': type_pattern['name'],
                        'fields': type_pattern.get('fields', [])}})
                interfaces = self._extract_interface_patterns(ast_dict)
                for interface in interfaces:
                    patterns.append({'name':
                        f"graphql_interface_{interface['name']}", 'content':
                        interface['content'], 'pattern_type': PatternType.
                        CODE_STRUCTURE, 'language': self.language_id,
                        'confidence': 0.85, 'metadata': {'type':
                        'graphql_interface', 'name': interface['name'],
                        'fields': interface.get('fields', [])}})
                schema_patterns = self._extract_schema_patterns(ast_dict)
                for schema in schema_patterns:
                    patterns.append({'name':
                        f"graphql_schema_{schema['category']}", 'content':
                        schema['content'], 'pattern_type': PatternType.
                        CODE_STRUCTURE, 'language': self.language_id,
                        'confidence': 0.95, 'metadata': {'type':
                        'graphql_schema', 'category': schema['category'],
                        'elements': schema.get('elements', [])}})
                naming_patterns = self._extract_naming_patterns(ast_dict)
                for naming in naming_patterns:
                    patterns.append({'name':
                        f"graphql_naming_{naming['convention']}", 'content':
                        naming['examples'], 'pattern_type': PatternType.
                        CODE_NAMING, 'language': self.language_id,
                        'confidence': 0.8, 'metadata': {'type':
                        'naming_convention', 'convention': naming[
                        'convention'], 'examples': naming['examples'].split
                        (', ')}})
            except Exception as e:
                log(f'Error extracting GraphQL patterns: {e}', level='error')
        return patterns

    def _extract_type_patterns(self, ast: Dict[str, Any]) ->List[Dict[str, Any]
        ]:
        """Extract type patterns from the AST."""
        types = []
@handle_errors(error_types=(Exception,))

        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'type':
                fields = []
                for child in node.get('children', []):
                    if child.get('type') == 'field':
                        fields.append({'name': child.get('name', ''),
                            'field_type': child.get('field_type', '')})
                types.append({'name': node.get('name', ''), 'content': str(
                    node), 'fields': fields})
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return types

    def _extract_interface_patterns(self, ast: Dict[str, Any]) ->List[Dict[
        str, Any]]:
        """Extract interface patterns from the AST."""
@handle_errors(error_types=(Exception,))
        interfaces = []

        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'interface':
                fields = []
                for child in node.get('children', []):
                    if child.get('type') == 'field':
                        fields.append({'name': child.get('name', ''),
                            'field_type': child.get('field_type', '')})
                interfaces.append({'name': node.get('name', ''), 'content':
                    str(node), 'fields': fields})
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return interfaces

    def _extract_schema_patterns(self, ast: Dict[str, Any]) ->List[Dict[str,
        Any]]:
        """Extract schema patterns from the AST."""
        query_elements = []
@handle_errors(error_types=(Exception,))
        mutation_elements = []
        subscription_elements = []

        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'type':
                name = node.get('name', '')
                if name == 'Query':
                    for child in node.get('children', []):
                        if child.get('type') == 'field':
                            query_elements.append({'name': child.get('name',
                                ''), 'field_type': child.get('field_type', '')}
                                )
                elif name == 'Mutation':
                    for child in node.get('children', []):
                        if child.get('type') == 'field':
                            mutation_elements.append({'name': child.get(
                                'name', ''), 'field_type': child.get(
                                'field_type', '')})
                elif name == 'Subscription':
                    for child in node.get('children', []):
                        if child.get('type') == 'field':
                            subscription_elements.append({'name': child.get
                                ('name', ''), 'field_type': child.get(
                                'field_type', '')})
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        patterns = []
        if query_elements:
            patterns.append({'category': 'query', 'content': 'Query { ' +
                ', '.join(e['name'] for e in query_elements) + ' }',
                'elements': query_elements})
        if mutation_elements:
            patterns.append({'category': 'mutation', 'content': 
                'Mutation { ' + ', '.join(e['name'] for e in
                mutation_elements) + ' }', 'elements': mutation_elements})
        if subscription_elements:
            patterns.append({'category': 'subscription', 'content': 
                'Subscription { ' + ', '.join(e['name'] for e in
                subscription_elements) + ' }', 'elements':
                subscription_elements})
        return patterns

    def _extract_naming_patterns(self, ast: Dict[str, Any]) ->List[Dict[str,
        Any]]:
@handle_errors(error_types=(Exception,))
        """Extract naming convention patterns from the AST."""
        type_names = []
        field_names = []

        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'type' or node.get('type'
                    ) == 'interface':
                    name = node.get('name', '')
                    if name:
                        type_names.append(name)
                elif node.get('type') == 'field':
                    name = node.get('name', '')
                    if name:
                        field_names.append(name)
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        patterns = []
        pascal_case_types = [name for name in type_names if name[0].isupper
            () and not '_' in name]
        if len(pascal_case_types) > 0 and len(pascal_case_types) / max(1,
            len(type_names)) > 0.7:
            patterns.append({'convention': 'PascalCase_types', 'examples':
                ', '.join(pascal_case_types[:3])})
        camel_case_fields = [name for name in field_names if name[0].
            islower() and not '_' in name]
        if len(camel_case_fields) > 0 and len(camel_case_fields) / max(1,
            len(field_names)) > 0.7:
            patterns.append({'convention': 'camelCase_fields', 'examples':
                ', '.join(camel_case_fields[:3])})
        return patterns
