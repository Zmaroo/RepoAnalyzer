"""
Custom GraphQL parser.

This parser uses regexes to capture common GraphQL definitions such as type, interface,
enum, or schema definitions from a GraphQL file.
"""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, PatternCategory
from parsers.query_patterns.graphql import GRAPHQL_PATTERNS
from parsers.models import GraphQLNode
from utils.logger import log
import re

class GraphqlParser(BaseParser):
    """Parser for GraphQL schema files."""
    
    def __init__(self, language_id: str = "graphql", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CODE)
        self.patterns = {
            name: re.compile(pattern.pattern)
            for category in GRAPHQL_PATTERNS.values()
            for name, pattern in category.items()
        }
    
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
    ) -> GraphQLNode:
        """Create a standardized GraphQL AST node."""
        return GraphQLNode(
            type=node_type,
            start_point=start_point,
            end_point=end_point,
            children=[],
            **kwargs
        )

    def _process_arguments(self, args_str: str) -> List[Dict]:
        """Process field arguments into structured nodes."""
        if not args_str:
            return []
            
        arg_nodes = []
        args = [arg.strip() for arg in args_str.split(',')]
        
        for arg in args:
            if match := self.patterns['argument'].match(arg):
                arg_data = GRAPHQL_PATTERNS[PatternCategory.SEMANTICS]['argument'].extract(match)
                arg_data["line_number"] = match.string.count('\n', 0, match.start()) + 1
                arg_nodes.append(arg_data)
        return arg_nodes

    def _process_directives(self, line: str, line_number: int) -> List[Dict]:
        """Extract directives as structured nodes."""
        directives = []
        for match in self.patterns['directive'].finditer(line):
            directive = GRAPHQL_PATTERNS[PatternCategory.SEMANTICS]['directive'].extract(match)
            directive["line_number"] = line_number
            directive["arguments"] = self._process_arguments(directive["arguments"])
            directives.append(directive)
        return directives

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse GraphQL content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
            current_type = None
            current_interface = None
            current_description = None
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                line = line.strip()
                if not line:
                    continue
                
                # Process descriptions and comments
                if desc_match := self.patterns['description'].match(line):
                    node = self._create_node(
                        "description",
                        line_start,
                        line_end,
                        **GRAPHQL_PATTERNS[PatternCategory.DOCUMENTATION]['description'].extract(desc_match)
                    )
                    ast.children.append(node)
                    current_description = node
                    continue
                    
                if comment_match := self.patterns['comment'].match(line):
                    node = self._create_node(
                        "comment",
                        line_start,
                        line_end,
                        **GRAPHQL_PATTERNS[PatternCategory.DOCUMENTATION]['comment'].extract(comment_match)
                    )
                    ast.children.append(node)
                    continue
                
                # Process type definitions
                if type_match := self.patterns['type'].match(line):
                    node = self._create_node(
                        "type",
                        line_start,
                        line_end,
                        **GRAPHQL_PATTERNS[PatternCategory.SYNTAX]['type'].extract(type_match)
                    )
                    if current_description:
                        node.metadata["description"] = current_description
                        current_description = None
                    ast.children.append(node)
                    current_type = node
                    continue
                
                # Process interfaces
                if interface_match := self.patterns['interface'].match(line):
                    node = self._create_node(
                        "interface",
                        line_start,
                        line_end,
                        **GRAPHQL_PATTERNS[PatternCategory.STRUCTURE]['interface'].extract(interface_match)
                    )
                    if current_description:
                        node.metadata["description"] = current_description
                        current_description = None
                    ast.children.append(node)
                    current_interface = node
                    continue
                
                # Process fields
                if field_match := self.patterns['field'].match(line):
                    if not (current_type or current_interface):
                        continue
                        
                    field_data = GRAPHQL_PATTERNS[PatternCategory.SYNTAX]['field'].extract(field_match)
                    field_data["arguments"] = self._process_arguments(field_data["arguments"])
                    field_data["directives"] = self._process_directives(line, i + 1)
                    
                    node = self._create_node(
                        "field",
                        line_start,
                        line_end,
                        **field_data
                    )
                    
                    if current_type:
                        current_type.children.append(node)
                    else:
                        current_interface.children.append(node)
                    continue
                
                # Process fragments
                if fragment_match := self.patterns['fragment'].match(line):
                    node = self._create_node(
                        "fragment",
                        line_start,
                        line_end,
                        **GRAPHQL_PATTERNS[PatternCategory.STRUCTURE]['fragment'].extract(fragment_match)
                    )
                    ast.children.append(node)
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing GraphQL content: {e}", level="error")
            return GraphQLNode(
                type="document",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__