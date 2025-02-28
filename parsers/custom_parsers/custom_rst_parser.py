"""Custom parser for reStructuredText with enhanced documentation and pattern extraction features."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.models import RstNode, PatternType
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.rst import RST_PATTERNS
from utils.logger import log
import re
from collections import Counter

class RstParser(BaseParser):
    """Parser for reStructuredText files with enhanced pattern extraction capabilities."""
    
    def __init__(self, language_id: str = "rst", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.DOCUMENTATION, parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(RST_PATTERNS)
    
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
    ) -> RstNode:
        """Create a standardized RST AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return RstNode(**node_dict)

    def _get_section_level(self, char: str) -> int:
        """Determine section level based on underline character."""
        levels = {
            '=': 1, '-': 2, '~': 3,
            '^': 4, '"': 5, '+': 6
        }
        return levels.get(char, 99)

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse RST content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )

            current_content = []
            section_stack = []

            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                # Process section underlines when current content exists.
                if self.patterns.get('section') and self.patterns['section'].match(line) and current_content:
                    section_title = current_content[-1]
                    section_level = self._get_section_level(line[0])
                    
                    node = self._create_node(
                        "section",
                        [i - 1, 0],
                        line_end,
                        title=section_title,
                        level=section_level
                    )
                    
                    while section_stack and section_stack[-1].metadata.get('level', 0) >= section_level:
                        section_stack.pop()
                    
                    if section_stack:
                        section_stack[-1].children.append(node)
                    else:
                        ast.children.append(node)
                    
                    section_stack.append(node)
                    current_content = []
                    continue

                # Process other patterns.
                matched = False
                for category in RST_PATTERNS.values():
                    for pattern_name, pattern_obj in category.items():
                        if match := self.patterns[pattern_name].match(line):
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                line_end,
                                **pattern_obj.extract(match)
                            )
                            
                            if section_stack:
                                section_stack[-1].children.append(node)
                            else:
                                ast.children.append(node)
                                
                            matched = True
                            break
                    if matched:
                        break

                if not matched and line.strip():
                    current_content.append(line)

            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing RST content: {e}", level="error")
            return RstNode(
                type="document",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__ 
    
    def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract documentation patterns from reStructuredText files for repository learning.
        
        Args:
            source_code: The content of the RST file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        try:
            # Parse the source first to get a structured representation
            ast_dict = self._parse_source(source_code)
            
            # Extract section structure patterns
            section_patterns = self._extract_section_patterns(ast_dict)
            for section in section_patterns:
                patterns.append({
                    'name': f'rst_section_{section["name"]}',
                    'content': section["content"],
                    'pattern_type': PatternType.DOCUMENTATION_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.9,
                    'metadata': {
                        'type': 'rst_section',
                        'section_level': section.get("level", 1),
                        'section_count': section.get("count", 1)
                    }
                })
            
            # Extract directive patterns
            directive_patterns = self._extract_directive_patterns(ast_dict)
            for directive in directive_patterns:
                patterns.append({
                    'name': f'rst_directive_{directive["type"]}',
                    'content': directive["content"],
                    'pattern_type': PatternType.DOCUMENTATION_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.85,
                    'metadata': {
                        'type': 'rst_directive',
                        'directive_type': directive["type"],
                        'directives': directive.get("items", [])
                    }
                })
            
            # Extract role patterns
            role_patterns = self._extract_role_patterns(ast_dict)
            for role in role_patterns:
                patterns.append({
                    'name': f'rst_role_{role["type"]}',
                    'content': role["content"],
                    'pattern_type': PatternType.DOCUMENTATION_REFERENCE,
                    'language': self.language_id,
                    'confidence': 0.8,
                    'metadata': {
                        'type': 'rst_role',
                        'role_type': role["type"],
                        'roles': role.get("items", [])
                    }
                })
            
            # Extract structural patterns
            structure_patterns = self._extract_structure_patterns(ast_dict)
            for structure in structure_patterns:
                patterns.append({
                    'name': f'rst_structure_{structure["type"]}',
                    'content': structure["content"],
                    'pattern_type': PatternType.DOCUMENTATION_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.85,
                    'metadata': {
                        'type': 'document_structure',
                        'structure_type': structure["type"],
                        'count': structure.get("count", 1)
                    }
                })
                
        except Exception as e:
            log(f"Error extracting RST patterns: {e}", level="error")
            
        return patterns
        
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
        
    def _extract_role_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract role patterns from the AST."""
        # Count roles by type
        role_types = Counter()
        role_examples = {}
        
        def process_node(node):
            if isinstance(node, dict):
                if node.get('type') == 'role':
                    role_type = node.get('role_type', 'unknown')
                    role_content = node.get('content', '')
                    role_types[role_type] += 1
                    
                    if role_type not in role_examples:
                        role_examples[role_type] = []
                    
                    if role_content:
                        role_examples[role_type].append(role_content)
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)
        
        process_node(ast)
        
        # Create patterns for each role type
        patterns = []
        
        for role_type, count in role_types.items():
            patterns.append({
                'type': role_type,
                'content': f"Document uses {count} '{role_type}' roles",
                'items': role_examples.get(role_type, [])[:3]  # Include up to 3 examples
            })
        
        return patterns
        
    def _extract_structure_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract structural patterns from the AST."""
        # Count different node types
        type_counts = Counter()
        
        def process_node(node):
            if isinstance(node, dict):
                node_type = node.get('type')
                if node_type:
                    type_counts[node_type] += 1
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)
        
        process_node(ast)
        
        # Create patterns for significant structure elements
        patterns = []
        
        # Document overview pattern
        structure_elements = []
        for node_type, count in type_counts.most_common():
            if node_type not in ['document', 'section'] and count >= 2:
                structure_elements.append(f"{count} {node_type}{'s' if count > 1 else ''}")
        
        if structure_elements:
            patterns.append({
                'type': 'document_composition',
                'content': f"Document structure: {', '.join(structure_elements)}",
                'count': len(structure_elements)
            })
        
        # Look for specific structural patterns
        if type_counts.get('field', 0) >= 3:
            patterns.append({
                'type': 'field_list',
                'content': f"Document uses field lists ({type_counts['field']} fields)",
                'count': type_counts['field']
            })
            
        if type_counts.get('admonition', 0) >= 2:
            patterns.append({
                'type': 'admonitions',
                'content': f"Document uses admonitions ({type_counts['admonition']} instances)",
                'count': type_counts['admonition']
            })
            
        if type_counts.get('reference', 0) >= 3:
            patterns.append({
                'type': 'references',
                'content': f"Document uses many references ({type_counts['reference']} instances)",
                'count': type_counts['reference']
            })
            
        if type_counts.get('include', 0) >= 2:
            patterns.append({
                'type': 'modular_documentation',
                'content': f"Document uses modular structure with includes ({type_counts['include']} instances)",
                'count': type_counts['include']
            })
        
        return patterns 