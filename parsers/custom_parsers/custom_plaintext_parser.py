"""Custom parser for plaintext with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.plaintext import PLAINTEXT_PATTERNS, PatternCategory
from utils.logger import log

@dataclass
class PlaintextNode:
    """Base class for plaintext AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class PlaintextParser(CustomParser):
    """Parser for plaintext files."""
    
    def __init__(self, language_id: str = "plaintext", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: pattern.pattern
            for category in PLAINTEXT_PATTERNS.values()
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

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse plaintext content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
            )

            current_paragraph = []
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                line = line.strip()
                if not line:
                    if current_paragraph:
                        node = self._create_node(
                            "paragraph",
                            [i - len(current_paragraph), 0],
                            [i - 1, len(current_paragraph[-1])],
                            content="\n".join(current_paragraph)
                        )
                        ast["children"].append(node)
                        current_paragraph = []
                    continue

                # Process patterns
                matched = False
                for category in PLAINTEXT_PATTERNS.values():
                    for pattern_name, pattern in category.items():
                        if match := pattern.pattern(line):
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                line_end,
                                **pattern.extract(match)
                            )
                            ast["children"].append(node)
                            matched = True
                            break
                    if matched:
                        break

                if not matched:
                    current_paragraph.append(line)

            # Handle any remaining paragraph
            if current_paragraph:
                node = self._create_node(
                    "paragraph",
                    [len(lines) - len(current_paragraph), 0],
                    [len(lines) - 1, len(current_paragraph[-1])],
                    content="\n".join(current_paragraph)
                )
                ast["children"].append(node)

            return ast
            
        except Exception as e:
            log(f"Error parsing plaintext content: {e}", level="error")
            return {
                "type": "document",
                "error": str(e),
                "children": []
            }