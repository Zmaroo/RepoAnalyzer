"""Custom parser for AsciiDoc with enhanced documentation features."""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
from parsers.base_parser import BaseParser
from parsers.models import AsciidocNode
from parsers.types import FileType, ParserType
from parsers.query_patterns.asciidoc import ASCIIDOC_PATTERNS
from utils.logger import log
import re

class AsciidocParser(BaseParser):
    """Parser for AsciiDoc documents."""
    
    def __init__(self, language_id: str = "asciidoc", file_type: Optional[FileType] = None):
        # Assume AsciiDoc files are documentation files by default
        from parsers.types import FileType
        if file_type is None:
            file_type = FileType.DOC
        # Set parser_type to CUSTOM so that the base class creates a CustomFeatureExtractor
        super().__init__(language_id, file_type, parser_type=ParserType.CUSTOM)
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

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse AsciiDoc source code and produce an AST."""
        try:
            ast = self._create_node("asciidoc_document", [0, 0], [0, 0], children=[])
            # Your custom parsing logic here...
            # For each line, create nodes as needed.
            lines = source_code.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("="):
                    # Example: treat lines starting with "=" as headers.
                    node = self._create_node("header", [i, 0], [i, len(line)], title=line.strip("="))
                    ast["children"].append(node)
            return ast
        except Exception as e:
            log(f"Error parsing AsciiDoc content: {e}", level="error")
            fallback = self._create_node("asciidoc_document", [0, 0], [0, 0], error=str(e), children=[])
            return fallback 