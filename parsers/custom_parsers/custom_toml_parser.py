"""Custom parser for TOML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, PatternCategory
from parsers.query_patterns.toml import TOML_PATTERNS, PatternCategory
from parsers.models import TomlNode
from utils.logger import log
import tomli

class TomlParser(BaseParser):
    """Parser for TOML files."""
    
    def __init__(self, language_id: str = "toml", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG)
        self.patterns = {
            name: pattern.pattern
            for category in TOML_PATTERNS.values()
            for name, pattern in category.items()
        }

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
    ) -> TomlNode:
        """Create a standardized TOML AST node."""
        return TomlNode(
            type=node_type,
            start_point=start_point,
            end_point=end_point,
            children=[],
            **kwargs
        )

    def _process_value(self, value: Any, path: List[str], start_point: List[int]) -> TomlNode:
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
            value_data.type = "table"
            value_data.metadata["keys"] = list(value.keys())
            for key, val in value.items():
                child = self._process_value(
                    val,
                    path + [key],
                    [start_point[0], start_point[1] + len(key) + 1]
                )
                value_data.children.append(child)
                
        elif isinstance(value, list):
            value_data.type = "array"
            value_data.metadata["length"] = len(value)
            for i, item in enumerate(value):
                child = self._process_value(
                    item,
                    path + [f"[{i}]"],
                    [start_point[0], start_point[1] + i]
                )
                value_data.children.append(child)
        
        return value_data

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse TOML content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
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
                                node.metadata["comments"] = current_comments
                                current_comments = []
                            ast.children.append(node)
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
                ast.children.append(root_value)
            except Exception as e:
                log(f"Error parsing TOML content: {e}", level="error")
                return TomlNode(
                    type="document",
                    start_point=[0, 0],
                    end_point=[0, 0],
                    error=str(e),
                    children=[]
                ).__dict__

            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing TOML content: {e}", level="error")
            return TomlNode(
                type="document",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__ 