"""Custom parser for JSON with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.json import JSON_PATTERNS, PatternCategory
from utils.logger import log
import json

@dataclass
class JsonNode:
    """Base class for JSON AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class JsonParser(CustomParser):
    """Parser for JSON files."""
    
    def __init__(self, language_id: str = "json", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: pattern.pattern
            for category in JSON_PATTERNS.values()
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

    def _process_node(self, value: Any, path: List[str], start_point: List[int]) -> Dict:
        """Process a JSON node and build AST structure."""
        node = self._create_node(
            type(value).__name__,
            start_point,
            [start_point[0], start_point[1] + len(str(value))],
            path='.'.join(path)
        )
        
        if isinstance(value, dict):
            node["type"] = "object"
            for key, val in value.items():
                child = self._process_node(
                    val,
                    path + [key],
                    [start_point[0], start_point[1] + len(str(key)) + 2]
                )
                child["key"] = key
                
                # Process semantic patterns
                for pattern_name in ['variable', 'schema_type']:
                    if JSON_PATTERNS[PatternCategory.SEMANTICS][pattern_name].pattern(child):
                        child["semantics"] = JSON_PATTERNS[PatternCategory.SEMANTICS][pattern_name].extract(child)
                
                node["children"].append(child)
                
        elif isinstance(value, list):
            node["type"] = "array"
            for i, item in enumerate(value):
                child = self._process_node(
                    item,
                    path + [f"[{i}]"],
                    [start_point[0], start_point[1] + 1]
                )
                node["children"].append(child)
                
        else:
            node["value"] = value
            
        return node

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse JSON content into AST structure."""
        try:
            data = json.loads(source_code)
            lines = source_code.splitlines()
            
            ast = self._create_node(
                "json_document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
            )
            
            ast["root"] = self._process_node(data, [], [0, 0])
            
            # Process documentation patterns
            for pattern_name in ['description', 'metadata']:
                if JSON_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].pattern(ast["root"]):
                    ast["documentation"] = JSON_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].extract(ast["root"])
            
            return ast
            
        except Exception as e:
            log(f"Error parsing JSON content: {e}", level="error")
            return {
                "type": "json_document",
                "error": str(e),
                "children": []
            } 