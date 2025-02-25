"""Custom parser for JSON with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.query_patterns.json import JSON_PATTERNS
from parsers.types import PatternCategory, FileType, ParserType
from parsers.models import JsonNode
from utils.logger import log
import json

class JsonParser(BaseParser):
    """Parser for JSON files."""
    
    def __init__(self, language_id: str = "json", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.DATA, parser_type=ParserType.CUSTOM)
        # Compile regex patterns from JSON_PATTERNS using the shared helper.
        self.patterns = self._compile_patterns(JSON_PATTERNS)
    
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
    ) -> JsonNode:
        """Create a standardized JSON AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return JsonNode(**node_dict)

    def _process_node(self, value: Any, path: List[str], start_point: List[int]) -> JsonNode:
        """Process a JSON node and build AST structure."""
        node = self._create_node(
            type(value).__name__,
            start_point,
            [start_point[0], start_point[1] + len(str(value))],
            path='.'.join(path)
        )
        
        if isinstance(value, dict):
            node.type = "object"
            for key, val in value.items():
                child = self._process_node(
                    val,
                    path + [key],
                    [start_point[0], start_point[1] + len(str(key)) + 2]
                )
                child.key = key
                
                # Process semantic patterns.
                for pattern_name in ['variable', 'schema_type']:
                    if JSON_PATTERNS[PatternCategory.SEMANTICS][pattern_name].pattern(child.__dict__):
                        child.metadata["semantics"] = JSON_PATTERNS[PatternCategory.SEMANTICS][pattern_name].extract(child.__dict__)
                
                node.children.append(child)
                
        elif isinstance(value, list):
            node.type = "array"
            for i, item in enumerate(value):
                child = self._process_node(
                    item,
                    path + [f"[{i}]"],
                    [start_point[0], start_point[1] + 1]
                )
                node.children.append(child)
                
        else:
            node.value = value
            
        return node

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse JSON content into AST structure."""
        try:
            data = json.loads(source_code)
            lines = source_code.splitlines()
            
            ast = self._create_node(
                "json_document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
            root_node = self._process_node(data, [], [0, 0])
            ast.children.append(root_node)
            
            # Process documentation patterns.
            for pattern_name in ['description', 'metadata']:
                if JSON_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].pattern(root_node.__dict__):
                    ast.metadata["documentation"] = JSON_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].extract(root_node.__dict__)
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing JSON content: {e}", level="error")
            return JsonNode(
                type="json_document",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__ 