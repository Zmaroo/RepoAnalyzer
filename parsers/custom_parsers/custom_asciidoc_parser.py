"""Custom parser for AsciiDoc with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.models import ParserResult
from parsers.query_patterns.asciidoc import ASCIIDOC_PATTERNS
from utils.logger import log
import re

@dataclass
class AsciiDocNode:
    """Base class for AsciiDoc AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class AsciidocParser(CustomParser):
    """Parser for AsciiDoc documents."""
    
    def __init__(self, language_id: str = "asciidoc", classification=None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: re.compile(pattern.pattern)
            for category in ASCIIDOC_PATTERNS.values()
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
        """Parse AsciiDoc content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "asciidoc_document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                metadata={},
                sections=[],
                blocks=[]
            )
            
            current_section: Optional[Dict] = None
            in_block = False
            current_block = None
            header_processed = False
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]

                # Process document header
                if not header_processed and (header_match := self.patterns['header'].match(line)):
                    header_node = self._create_node(
                        "header",
                        line_start,
                        line_end,
                        title=header_match.group(1)
                    )
                    ast["children"].append(header_node)
                    ast["metadata"]["title"] = header_match.group(1)
                    header_processed = True
                    continue

                # Process sections
                if section_match := self.patterns['section'].match(line):
                    section = self._create_node(
                        "section",
                        line_start,
                        line_end,
                        level=len(section_match.group(1)),
                        title=section_match.group(2),
                        content=[]
                    )
                    ast["sections"].append(section)
                    ast["children"].append(section)
                    current_section = section
                    continue

                # Process blocks
                if block_match := self.patterns['block'].match(line):
                    if not in_block:
                        in_block = True
                        current_block = self._create_node(
                            "block",
                            line_start,
                            None,  # Will be set when block ends
                            content=[]
                        )
                    else:
                        if current_block:
                            current_block["end_point"] = line_end
                            ast["blocks"].append(current_block)
                            ast["children"].append(current_block)
                        in_block = False
                        current_block = None
                    continue

                # Add content to current block or section
                if in_block and current_block:
                    current_block["content"].append(line)
                elif current_section:
                    current_section["content"].append(line)

            return ast
            
        except Exception as e:
            log(f"Error parsing AsciiDoc content: {e}", level="error")
            return {
                "type": "asciidoc_document",
                "error": str(e),
                "children": []
            } 