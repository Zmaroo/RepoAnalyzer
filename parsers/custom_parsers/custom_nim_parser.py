"""Custom parser for Nim with enhanced documentation features."""

from typing import Dict, List, Any, Optional
import re
from parsers.base_parser import BaseParser
from parsers.models import NimNode
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.nim import NIM_PATTERNS
from utils.logger import log

class NimParser(BaseParser):
    """Parser for Nim files."""
    
    def __init__(self, language_id: str = "nim", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CODE, parser_type=ParserType.CUSTOM)
        self.patterns = self._compile_patterns(NIM_PATTERNS)
    
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
    ) -> NimNode:
        """Create a standardized Nim AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return NimNode(**node_dict)

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
                [len(lines) - 1, len(lines[-1]) if lines else 0]
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
                    node.metadata["parameters"] = self._process_parameters(node.metadata.get("parameters", ""))
                    if current_doc:
                        node.metadata["documentation"] = current_doc
                        current_doc = []
                    ast.children.append(node)
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
                            node.metadata["documentation"] = current_doc
                            current_doc = []
                        ast.children.append(node)
                        break

            # Add any remaining documentation
            if current_doc:
                ast.metadata["trailing_documentation"] = current_doc

            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing Nim content: {e}", level="error")
            return NimNode(
                type="module",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__