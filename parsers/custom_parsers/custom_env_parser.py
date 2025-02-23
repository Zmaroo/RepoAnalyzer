"""
Custom .env file parser.

This parser processes .env files by extracting key=value pairs.
Comments (lines starting with #) are skipped (or can be used as documentation).
"""

from typing import Dict, List, Any, Optional, Tuple
from parsers.base_parser import BaseParser
from parsers.models import FileType
from parsers.pattern_processor import PatternCategory 
from parsers.query_patterns.env import ENV_PATTERNS
from parsers.models import EnvNode
from utils.logger import log
import re

class EnvParser(BaseParser):
    """Parser for .env files."""
    
    def __init__(self, language_id: str = "env", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG)
        self.patterns = {
            name: re.compile(pattern.pattern)
            for category in ENV_PATTERNS.values()
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
    ) -> EnvNode:
        """Create a standardized ENV AST node."""
        return EnvNode(
            type=node_type,
            start_point=start_point,
            end_point=end_point,
            children=[],
            **kwargs
        )

    def _process_value(self, value: str) -> Tuple[str, str]:
        """Process a value that might be quoted or multiline."""
        if value.startswith('"') or value.startswith("'"):
            quote = value[0]
            if value.endswith(quote) and len(value) > 1:
                return value[1:-1], "quoted"
        elif value.startswith('`') and value.endswith('`'):
            return value[1:-1], "multiline"
        return value, "raw"

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse env content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "env_file",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
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
                    ast.children.append(node)
                    continue
                
                # Process exports
                if export_match := self.patterns['export'].match(line):
                    name, raw_value = export_match.groups()
                    value, value_type = self._process_value(raw_value)
                    
                    node = self._create_node(
                        "export",
                        line_start,
                        line_end,
                        name=name,
                        value=value,
                        value_type=value_type
                    )
                    ast.children.append(node)
                    continue
                
                # Process variables
                if var_match := self.patterns['variable'].match(line):
                    name, raw_value = var_match.groups()
                    value, value_type = self._process_value(raw_value)
                    
                    node = self._create_node(
                        "variable",
                        line_start,
                        line_end,
                        name=name,
                        value=value,
                        value_type=value_type
                    )
                    ast.children.append(node)
                    
                    # Process semantic patterns
                    for pattern_name in ['url', 'path']:
                        if pattern_match := self.patterns[pattern_name].search(raw_value):
                            semantic_data = ENV_PATTERNS[PatternCategory.SEMANTICS][pattern_name].extract(pattern_match)
                            node.metadata["semantics"] = semantic_data
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing env content: {e}", level="error")
            return EnvNode(
                type="env_file",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__