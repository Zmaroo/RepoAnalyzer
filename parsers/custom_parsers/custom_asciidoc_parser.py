"""Custom parser for AsciiDoc with enhanced documentation features."""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
from parsers.base_parser import BaseParser
from parsers.models import AsciidocNode
from parsers.types import FileType
from parsers.query_patterns.asciidoc import ASCIIDOC_PATTERNS
from utils.logger import log
import re

class AsciidocParser(BaseParser):
    """Parser for AsciiDoc documents."""
    
    def __init__(self, language_id: str = "asciidoc", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.DOCUMENTATION)
        self.patterns = self._compile_patterns(ASCIIDOC_PATTERNS)
    
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
    ) -> AsciidocNode:
        """Create a standardized AsciiDoc AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return AsciidocNode(**node_dict)

    def parse(self, source_code: str) -> Dict[str, Any]:
        """Parse the source code into an AST."""
        try:
            ast = self._create_node("asciidoc_document", [0, 0], [0, 0], children=[])
            lines = source_code.splitlines()
            for i, line in enumerate(lines):
                if match := self.patterns.get("header", None) and self.patterns["header"].match(line):
                    node = self._create_node(
                        "header",
                        [i, 0],
                        [i, len(line)],
                        title=match.group(1)
                    )
                    ast["children"].append(node)
            return ast
        except Exception as e:
            log(f"Error parsing AsciiDoc content: {e}", level="error")
            fallback = self._create_node("asciidoc_document", [0, 0], [0, 0], error=str(e), children=[])
            return fallback 