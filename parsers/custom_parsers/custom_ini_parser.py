"""Custom parser for INI/Properties files with enhanced pattern extraction."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.models import IniNode, PatternType
from parsers.query_patterns.ini import INI_PATTERNS
from utils.logger import log
import re
from collections import Counter

class IniParser(BaseParser):
    """Parser for INI files with enhanced pattern extraction capabilities."""
    
    def __init__(self, language_id: str = "ini", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        # Compile regex patterns from INI_PATTERNS using the shared helper.
        self.patterns = self._compile_patterns(INI_PATTERNS)
    
    def initialize(self) -> bool:
        """Initialize parser resources."""
        self._initialized = True
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> IniNode:
        """Create a standardized INI AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return IniNode(**node_dict)

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse INI content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "ini_file",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
            current_section = None
            current_comment_block = []
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                line = line.strip()
                if not line:
                    continue
                
                # Process comments
                if comment_match := self.patterns['comment'].match(line):
                    node = self._create_node(
                        "comment",
                        line_start,
                        line_end,
                        **INI_PATTERNS[PatternCategory.DOCUMENTATION]['comment'].extract(comment_match)
                    )
                    current_comment_block.append(node)
                    continue
                
                # Process sections
                if section_match := self.patterns['section'].match(line):
                    node = self._create_node(
                        "section",
                        line_start,
                        line_end,
                        **INI_PATTERNS[PatternCategory.SYNTAX]['section'].extract(section_match)
                    )
                    if current_comment_block:
                        node.metadata["comments"] = current_comment_block
                        current_comment_block = []
                    ast.children.append(node)
                    current_section = node
                    continue
                
                # Process properties
                if property_match := self.patterns['property'].match(line):
                    node = self._create_node(
                        "property",
                        line_start,
                        line_end,
                        **INI_PATTERNS[PatternCategory.SYNTAX]['property'].extract(property_match)
                    )
                    if current_comment_block:
                        node.metadata["comments"] = current_comment_block
                        current_comment_block = []
                    
                    # Check for semantic patterns.
                    for pattern_name in ['environment', 'path']:
                        if semantic_match := self.patterns[pattern_name].match(line):
                            semantic_data = INI_PATTERNS[PatternCategory.SEMANTICS][pattern_name].extract(semantic_match)
                            node.metadata["semantics"] = semantic_data
                    
                    if current_section:
                        current_section.children.append(node)
                    else:
                        ast.children.append(node)
            
            # Add any remaining comments.
            if current_comment_block:
                ast.metadata["trailing_comments"] = current_comment_block
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing INI content: {e}", level="error")
            return self._create_node(
                "ini_file",
                [0, 0],
                [0, 0],
                error=str(e),
                children=[]
            ).__dict__
            
    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract configuration patterns from INI files for repository learning.
        
        Args:
            source_code: The content of the INI file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        try:
            # Parse the source first to get a structured representation
            ast_dict = self._parse_source(source_code)
            
            # Extract section patterns
            section_patterns = self._extract_section_patterns(ast_dict)
            for section in section_patterns:
                patterns.append({
                    'name': f'ini_section_{section["name"]}',
                    'content': section["content"],
                    'pattern_type': PatternType.CONFIG_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.9,
                    'metadata': {
                        'type': 'ini_section',
                        'name': section["name"],
                        'properties': section.get("properties", [])
                    }
                })
            
            # Extract common property patterns
            property_patterns = self._extract_property_patterns(ast_dict)
            for prop in property_patterns:
                patterns.append({
                    'name': f'ini_property_{prop["category"]}',
                    'content': prop["content"],
                    'pattern_type': PatternType.CONFIG_PROPERTY,
                    'language': self.language_id,
                    'confidence': 0.85,
                    'metadata': {
                        'type': 'ini_property',
                        'category': prop["category"],
                        'properties': prop.get("properties", [])
                    }
                })
                
            # Extract reference patterns (environment variables, includes, etc.)
            reference_patterns = self._extract_reference_patterns(ast_dict)
            for ref in reference_patterns:
                patterns.append({
                    'name': f'ini_reference_{ref["type"]}',
                    'content': ref["content"],
                    'pattern_type': PatternType.CONFIG_REFERENCE,
                    'language': self.language_id,
                    'confidence': 0.9,
                    'metadata': {
                        'type': 'ini_reference',
                        'reference_type': ref["type"],
                        'references': ref.get("references", [])
                    }
                })
                
            # Extract naming convention patterns
            naming_patterns = self._extract_naming_convention_patterns(ast_dict)
            for naming in naming_patterns:
                patterns.append({
                    'name': f'ini_naming_{naming["convention"]}',
                    'content': naming["content"],
                    'pattern_type': PatternType.NAMING_CONVENTION,
                    'language': self.language_id,
                    'confidence': 0.8,
                    'metadata': {
                        'type': 'naming_convention',
                        'convention': naming["convention"],
                        'examples': naming.get("examples", [])
                    }
                })
                
        except Exception as e:
            log(f"Error extracting INI patterns: {e}", level="error")
            
        return patterns
        
    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        sections = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'section':
                properties = []
                
                # Extract properties from this section
                for child in node.get('children', []):
                    if isinstance(child, dict) and child.get('type') == 'property':
                        properties.append({
                            'key': child.get('key', ''),
                            'value': child.get('value', '')
                        })
                
                section_name = node.get('name', '')
                if section_name:
                    sections.append({
                        'name': section_name,
                        'content': f"[{section_name}]\n" + "\n".join(f"{prop['key']} = {prop['value']}" for prop in properties[:3]),
                        'properties': properties
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return sections
        
    def _extract_property_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract common property patterns from the AST."""
        property_categories = {}
        
        def collect_properties(node, categories=None):
            if categories is None:
                categories = {}
                
            if isinstance(node, dict):
                # Check properties directly
                if node.get('type') == 'property':
                    key = node.get('key', '').lower()
                    value = node.get('value', '')
                    
                    # Categorize properties
                    if any(term in key for term in ['host', 'server', 'url', 'endpoint']):
                        category = 'connection'
                    elif any(term in key for term in ['user', 'password', 'auth', 'token', 'key', 'secret']):
                        category = 'authentication'
                    elif any(term in key for term in ['log', 'debug', 'verbose', 'trace']):
                        category = 'logging'
                    elif any(term in key for term in ['dir', 'path', 'file', 'folder']):
                        category = 'filesystem'
                    elif any(term in key for term in ['port', 'timeout', 'retry', 'max', 'min']):
                        category = 'connection_params'
                    elif any(term in key for term in ['enable', 'disable', 'toggle', 'feature']):
                        category = 'feature_flags'
                    else:
                        category = 'other'
                        
                    if category not in categories:
                        categories[category] = []
                        
                    categories[category].append({
                        'key': key,
                        'value': value
                    })
                
                # Process children recursively
                for child in node.get('children', []):
                    collect_properties(child, categories)
                    
            return categories
            
        # Collect properties by category
        property_categories = collect_properties(ast)
        
        # Create patterns for each category
        patterns = []
        for category, properties in property_categories.items():
            if properties:  # Only include non-empty categories
                patterns.append({
                    'category': category,
                    'content': "\n".join(f"{prop['key']} = {prop['value']}" for prop in properties[:3]),
                    'properties': properties
                })
                
        return patterns
        
    def _extract_reference_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract reference patterns from the AST."""
        references = {}
        
        def collect_references(node, refs=None):
            if refs is None:
                refs = {'environment': [], 'include': [], 'reference': []}
                
            if isinstance(node, dict):
                # Check for environment variable references
                if node.get('type') == 'property':
                    value = node.get('value', '')
                    key = node.get('key', '')
                    
                    # Check for environment variable pattern ${VAR} or $VAR
                    if re.search(r'\${[^}]+}', value) or re.search(r'\$[A-Za-z0-9_]+', value):
                        refs['environment'].append({
                            'key': key,
                            'value': value
                        })
                    
                    # Check for include directives
                    if key.lower() == 'include' or key.lower().startswith('include.'):
                        refs['include'].append({
                            'key': key,
                            'value': value
                        })
                        
                    # Check for internal references 
                    if re.search(r'%{[^}]+}', value) or re.search(r'@{[^}]+}', value):
                        refs['reference'].append({
                            'key': key,
                            'value': value
                        })
                
                # Process children recursively
                for child in node.get('children', []):
                    collect_references(child, refs)
                    
            return refs
            
        # Collect references by type
        references = collect_references(ast)
        
        # Create patterns for each reference type
        patterns = []
        for ref_type, refs in references.items():
            if refs:  # Only include non-empty reference types
                patterns.append({
                    'type': ref_type,
                    'content': "\n".join(f"{ref['key']} = {ref['value']}" for ref in refs[:3]),
                    'references': refs
                })
                
        return patterns
        
    def _extract_naming_convention_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract naming convention patterns from the AST."""
        # Collect all property keys and section names
        keys = []
        section_names = []
        
        def collect_names(node):
            if isinstance(node, dict):
                if node.get('type') == 'section':
                    section_name = node.get('name')
                    if section_name:
                        section_names.append(section_name)
                        
                elif node.get('type') == 'property':
                    key = node.get('key')
                    if key:
                        keys.append(key)
                
                # Process children recursively
                for child in node.get('children', []):
                    collect_names(child)
                    
        collect_names(ast)
        
        # Analyze naming conventions
        patterns = []
        
        # For keys
        key_conventions = self._detect_naming_conventions(keys)
        if key_conventions:
            patterns.append({
                'convention': f"property_keys_{key_conventions[0]}",
                'content': ", ".join(keys[:5]),
                'examples': keys[:5]
            })
            
        # For section names
        section_conventions = self._detect_naming_conventions(section_names)
        if section_conventions:
            patterns.append({
                'convention': f"section_names_{section_conventions[0]}",
                'content': ", ".join(section_names[:5]),
                'examples': section_names[:5]
            })
            
        return patterns
        
    def _detect_naming_conventions(self, names: List[str]) -> List[str]:
        """Detect naming conventions in a list of names."""
        if not names:
            return []
            
        conventions = []
        
        # Check for camelCase
        if any(re.match(r'^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name) for name in names):
            conventions.append("camelCase")
            
        # Check for snake_case
        if any(re.match(r'^[a-z][a-z0-9_]*$', name) and '_' in name for name in names):
            conventions.append("snake_case")
            
        # Check for kebab-case
        if any(re.match(r'^[a-z][a-z0-9-]*$', name) and '-' in name for name in names):
            conventions.append("kebab-case")
            
        # Check for PascalCase
        if any(re.match(r'^[A-Z][a-zA-Z0-9]*$', name) for name in names):
            conventions.append("PascalCase")
            
        # Check for UPPER_CASE
        if any(re.match(r'^[A-Z][A-Z0-9_]*$', name) and '_' in name for name in names):
            conventions.append("UPPER_CASE")
            
        # Check for lowercase
        if any(re.match(r'^[a-z][a-z0-9]*$', name) for name in names):
            conventions.append("lowercase")
            
        # Determine the most common convention
        if conventions:
            convention_counts = Counter(
                convention for name in names for convention in conventions 
                if self._matches_convention(name, convention)
            )
            
            if convention_counts:
                dominant_convention = convention_counts.most_common(1)[0][0]
                return [dominant_convention]
                
        return conventions
        
    def _matches_convention(self, name: str, convention: str) -> bool:
        """Check if a name matches a specific naming convention."""
        if convention == "camelCase":
            return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name))
        elif convention == "snake_case":
            return bool(re.match(r'^[a-z][a-z0-9_]*$', name) and '_' in name)
        elif convention == "kebab-case":
            return bool(re.match(r'^[a-z][a-z0-9-]*$', name) and '-' in name)
        elif convention == "PascalCase":
            return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))
        elif convention == "UPPER_CASE":
            return bool(re.match(r'^[A-Z][A-Z0-9_]*$', name) and '_' in name)
        elif convention == "lowercase":
            return bool(re.match(r'^[a-z][a-z0-9]*$', name))
        return False 