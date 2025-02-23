"""Custom parser for INI/Properties files."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.models import FileType
from parsers.query_patterns.ini import INI_PATTERNS, PatternCategory
from parsers.models import IniNode
from utils.logger import log
import re

class IniParser(BaseParser):
    """Parser for INI files."""
    
    def __init__(self, language_id: str = "ini", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG)
        self.patterns = {
            name: re.compile(pattern.pattern)
            for category in INI_PATTERNS.values()
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
    ) -> IniNode:
        """Create a standardized INI AST node."""
        return IniNode(
            type=node_type,
            start_point=start_point,
            end_point=end_point,
            children=[],
            **kwargs
        )

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
                    
                    # Check for semantic patterns
                    for pattern_name in ['environment', 'path']:
                        if semantic_match := self.patterns[pattern_name].match(line):
                            semantic_data = INI_PATTERNS[PatternCategory.SEMANTICS][pattern_name].extract(semantic_match)
                            node.metadata["semantics"] = semantic_data
                    
                    if current_section:
                        current_section.children.append(node)
                    else:
                        ast.children.append(node)
            
            # Add any remaining comments
            if current_comment_block:
                ast.metadata["trailing_comments"] = current_comment_block
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing INI content: {e}", level="error")
            return IniNode(
                type="ini_file",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__ 