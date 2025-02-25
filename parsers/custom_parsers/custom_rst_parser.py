"""Custom parser for reStructuredText with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.models import RstNode
from parsers.types import FileType, PatternCategory
from parsers.query_patterns.rst import RST_PATTERNS
from utils.logger import log

class RstParser(BaseParser):
    """Parser for reStructuredText files."""
    
    def __init__(self, language_id: str = "rst", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.DOCUMENTATION)
        # Compile regex patterns using the shared helper.
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
        """Parse RST content into AST structure."""
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