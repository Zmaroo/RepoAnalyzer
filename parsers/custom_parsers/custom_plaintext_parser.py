"""Custom parser for plaintext with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.models import PlaintextNode
from parsers.types import FileType, PatternCategory
from parsers.query_patterns.plaintext import PLAINTEXT_PATTERNS
from utils.logger import log

class PlaintextParser(BaseParser):
    """Parser for plaintext files."""
    
    def __init__(self, language_id: str = "plaintext", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.DOCUMENTATION)
        self.patterns = self._compile_patterns(PLAINTEXT_PATTERNS)

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
    ) -> PlaintextNode:
        """Create a standardized plaintext AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return PlaintextNode(**node_dict)

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse plaintext content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )

            current_paragraph = []
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                if not line.strip():
                    if current_paragraph:
                        node = self._create_node(
                            "paragraph",
                            [i - len(current_paragraph), 0],
                            [i - 1, len(current_paragraph[-1])],
                            content="\n".join(current_paragraph)
                        )
                        ast.children.append(node)
                        current_paragraph = []
                    continue

                matched = False
                for category in PLAINTEXT_PATTERNS.values():
                    for pattern_name, pattern_obj in category.items():
                        if match := self.patterns[pattern_name].match(line):
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                line_end,
                                **pattern_obj.extract(match)
                            )
                            ast.children.append(node)
                            matched = True
                            break
                    if matched:
                        break

                if not matched:
                    current_paragraph.append(line)

            if current_paragraph:
                node = self._create_node(
                    "paragraph",
                    [len(lines) - len(current_paragraph), 0],
                    [len(lines) - 1, len(current_paragraph[-1])],
                    content="\n".join(current_paragraph)
                )
                ast.children.append(node)

            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing plaintext content: {e}", level="error")
            return PlaintextNode(
                type="document",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__