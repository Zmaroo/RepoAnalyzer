"""
Custom parser for the Cobalt programming language.
"""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
from parsers.base_parser import BaseParser
from parsers.models import CobaltNode
from parsers.query_patterns.cobalt import COBALT_PATTERNS
from parsers.types import PatternCategory, FileType, ParserType
from utils.logger import log

class CobaltParser(BaseParser):
    """Parser for the Cobalt programming language."""
    
    def __init__(self, language_id: str = "cobalt", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CODE, parser_type=ParserType.CUSTOM)
        # Use the shared helper from BaseParser to compile the regex patterns.
        self.patterns = self._compile_patterns(COBALT_PATTERNS)
    
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
    ) -> CobaltNode:
        """Create a standardized Cobalt AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return CobaltNode(**node_dict)

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse Cobalt content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "module",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
            current_doc = []
            current_scope = [ast]
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                # Process docstrings.
                if doc_match := self.patterns['docstring'].match(line):
                    current_doc.append(doc_match.group(1))
                    continue
                    
                # Process regular comments.
                if comment_match := self.patterns['comment'].match(line):
                    current_scope[-1].children.append(
                        self._create_node(
                            "comment",
                            line_start,
                            line_end,
                            content=comment_match.group(1)
                        )
                    )
                    continue
                
                # Handle scope openings.
                if line.strip().endswith("{"):
                    # Look for declarations that open new scopes.
                    for pattern_name in ['function', 'class', 'namespace']:
                        if pattern_name in self.patterns and (match := self.patterns[pattern_name].match(line)):
                            node_data = COBALT_PATTERNS[PatternCategory.SYNTAX][pattern_name].extract(match)
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                None,  # End point to be set when scope closes.
                                **node_data
                            )
                            if current_doc:
                                node.metadata["documentation"] = "\n".join(current_doc)
                                current_doc = []
                            current_scope[-1].children.append(node)
                            current_scope.append(node)
                            break
                
                elif line.strip() == "}":
                    if len(current_scope) > 1:
                        current_scope[-1].end_point = line_end
                        current_scope.pop()
                    continue
                
                # Flush accumulated docstrings before declarations.
                if current_doc and not line.strip().startswith("///"):
                    current_scope[-1].children.append(
                        self._create_node(
                            "docstring",
                            [i - len(current_doc), 0],
                            [i - 1, len(current_doc[-1])],
                            content="\n".join(current_doc)
                        )
                    )
                    current_doc = []
                
                # Process other declarations.
                for pattern_name, pattern in self.patterns.items():
                    if pattern_name in ['docstring', 'comment', 'function', 'class', 'namespace']:
                        continue
                    
                    if match := pattern.match(line):
                        category = next(
                            cat for cat, patterns in COBALT_PATTERNS.items()
                            if pattern_name in patterns
                        )
                        node_data = COBALT_PATTERNS[category][pattern_name].extract(match)
                        node = self._create_node(
                            pattern_name,
                            line_start,
                            line_end,
                            **node_data
                        )
                        current_scope[-1].children.append(node)
                        break
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing Cobalt content: {e}", level="error")
            return CobaltNode(
                type="module",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__ 