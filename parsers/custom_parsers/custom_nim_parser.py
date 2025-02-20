"""Custom parser for Nim with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.nim import NIM_PATTERNS, PatternCategory
from utils.logger import log
import re

@dataclass
class NimNode:
    """Base class for Nim AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class NimParser(CustomParser):
    """Parser for Nim files."""
    
    def __init__(self, language_id: str = "nim", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.patterns = {
            name: re.compile(pattern.pattern)
            for category in NIM_PATTERNS.values()
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

    def _process_parameters(self, params_str: str) -> List[Dict]:
        """Process procedure parameters into parameter nodes."""
        if not params_str.strip():
            return []
        
        param_nodes = []
        params = [p.strip() for p in params_str.split(',')]
        for param in params:
            if match := self.patterns['parameter'].match(param):
                param_nodes.append(
                    NIM_PATTERNS[PatternCategory.SEMANTICS]['parameter'].extract(match)
                )
        return param_nodes

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse Nim content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "module",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
            )

            current_doc = []
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                line = line.strip()
                if not line:
                    continue

                # Process documentation
                if doc_match := self.patterns['docstring'].match(line):
                    node = self._create_node(
                        "docstring",
                        line_start,
                        line_end,
                        **NIM_PATTERNS[PatternCategory.DOCUMENTATION]['docstring'].extract(doc_match)
                    )
                    current_doc.append(node)
                    continue

                # Process procedures
                if proc_match := self.patterns['proc'].match(line):
                    node = self._create_node(
                        "proc",
                        line_start,
                        line_end,
                        **NIM_PATTERNS[PatternCategory.SYNTAX]['proc'].extract(proc_match)
                    )
                    node["parameters"] = self._process_parameters(node["parameters"])
                    if current_doc:
                        node["documentation"] = current_doc
                        current_doc = []
                    ast["children"].append(node)
                    continue

                # Process other patterns
                for pattern_name, category in [
                    ('type', PatternCategory.SYNTAX),
                    ('import', PatternCategory.STRUCTURE),
                    ('variable', PatternCategory.SEMANTICS)
                ]:
                    if match := self.patterns[pattern_name].match(line):
                        node = self._create_node(
                            pattern_name,
                            line_start,
                            line_end,
                            **NIM_PATTERNS[category][pattern_name].extract(match)
                        )
                        if current_doc:
                            node["documentation"] = current_doc
                            current_doc = []
                        ast["children"].append(node)
                        break

            # Add any remaining documentation
            if current_doc:
                ast["trailing_documentation"] = current_doc

            return ast
            
        except Exception as e:
            log(f"Error parsing Nim content: {e}", level="error")
            return {
                "type": "module",
                "error": str(e),
                "children": []
            }