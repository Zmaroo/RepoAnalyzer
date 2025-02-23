"""Custom parser for YAML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, PatternCategory
from parsers.query_patterns.yaml import YAML_PATTERNS, PatternCategory
from parsers.models import YamlNode
from utils.logger import log
import yaml
import re

class YamlParser(BaseParser):
    """Parser for YAML files."""
    
    def __init__(self, language_id: str = "yaml", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.DATA)
        self.patterns = {
            name: re.compile(pattern.pattern)
            for category in YAML_PATTERNS.values()
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
    ) -> YamlNode:
        """Create a standardized YAML AST node."""
        return YamlNode(
            type=node_type,
            start_point=start_point,
            end_point=end_point,
            children=[],
            **kwargs
        )

    def _process_value(self, value: Any, path: List[str], start_point: List[int]) -> YamlNode:
        """Process a YAML value and build AST structure."""
        node = self._create_node(
            type(value).__name__,
            start_point,
            [start_point[0], start_point[1] + len(str(value))],
            path='.'.join(path)
        )
        
        if isinstance(value, dict):
            node.type = "mapping"
            for key, val in value.items():
                child = self._process_value(
                    val,
                    path + [str(key)],
                    [start_point[0], start_point[1] + 1]
                )
                child.key = key
                
                # Process semantic patterns
                for pattern_name in ['url', 'path', 'version']:
                    if pattern_match := self.patterns[pattern_name].match(str(val)):
                        child.metadata["semantics"] = YAML_PATTERNS[PatternCategory.SEMANTICS][pattern_name].extract(pattern_match)
                
                node.children.append(child)
                
        elif isinstance(value, list):
            node.type = "sequence"
            for i, item in enumerate(value):
                child = self._process_value(
                    item,
                    path + [f"[{i}]"],
                    [start_point[0], start_point[1] + 1]
                )
                node.children.append(child)
                
        else:
            node.type = "scalar"
            node.value = value
            
        return node

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse YAML content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
            current_comment_block = []
            
            # First pass: collect comments and document structure
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                # Process comments
                if comment_match := self.patterns['comment'].match(line):
                    current_comment_block.append(comment_match.group(1).strip())
                    continue
                
                # If we have a non-comment line and accumulated comments, process them
                if line.strip() and current_comment_block:
                    node = self._create_node(
                        "comment_block",
                        [i - len(current_comment_block), 0],
                        [i - 1, len(current_comment_block[-1])],
                        content="\n".join(current_comment_block)
                    )
                    ast.children.append(node)
                    current_comment_block = []

            # Second pass: parse YAML structure
            try:
                data = yaml.safe_load(source_code)
                if data is not None:
                    root_node = self._process_value(data, [], [0, 0])
                    ast.children.append(root_node)
                    
                    # Process documentation patterns
                    for pattern_name in ['description', 'metadata']:
                        if YAML_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].pattern(root_node.__dict__):
                            ast.metadata["documentation"] = YAML_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].extract(root_node.__dict__)
            
            except yaml.YAMLError as e:
                log(f"Error parsing YAML structure: {e}", level="error")
                ast.metadata["parse_error"] = str(e)

            # Add any remaining comments at the end
            if current_comment_block:
                ast.metadata["trailing_comments"] = current_comment_block

            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing YAML content: {e}", level="error")
            return YamlNode(
                type="document",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__