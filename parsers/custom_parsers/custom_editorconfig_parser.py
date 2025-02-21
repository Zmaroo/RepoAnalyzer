"""
Custom EditorConfig parser.

This module implements a lightweight parser for EditorConfig files.
It extracts section headers (e.g. [*] or [*.py]) and
key-value property lines beneath each section.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.editorconfig import EDITORCONFIG_PATTERNS
from utils.logger import log
import re

@dataclass
class EditorconfigNode:
    """Base class for EditorConfig AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class EditorconfigParser(CustomParser):
    """Parser for EditorConfig files."""
    
    def __init__(self, language_id: str = "editorconfig", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: re.compile(pattern.pattern)
            for category in EDITORCONFIG_PATTERNS.values()
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
        """Parse EditorConfig content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "editorconfig",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
            )
            
            current_section = None
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Process comments
                if comment_match := self.patterns['comment'].match(line):
                    node = self._create_node(
                        "comment",
                        line_start,
                        line_end,
                        content=comment_match.group(1).strip()
                    )
                    if current_section:
                        current_section["children"].append(node)
                    else:
                        ast["children"].append(node)
                    continue
                
                # Process sections
                if section_match := self.patterns['section'].match(line):
                    current_section = self._create_node(
                        "section",
                        line_start,
                        line_end,
                        glob=section_match.group(1).strip(),
                        properties=[]
                    )
                    ast["children"].append(current_section)
                    continue
                
                # Process properties
                if current_section and (property_match := self.patterns['property'].match(line)):
                    node = self._create_node(
                        "property",
                        line_start,
                        line_end,
                        key=property_match.group(1).strip(),
                        value=property_match.group(2).strip()
                    )
                    current_section["properties"].append(node)
                    current_section["children"].append(node)
                    continue
                
                # Process semantic patterns
                for pattern_name, pattern in self.patterns.items():
                    if pattern_name in ['comment', 'section', 'property']:
                        continue
                    
                    if match := pattern.match(line):
                        category = next(
                            cat for cat, patterns in EDITORCONFIG_PATTERNS.items()
                            if pattern_name in patterns
                        )
                        node_data = EDITORCONFIG_PATTERNS[category][pattern_name].extract(match)
                        node = self._create_node(
                            pattern_name,
                            line_start,
                            line_end,
                            **node_data
                        )
                        if current_section:
                            current_section["children"].append(node)
                        else:
                            ast["children"].append(node)
                        break
            
            return ast
            
        except Exception as e:
            log(f"Error parsing EditorConfig content: {e}", level="error")
            return {
                "type": "editorconfig",
                "error": str(e),
                "children": []
            }