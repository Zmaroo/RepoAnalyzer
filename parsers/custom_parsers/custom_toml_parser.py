"""Custom parser for TOML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.toml import TOML_PATTERNS, PatternCategory
from utils.logger import log
import tomli

@dataclass
class TomlNode:
    """Base class for TOML AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class TomlParser(CustomParser):
    """Parser for TOML files."""
    
    def __init__(self, language_id: str = "toml", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: pattern.pattern
            for category in TOML_PATTERNS.values()
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

    def _process_value(self, value: Any, path: List[str], start_point: List[int]) -> Dict:
        """Process a TOML value and extract its features."""
        value_data = self._create_node(
            "value",
            start_point,
            [start_point[0], start_point[1] + len(str(value))],
            path='.'.join(path),
            value_type=type(value).__name__,
            value=value
        )
        
        if isinstance(value, dict):
            value_data["type"] = "table"
            value_data["keys"] = list(value.keys())
            for key, val in value.items():
                child = self._process_value(
                    val,
                    path + [key],
                    [start_point[0], start_point[1] + len(key) + 1]
                )
                value_data["children"].append(child)
                
        elif isinstance(value, list):
            value_data["type"] = "array"
            value_data["length"] = len(value)
            for i, item in enumerate(value):
                child = self._process_value(
                    item,
                    path + [f"[{i}]"],
                    [start_point[0], start_point[1] + i]
                )
                value_data["children"].append(child)
        
        return value_data

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse TOML content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
            )

            # Process comments and structure
            current_comments = []
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                # Process patterns
                matched = False
                for category in TOML_PATTERNS.values():
                    for pattern_name, pattern in category.items():
                        if match := self.patterns[pattern_name].match(line):
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                line_end,
                                **pattern.extract(match)
                            )
                            if current_comments:
                                node["comments"] = current_comments
                                current_comments = []
                            ast["children"].append(node)
                            matched = True
                            break
                    if matched:
                        break

                if not matched and line.strip():
                    current_comments.append(line)

            # Parse TOML content
            try:
                data = tomli.loads(source_code)
                root_value = self._process_value(data, [], [0, 0])
                ast["children"].append(root_value)
            except Exception as e:
                log(f"Error parsing TOML content: {e}", level="error")
                return {
                    "type": "document",
                    "error": str(e),
                    "children": []
                }

            return ast
            
        except Exception as e:
            log(f"Error parsing TOML content: {e}", level="error")
            return {
                "type": "document",
                "error": str(e),
                "children": []
            } 