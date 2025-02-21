"""Custom parser for YAML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.yaml import YAML_PATTERNS
from utils.logger import log
import yaml

@dataclass
class YamlNode:
    """Base class for YAML AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class YamlParser(CustomParser):
    """Parser for YAML files."""
    
    def __init__(self, language_id: str = "yaml", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: pattern.pattern
            for category in YAML_PATTERNS.values()
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

    def parse(self, source_code: str) -> dict:
        """Parse YAML content with standardized feature extraction."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
            )

            # Process patterns first
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                for category in YAML_PATTERNS.values():
                    for pattern_name, pattern in category.items():
                        if match := pattern.pattern.match(line):
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                line_end,
                                **pattern.extract(match)
                            )
                            ast["children"].append(node)

            # Parse YAML structure
            try:
                data = yaml.safe_load(source_code)
                if data:
                    root_value = self._analyze_structure(data)
                    ast["children"].append(root_value)
            except yaml.YAMLError as e:
                log(f"Error parsing YAML structure: {e}", level="error")
                return {
                    "type": "document",
                    "error": str(e),
                    "children": []
                }

            return ast
            
        except Exception as e:
            log(f"Error parsing YAML content: {e}", level="error")
            return {
                "type": "document",
                "error": str(e),
                "children": []
            }

    def _analyze_structure(self, data: Any) -> Dict[str, Any]:
        """Analyze YAML structure for better feature extraction."""
        if isinstance(data, dict):
            return {
                "type": "mapping",
                "keys": list(data.keys()),
                "nested_types": {
                    k: self._analyze_structure(v)
                    for k, v in data.items()
                }
            }
        elif isinstance(data, list):
            return {
                "type": "sequence",
                "length": len(data),
                "item_types": [
                    self._analyze_structure(item)
                    for item in data[:10]  # Limit analysis to first 10 items
                ]
            }
        else:
            return {
                "type": "scalar",
                "value_type": type(data).__name__
            }