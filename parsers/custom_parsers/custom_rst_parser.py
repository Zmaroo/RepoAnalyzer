"""Custom parser for reStructuredText with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.rst import RST_PATTERNS, PatternCategory
from utils.logger import log

@dataclass
class RstNode:
    """Base class for RST AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class RstParser(CustomParser):
    """Parser for reStructuredText files."""
    
    def __init__(self, language_id: str = "rst", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: pattern.pattern
            for category in RST_PATTERNS.values()
            for name, pattern in category.items()
        }

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> Dict:
        """Create a standardized AST node."""
        return {
            "type": node_type,
            "start_point": start_point,
            "end_point": end_point,
            "children": [],
            **kwargs
        }

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
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
            )

            current_section = None
            current_content = []
            section_stack = []

            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                # Process sections
                if self.patterns['section'].match(line) and current_content:
                    section_title = current_content[-1]
                    section_level = self._get_section_level(line[0])
                    
                    node = self._create_node(
                        "section",
                        [i - 1, 0],
                        line_end,
                        title=section_title,
                        level=section_level
                    )
                    
                    while section_stack and section_stack[-1]["level"] >= section_level:
                        section_stack.pop()
                    
                    if section_stack:
                        section_stack[-1]["children"].append(node)
                    else:
                        ast["children"].append(node)
                    
                    section_stack.append(node)
                    current_content = []
                    continue

                # Process other patterns
                matched = False
                for category in RST_PATTERNS.values():
                    for pattern_name, pattern in category.items():
                        if match := self.patterns[pattern_name].match(line):
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                line_end,
                                **pattern.extract(match)
                            )
                            
                            if section_stack:
                                section_stack[-1]["children"].append(node)
                            else:
                                ast["children"].append(node)
                                
                            matched = True
                            break
                    if matched:
                        break

                if not matched and line.strip():
                    current_content.append(line)

            return ast
            
        except Exception as e:
            log(f"Error parsing RST content: {e}", level="error")
            return {
                "type": "document",
                "error": str(e),
                "children": []
            } 