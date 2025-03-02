"""Custom parser for JSON files with enhanced documentation and pattern extraction."""
from typing import Dict, List, Any, Optional, Union, Tuple
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.models import JsonNode, PatternType
from parsers.query_patterns.json import JSON_PATTERNS
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, AsyncErrorBoundary
import json
import re
from collections import Counter


class JsonParser(BaseParser):
    """Parser for JSON files with enhanced documentation and structure analysis."""

    def __init__(self, language_id: str='json', file_type: Optional[
        FileType]=None):
        super().__init__(language_id, file_type or FileType.DATA,
            parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(JSON_PATTERNS)

@handle_errors(error_types=(Exception,))
    def initialize(self) ->bool:
        """Initialize parser resources."""
        self._initialized = True
        return True

    def _create_node(self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs) ->JsonNode:
        """Create a standardized JSON AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point,
            **kwargs)
        return JsonNode(**node_dict)

    def _process_json_value(self, value: Any, path: str, parent_key:
        Optional[str]=None) ->JsonNode:
        """Process a JSON value into a node structure."""
        if isinstance(value, dict):
            node = self._create_node('object', [0, 0], [0, 0], path=path,
                children=[], keys=list(value.keys()), key_ordering=list(
                value.keys()), parent_key=parent_key, schema_type='object')
            for key, item in value.items():
                child_path = f'{path}.{key}' if path else key
                child = self._process_json_value(item, child_path, key)
                node.children.append(child)
            return node
        elif isinstance(value, list):
            node = self._create_node('array', [0, 0], [0, 0], path=path,
                children=[], items_count=len(value), parent_key=parent_key,
                schema_type='array')
            for idx, item in enumerate(value):
                child_path = f'{path}[{idx}]' if path else f'[{idx}]'
                child = self._process_json_value(item, child_path)
                node.children.append(child)
            return node
        else:
            if value is None:
                schema_type = 'null'
            elif isinstance(value, bool):
                schema_type = 'boolean'
            elif isinstance(value, int):
                schema_type = 'integer'
            elif isinstance(value, float):
                schema_type = 'number'
            elif isinstance(value, str):
                schema_type = 'string'
                if re.match('^\\d{4}-\\d{2}-\\d{2}', value):
                    if re.match('^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}',
                        value):
                        schema_type = 'string:datetime'
                    else:
                        schema_type = 'string:date'
                elif re.match(
                    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                    , value, re.I):
                    schema_type = 'string:uuid'
                elif re.match('^https?://', value):
                    schema_type = 'string:uri'
                elif re.match('^[\\w._%+-]+@[\\w.-]+\\.[a-zA-Z]{2,}$', value):
                    schema_type = 'string:email'
            else:
                schema_type = 'unknown'
            return self._create_node('value', [0, 0], [0, 0], path=path,
                parent_key=parent_key, schema_type=schema_type, value=value,
                value_type=type(value).__name__)

    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) ->Dict[str, Any]:
        """Parse JSON content into AST structure with caching support."""
        lines = source_code.splitlines()
        line_count = len(lines)
        with ErrorBoundary(error_types=(ParsingError,), context='JSON parsing'
            ):
            try:
                data = json.loads(source_code)
                ast = self._process_json_value(data, '')
                ast.start_point = [0, 0]
                ast.end_point = [line_count - 1, len(lines[-1]) if lines else 0
                    ]
                self._analyze_structure(ast)
                return ast.__dict__
            except json.JSONDecodeError as e:
                log(f'Error parsing JSON: {e}', level='error')
                return self._create_node('document', [0, 0], [line_count - 
                    1, len(lines[-1]) if lines else 0], error=str(e),
                    children=[]).__dict__

    def _analyze_structure(self, node: JsonNode) ->None:
        """Analyze JSON structure for insights."""
        if node.type == 'object':
            if node.keys:
                conventions = self._detect_naming_convention(node.keys)
                node.metadata['naming_convention'] = conventions[0
                    ] if conventions else 'mixed'
                node.metadata['naming_conventions'] = conventions
            max_depth = 0
            for child in node.children:
                self._analyze_structure(child)
                child_depth = child.metadata.get('max_depth', 0)
                max_depth = max(max_depth, child_depth + 1)
            node.metadata['max_depth'] = max_depth
        elif node.type == 'array':
            schema_types = [child.schema_type for child in node.children]
            if schema_types:
                is_homogeneous = len(set(schema_types)) == 1
                node.metadata['is_homogeneous'] = is_homogeneous
                node.metadata['item_type'] = schema_types[0
                    ] if is_homogeneous else 'mixed'
            max_depth = 0
            for child in node.children:
                self._analyze_structure(child)
                child_depth = child.metadata.get('max_depth', 0)
                max_depth = max(max_depth, child_depth + 1)
            node.metadata['max_depth'] = max_depth
        else:
            node.metadata['max_depth'] = 0

    def _detect_naming_convention(self, keys: List[str]) ->List[str]:
        """Detect naming conventions in a list of keys."""
        conventions = []
        if any(re.match('^[a-z][a-zA-Z0-9]*$', key) and any(c.isupper() for
            c in key) for key in keys):
            conventions.append('camelCase')
        if any(re.match('^[a-z][a-z0-9_]*$', key) and '_' in key for key in
            keys):
            conventions.append('snake_case')
        if any(re.match('^[a-z][a-z0-9-]*$', key) and '-' in key for key in
            keys):
            conventions.append('kebab-case')
        if any(re.match('^[A-Z][a-zA-Z0-9]*$', key) for key in keys):
            conventions.append('PascalCase')
        if any(re.match('^[A-Z][A-Z0-9_]*$', key) and '_' in key for key in
            keys):
            conventions.append('UPPER_CASE')
        return conventions

    @handle_errors(error_types=(ProcessingError,))
    def extract_patterns(self, source_code: str) ->List[Dict[str, Any]]:
        """
        Extract JSON patterns from the source code for repository learning.
        
        Args:
            source_code: The content of the JSON file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        with ErrorBoundary(error_types=(ProcessingError,), context=
            'JSON pattern extraction'):
            try:
                ast_dict = self._parse_source(source_code)
                ast = JsonNode(**ast_dict)
                structure_patterns = self._extract_structure_patterns(ast)
                patterns.extend(structure_patterns)
                naming_patterns = self._extract_naming_convention_patterns(ast)
                patterns.extend(naming_patterns)
                schema_patterns = self._extract_schema_patterns(ast)
                patterns.extend(schema_patterns)
                field_patterns = self._extract_common_field_patterns(ast)
                patterns.extend(field_patterns)
            except (ValueError, KeyError, TypeError) as e:
                log(f'Error extracting JSON patterns: {e}', level='error')
        return patterns

    def _extract_structure_patterns(self, ast: JsonNode) ->List[Dict[str, Any]
        ]:
        """Extract structure patterns from the AST."""
        patterns = []
        if ast.type == 'object':
            patterns.append({'name': 'json_root_structure', 'content': json
                .dumps({'root_keys': ast.keys}, indent=2), 'pattern_type':
                PatternType.DATA_STRUCTURE, 'language': self.language_id,
                'confidence': 0.9, 'metadata': {'root_keys': ast.keys,
                'max_depth': ast.metadata.get('max_depth', 0)}})
            if self._is_likely_config_file(ast):
                patterns.append({'name': 'json_config_file', 'content':
                    json.dumps({'type': 'configuration_file'}, indent=2),
                    'pattern_type': PatternType.FILE_TYPE, 'language': self
                    .language_id, 'confidence': 0.85, 'metadata': {
                    'file_type': 'configuration', 'config_sections': self.
                    _extract_config_sections(ast)}})
        elif ast.type == 'array':
            item_types = self._analyze_array_item_types(ast)
            patterns.append({'name': 'json_array_structure', 'content':
                json.dumps({'root_structure': 'array', 'item_types':
                item_types}, indent=2), 'pattern_type': PatternType.
                DATA_STRUCTURE, 'language': self.language_id, 'confidence':
                0.9, 'metadata': {'is_homogeneous': ast.metadata.get(
                'is_homogeneous', False), 'item_type': ast.metadata.get(
                'item_type', 'mixed'), 'items_count': ast.items_count,
                'item_types': item_types}})
            if self._is_likely_data_collection(ast):
                patterns.append({'name': 'json_data_collection', 'content':
                    json.dumps({'type': 'data_collection'}, indent=2),
                    'pattern_type': PatternType.FILE_TYPE, 'language': self
                    .language_id, 'confidence': 0.85, 'metadata': {
                    'file_type': 'data_collection', 'item_count': ast.
                    items_count, 'common_fields': self.
                    _extract_common_fields(ast)}})
        nested_patterns = self._extract_nested_structure_patterns(ast)
        patterns.extend(nested_patterns)
        return patterns

    def _extract_naming_convention_patterns(self, ast: JsonNode) ->List[Dict
        [str, Any]]:
        """Extract naming convention patterns from the AST."""
        patterns = []
        conventions = {}
@handle_errors(error_types=(Exception,))

        def collect_conventions(node):
            if node.type == 'object' and node.metadata.get('naming_convention'
                ):
                convention = node.metadata['naming_convention']
                if convention != 'mixed':
                    conventions[convention] = conventions.get(convention, 0
                        ) + 1
            for child in node.children:
                collect_conventions(child)
        collect_conventions(ast)
        if conventions:
            dominant_convention = max(conventions.items(), key=lambda x: x[1])[
                0]
            patterns.append({'name':
                f'json_naming_convention_{dominant_convention}', 'content':
                f'JSON naming convention: {dominant_convention}',
                'pattern_type': PatternType.NAMING_CONVENTION, 'language':
                self.language_id, 'confidence': min(0.7 + conventions[
                dominant_convention] / 10, 0.95), 'metadata': {'convention':
                dominant_convention, 'frequency': conventions[
                dominant_convention], 'all_conventions': conventions}})
        return patterns

    def _extract_schema_patterns(self, ast: JsonNode) ->List[Dict[str, Any]]:
        """Extract schema patterns from the AST."""
        patterns = []
@handle_errors(error_types=(Exception,))
        field_schemas = {}

        def collect_field_schemas(node, path=''):
            if node.type == 'object':
                for child in node.children:
                    child_path = (f'{path}.{child.parent_key}' if path else
                        child.parent_key)
                    if child.type == 'value':
                        field_schemas[child_path] = child.schema_type
                    collect_field_schemas(child, child_path)
            elif node.type == 'array' and node.children and node.metadata.get(
                'is_homogeneous', False):
                sample_child = node.children[0]
                if sample_child.type == 'object':
                    collect_field_schemas(sample_child, f'{path}[item]')
        collect_field_schemas(ast)
        if field_schemas:
            patterns.append({'name': 'json_schema_fields', 'content': json.
                dumps(field_schemas, indent=2), 'pattern_type': PatternType
                .DATA_SCHEMA, 'language': self.language_id, 'confidence': 
                0.85, 'metadata': {'field_schemas': field_schemas}})
            special_types = {k: v for k, v in field_schemas.items() if ':' in
                v and v.startswith('string:')}
            if special_types:
                patterns.append({'name': 'json_special_field_types',
                    'content': json.dumps(special_types, indent=2),
                    'pattern_type': PatternType.DATA_SCHEMA, 'language':
                    self.language_id, 'confidence': 0.9, 'metadata': {
                    'special_field_types': special_types}})
        return patterns

    def _extract_common_field_patterns(self, ast: JsonNode) ->List[Dict[str,
        Any]]:
        """Extract common field patterns from the AST."""
@handle_errors(error_types=(Exception,))
        patterns = []
        common_fields = set()

        def collect_fields(node, field_set=None):
            if field_set is None:
                field_set = set()
            if node.type == 'object':
                field_set.update(node.keys)
            for child in node.children:
                collect_fields(child, field_set)
            return field_set
        all_fields = collect_fields(ast)
        common_patterns = [('id', 'identifier_field', ['id', '_id', 'uuid',
            'guid']), ('timestamp', 'timestamp_field', ['created_at',
            'updated_at', 'timestamp', 'date', 'time', 'created', 'updated'
            ]), ('user', 'user_field', ['user', 'user_id', 'author',
            'owner', 'creator']), ('status', 'status_field', ['status',
            'state', 'active', 'enabled', 'disabled']), ('type',
            'type_field', ['type', 'kind', 'category', 'class']), (
            'version', 'version_field', ['version', 'v', 'rev', 'revision']
            ), ('config', 'config_field', ['config', 'configuration',
            'settings', 'options']), ('metadata', 'metadata_field', [
            'metadata', 'meta', 'info', 'data']), ('pagination',
            'pagination_field', ['page', 'limit', 'offset', 'per_page',
            'total']), ('error', 'error_field', ['error', 'errors',
            'message', 'code', 'success'])]
        for pattern_type, pattern_name, keywords in common_patterns:
            matching_fields = [field for field in all_fields if field.lower
                () in keywords]
            if matching_fields:
                patterns.append({'name': f'json_{pattern_name}', 'content':
                    json.dumps({pattern_type: matching_fields}, indent=2),
                    'pattern_type': PatternType.DATA_FIELD, 'language':
                    self.language_id, 'confidence': 0.9, 'metadata': {
                    'field_type': pattern_type, 'matching_fields':
                    matching_fields}})
        return patterns

    def _is_likely_config_file(self, ast: JsonNode) ->bool:
        """Check if this is likely a configuration file."""
        if ast.type != 'object':
            return False
        config_indicators = ['config', 'configuration', 'settings',
            'options', 'preferences', 'environment', 'env', 'development',
            'production', 'staging', 'debug', 'release', 'version']
        for key in ast.keys:
            if key.lower() in config_indicators:
                return True
        has_nested_objects = any(child.type == 'object' for child in ast.
            children)
        has_primitive_values = any(child.type == 'value' for child in ast.
            children)
        return has_nested_objects and has_primitive_values

    def _extract_config_sections(self, ast: JsonNode) ->List[str]:
        """Extract configuration sections from a config file."""
        if ast.type != 'object':
            return []
        return [child.parent_key for child in ast.children if child.type ==
            'object' and child.parent_key]

    def _is_likely_data_collection(self, ast: JsonNode) ->bool:
        """Check if this is likely a data collection."""
        if ast.type != 'array' or not ast.children:
            return False
        is_array_of_objects = all(child.type == 'object' for child in ast.
            children)
        if is_array_of_objects and len(ast.children) > 1:
            common_fields = self._extract_common_fields(ast)
            return len(common_fields) >= 2
        return False

    def _extract_common_fields(self, ast: JsonNode) ->List[str]:
        """Extract common fields from an array of objects."""
        if ast.type != 'array' or not ast.children:
            return []
        object_children = [child for child in ast.children if child.type ==
            'object']
        if not object_children:
            return []
        all_fields = Counter()
        for child in object_children:
            all_fields.update(child.keys)
        threshold = 0.7 * len(object_children)
        return [field for field, count in all_fields.items() if count >=
            threshold]

    def _extract_nested_structure_patterns(self, ast: JsonNode) ->List[Dict
@handle_errors(error_types=(Exception,))
        [str, Any]]:
        """Extract patterns from nested structures."""
        patterns = []

        def process_nested_objects(node, path=''):
            if node.type == 'object' and len(node.keys) >= 3:
                patterns.append({'name':
                    f"json_nested_object_{path.replace('.', '_')}",
                    'content': json.dumps({'path': path, 'keys': node.keys},
                    indent=2), 'pattern_type': PatternType.DATA_STRUCTURE,
                    'language': self.language_id, 'confidence': 0.8,
                    'metadata': {'path': path, 'keys': node.keys, 'depth': 
                    path.count('.') + 1}})
            for child in node.children:
                if child.type in ['object', 'array']:
                    child_path = (f'{path}.{child.parent_key}' if path and
                        child.parent_key else child.parent_key if child.
                        parent_key else path)
                    process_nested_objects(child, child_path)
        process_nested_objects(ast)
        return patterns

    def _analyze_array_item_types(self, array_node: JsonNode) ->Dict[str, int]:
        """Analyze the types of items in an array."""
        if array_node.type != 'array':
            return {}
        type_counter = Counter()
        for child in array_node.children:
            type_counter[child.type] += 1
        return dict(type_counter)
