"""
Custom OCaml parsers with enhanced pattern extraction capabilities.

This module implements custom parsers for OCaml source files because we do not have
Tree-sitter language support for OCaml. Two kinds of source files are supported:
  - OCaml implementation files (.ml)
  - OCaml interface files (.mli)

Each parser extracts top-level declarations using regular expressions and converts the
source into a simplified custom AST with metadata (e.g. approximate byte positions,
document positions, and a top-level documentation comment if present).

NOTE:
  - This parser is intentionally a lightweight implementation meant for database ingestion
    and deep code base understanding. You can refine it over time to capture more detail.
  - Integrate this module with your main language parsing entry point so that when a file
    ends with .ml or .mli the corresponding function is called.

This module implements custom parsers for OCaml source files using a class-based structure.
Standalone parsing functions have been removed in favor of the classes below.
"""
import re
from typing import Dict, List, Any, Optional
from collections import Counter
from parsers.base_parser import BaseParser
from parsers.query_patterns.ocaml import OCAML_PATTERNS
from parsers.query_patterns.ocaml_interface import OCAML_INTERFACE_PATTERNS
from parsers.models import OcamlNode, PatternType
from parsers.types import FileType, ParserType, PatternCategory
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, AsyncErrorBoundary


@handle_errors(error_types=(Exception,))
def compute_offset(lines, line_no, col):
    """
    Compute the byte offset for a given (line, col) pair.
    We assume that each line is terminated by a single newline character.
    """
    return sum(len(lines[i]) + 1 for i in range(line_no)) + col


class OcamlParser(BaseParser):
    """Parser for OCaml files with enhanced pattern extraction capabilities."""

    def __init__(self, language_id: str='ocaml', file_type: Optional[
        FileType]=None):
        super().__init__(language_id, file_type or FileType.CODE,
            parser_type=ParserType.CUSTOM)
        self.is_interface = language_id == 'ocaml_interface'
        patterns_source = (OCAML_INTERFACE_PATTERNS if self.is_interface else
            OCAML_PATTERNS)
        self.patterns = self._compile_patterns(patterns_source)
@handle_errors(error_types=(Exception,))

    def initialize(self) ->bool:
        """Initialize parser resources."""
        self._initialized = True
        return True

    def _create_node(self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs) ->OcamlNode:
        """Create a standardized OCaml AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point,
            **kwargs)
        return OcamlNode(**node_dict)

    @handle_errors(error_types=(ParsingError,))
    def _parse_source(self, source_code: str) ->Dict[str, Any]:
        """Parse OCaml content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        with ErrorBoundary(operation_name='parsing OCaml content',
            error_types=(ParsingError,)) as error_boundary:
            try:
                lines = source_code.splitlines()
                ast = self._create_node('ocaml_module' if not self.
                    is_interface else 'ocaml_interface', [0, 0], [len(lines
                    ) - 1, len(lines[-1]) if lines else 0])
                patterns = (OCAML_INTERFACE_PATTERNS if self.is_interface else
                    OCAML_PATTERNS)
                current_doc = []
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    line = line.strip()
                    if not line:
                        continue
                    if (doc_match := self.patterns['doc_comment'].match(line)):
                        node = self._create_node('doc_comment', line_start,
                            line_end, **patterns['documentation'][
                            'doc_comment']['extract'](doc_match))
                        current_doc.append(node)
                        continue
                    for category in ['syntax', 'structure', 'semantics']:
                        for pattern_name, pattern_info in patterns[category
                            ].items():
                            if (match := self.patterns[pattern_name].match(
                                line)):
                                node = self._create_node(pattern_name,
                                    line_start, line_end, **pattern_info[
                                    'extract'](match))
                                if current_doc:
                                    node.metadata['documentation'
                                        ] = current_doc
                                    current_doc = []
                                ast.children.append(node)
                                break
                if current_doc:
                    ast.metadata['trailing_documentation'] = current_doc
                return ast.__dict__
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                log(f'Error parsing OCaml content: {e}', level='error')
                raise ParsingError(f'Failed to parse OCaml content: {str(e)}'
                    ) from e
        if error_boundary.error:
            log(f'Error in OCaml parser: {error_boundary.error}', level='error'
                )
            return OcamlNode(type='ocaml_module' if not self.is_interface else
                'ocaml_interface', start_point=[0, 0], end_point=[0, 0],
                error=str(error_boundary.error), children=[]).__dict__

    @handle_errors(error_types=(ProcessingError,))
    def extract_patterns(self, source_code: str) ->List[Dict[str, Any]]:
        """
        Extract code patterns from OCaml files for repository learning.
        
        Args:
            source_code: The content of the OCaml file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        with ErrorBoundary(operation_name='extracting OCaml patterns',
            error_types=(ProcessingError,)) as error_boundary:
            try:
                ast_dict = self._parse_source(source_code)
                let_binding_patterns = self._extract_let_binding_patterns(
                    ast_dict)
                for binding in let_binding_patterns:
                    patterns.append({'name':
                        f"ocaml_binding_{binding['name']}", 'content':
                        binding['content'], 'pattern_type': PatternType.
                        CODE_STRUCTURE, 'language': self.language_id,
                        'confidence': 0.9, 'metadata': {'type':
                        'ocaml_binding', 'name': binding['name'],
                        'is_recursive': binding.get('is_recursive', False)}})
                type_patterns = self._extract_type_patterns(ast_dict)
                for type_pattern in type_patterns:
                    patterns.append({'name':
                        f"ocaml_type_{type_pattern['name']}", 'content':
                        type_pattern['content'], 'pattern_type':
                        PatternType.CODE_STRUCTURE, 'language': self.
                        language_id, 'confidence': 0.85, 'metadata': {
                        'type': 'ocaml_type', 'name': type_pattern['name']}})
                module_patterns = self._extract_module_patterns(ast_dict)
                for module_pattern in module_patterns:
                    patterns.append({'name':
                        f"ocaml_module_{module_pattern['name']}", 'content':
                        module_pattern['content'], 'pattern_type':
                        PatternType.MODULE_STRUCTURE, 'language': self.
                        language_id, 'confidence': 0.9, 'metadata': {'type':
                        'ocaml_module', 'name': module_pattern['name'],
                        'elements': module_pattern.get('elements', [])}})
                naming_patterns = self._extract_naming_convention_patterns(
                    ast_dict)
                for naming in naming_patterns:
                    patterns.append({'name':
                        f"ocaml_naming_{naming['convention']}", 'content':
                        naming['content'], 'pattern_type': PatternType.
                        NAMING_CONVENTION, 'language': self.language_id,
                        'confidence': 0.85, 'metadata': {'type':
                        'naming_convention', 'convention': naming[
                        'convention'], 'examples': naming.get('examples', [])}}
                        )
                doc_patterns = self._extract_documentation_patterns(ast_dict)
                for doc in doc_patterns:
                    patterns.append({'name':
                        f"ocaml_documentation_{doc['type']}", 'content':
                        doc['content'], 'pattern_type': PatternType.
                        DOCUMENTATION_STRUCTURE, 'language': self.
                        language_id, 'confidence': 0.8, 'metadata': {'type':
                        'documentation', 'doc_type': doc['type'],
                        'examples': doc.get('examples', [])}})
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                log(f'Error extracting OCaml patterns: {e}', level='error')
                raise ProcessingError(
                    f'Failed to extract OCaml patterns: {str(e)}') from e
        if error_boundary.error:
            log(f'Error in OCaml pattern extraction: {error_boundary.error}',
                level='error')
        return patterns

    def _extract_let_binding_patterns(self, ast: Dict[str, Any]) ->List[Dict
        [str, Any]]:
        """Extract let binding patterns from the AST."""
@handle_errors(error_types=(Exception,))
        bindings = []

        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'let_binding':
                binding_name = self._extract_binding_name(node.get('name', ''))
                is_recursive = 'rec' in node.get('name', '')
                if binding_name:
                    bindings.append({'name': binding_name, 'content': node.
                        get('name', ''), 'is_recursive': is_recursive})
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return bindings

    def _extract_binding_name(self, binding_text: str) ->str:
        """Extract the name from a let binding text."""
        match = re.search('let\\s+(?:rec\\s+)?(\\w+)', binding_text)
        if match:
            return match.group(1)
        return ''

    def _extract_type_patterns(self, ast: Dict[str, Any]) ->List[Dict[str, Any]
        ]:
@handle_errors(error_types=(Exception,))
        """Extract type definition patterns from the AST."""
        types = []

        def process_node(node):
            if isinstance(node, dict) and node.get('type'
                ) == 'type_definition':
                type_name = node.get('name', '')
                if type_name:
                    types.append({'name': type_name, 'content':
                        f'type {type_name}'})
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        return types

    def _extract_module_patterns(self, ast: Dict[str, Any]) ->List[Dict[str,
@handle_errors(error_types=(Exception,))
        Any]]:
        """Extract module patterns from the AST."""
        modules = []

        def process_node(node):
            if isinstance(node, dict) and node.get('type'
                ) == 'module_declaration':
                module_name = node.get('name', '')
                if module_name:
                    elements = []
                    for child in node.get('children', []):
                        if isinstance(child, dict) and child.get('type') in [
                            'let_binding', 'type_definition']:
                            elements.append({'type': child.get('type'),
                                'name': child.get('name', '')})
                    modules.append({'name': module_name, 'content':
                        f'module {module_name}', 'elements': elements})
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
        file_elements = []
        for child in ast.get('children', []):
            if isinstance(child, dict):
                node_type = child.get('type')
                if node_type in ['let_binding', 'type_definition',
                    'module_declaration', 'open_statement']:
                    file_elements.append({'type': node_type, 'name': child.
                        get('name', '')})
        if file_elements:
            modules.append({'name': 'file_structure', 'content': 
                'File structure: ' + ', '.join(f"{e['type']} {e['name']}" for
                e in file_elements[:3]), 'elements': file_elements})
        process_node(ast)
        return modules

    def _extract_naming_convention_patterns(self, ast: Dict[str, Any]) ->List[
        Dict[str, Any]]:
@handle_errors(error_types=(Exception,))
        """Extract naming convention patterns from the AST."""
        values = []
        types = []
        modules = []

        def process_node(node):
            if isinstance(node, dict):
                node_type = node.get('type')
                name = node.get('name', '')
                if node_type == 'let_binding' and name:
                    binding_name = self._extract_binding_name(name)
                    if binding_name:
                        values.append(binding_name)
                elif node_type == 'type_definition' and name:
                    types.append(name)
                elif node_type == 'module_declaration' and name:
                    modules.append(name)
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        patterns = []
        if values:
            value_convention = self._analyze_naming_convention(values)
            if value_convention:
                patterns.append({'convention': f'value_{value_convention}',
                    'content':
                    f"Value naming convention: {value_convention} (e.g., {', '.join(values[:3])})"
                    , 'examples': values[:5]})
        if types:
            type_convention = self._analyze_naming_convention(types)
            if type_convention:
                patterns.append({'convention': f'type_{type_convention}',
                    'content':
                    f"Type naming convention: {type_convention} (e.g., {', '.join(types[:3])})"
                    , 'examples': types[:5]})
        if modules:
            module_convention = self._analyze_naming_convention(modules)
            if module_convention:
                patterns.append({'convention':
                    f'module_{module_convention}', 'content':
                    f"Module naming convention: {module_convention} (e.g., {', '.join(modules[:3])})"
                    , 'examples': modules[:5]})
        return patterns

    def _analyze_naming_convention(self, names: List[str]) ->Optional[str]:
        """Analyze the naming convention of a list of names."""
        if not names:
            return None
        camel_case = sum(1 for name in names if re.match(
            '^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name))
        snake_case = sum(1 for name in names if re.match(
            '^[a-z][a-z0-9_]*$', name) and '_' in name)
        lowercase = sum(1 for name in names if re.match('^[a-z][a-z0-9]*$',
            name) and not any(c.isupper() for c in name) and '_' not in name)
        uppercase_first = sum(1 for name in names if re.match(
            '^[A-Z][a-zA-Z0-9_]*$', name))
        conventions = {'camelCase': camel_case, 'snake_case': snake_case,
            'lowercase': lowercase, 'CapitalizedWord': uppercase_first}
        if any(conventions.values()):
            dominant = max(conventions.items(), key=lambda x: x[1])
            if dominant[1] > 0:
                return dominant[0]
        return None
@handle_errors(error_types=(Exception,))

    def _extract_documentation_patterns(self, ast: Dict[str, Any]) ->List[Dict
        [str, Any]]:
        """Extract documentation patterns from the AST."""
        doc_patterns = {}

        def process_node(node):
            if isinstance(node, dict):
                if (node_type := node.get('type')):
                    if node_type == 'doc_comment':
                        content = node.get('content', '')
                        if content:
                            doc_patterns.setdefault('doc_comment', []).append(
                                content)
                    elif node.get('metadata', {}).get('documentation'):
                        node_docs = node['metadata']['documentation']
                        for doc in node_docs:
                            if isinstance(doc, dict) and doc.get('type'
                                ) == 'doc_comment':
                                content = doc.get('content', '')
                                target_type = node.get('type', 'unknown')
                                key = f'{target_type}_doc'
                                if content:
                                    doc_patterns.setdefault(key, []).append(
                                        content)
                for child in node.get('children', []):
                    process_node(child)
        process_node(ast)
        results = []
        for doc_type, examples in doc_patterns.items():
            if examples:
                results.append({'type': doc_type, 'content': 
                    f"{doc_type.replace('_', ' ')} style: " + examples[0][:
                    50] + ('...' if len(examples[0]) > 50 else ''),
                    'examples': examples[:5]})
        return results
