"""Custom parser for YAML with enhanced documentation features."""

from typing import Dict, List, Any, Optional
import yaml
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.yaml import YAML_PATTERNS
from parsers.models import YamlNode
from utils.logger import log

class YamlParser(BaseParser):
    """Parser for YAML files."""
    
    def __init__(self, language_id: str = "yaml", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.DATA, parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(YAML_PATTERNS)
    
    def initialize(self) -> bool:
        self._initialized = True
        return True
    
    def _create_node(
        self, node_type: str, start_point: List[int],
        end_point: List[int], **kwargs
    ) -> YamlNode:
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return YamlNode(**node_dict)
    
    def _process_value(self, value: Any, path: List[str], start_point: List[int]) -> YamlNode:
        node = self._create_node(
            type(value).__name__, start_point,
            [start_point[0], start_point[1] + len(str(value))],
            path='.'.join(path)
        )
        if isinstance(value, dict):
            node.type = "mapping"
            for key, val in value.items():
                child = self._process_value(
                    val, path + [str(key)],
                    [start_point[0], start_point[1] + 1]
                )
                child.key = key
                for pattern_name in ['url', 'path', 'version']:
                    if pattern_match := self.patterns[pattern_name].match(str(val)):
                        child.metadata["semantics"] = YAML_PATTERNS[PatternCategory.SEMANTICS][pattern_name].extract(pattern_match)
                node.children.append(child)
        elif isinstance(value, list):
            node.type = "sequence"
            for i, item in enumerate(value):
                child = self._process_value(
                    item, path + [f"[{i}]"],
                    [start_point[0], start_point[1] + 1]
                )
                node.children.append(child)
        else:
            node.type = "scalar"
            node.value = value
        return node
    
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document", [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            current_comment_block = []
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                if comment_match := self.patterns['comment'].match(line):
                    current_comment_block.append(comment_match.group(1).strip())
                    continue
                if line.strip() and current_comment_block:
                    node = self._create_node(
                        "comment_block", [i - len(current_comment_block), 0],
                        [i - 1, len(current_comment_block[-1])],
                        content="\n".join(current_comment_block)
                    )
                    ast.children.append(node)
                    current_comment_block = []
            try:
                data = yaml.safe_load(source_code)
                if data is not None:
                    root_node = self._process_value(data, [], [0, 0])
                    ast.children.append(root_node)
                    for pattern_name in ['description', 'metadata']:
                        if YAML_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].pattern(root_node.__dict__):
                            ast.metadata["documentation"] = YAML_PATTERNS[PatternCategory.DOCUMENTATION][pattern_name].extract(root_node.__dict__)
            except yaml.YAMLError as e:
                log(f"Error parsing YAML structure: {e}", level="error")
                ast.metadata["parse_error"] = str(e)
            if current_comment_block:
                ast.metadata["trailing_comments"] = current_comment_block
            return ast.__dict__
        except Exception as e:
            log(f"Error parsing YAML content: {e}", level="error")
            return YamlNode(
                type="document", start_point=[0, 0], end_point=[0, 0],
                error=str(e), children=[]
            ).__dict__