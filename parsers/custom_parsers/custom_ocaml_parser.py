"""
Custom OCaml parsers.

This module implements custom parsers for OCaml source files because we do not have
Tree-sitter language support for OCaml. Two kinds of source files are supported:
  - OCaml implementation files (.ml)
  - OCaml interface files (.mli)

Each parser extracts top-level declarations using regular expressions and converts the
source into a simplified custom AST with metadata (e.g. approximate byte positions,
document positions, and a top-level documentation comment if present).

NOTE:
  - This parser is intentionally a lightweight implementation meant for database ingestion
    and deep code base understanding. You can refine it over time to capture more detail.
  - Integrate this module with your main language parsing entry point so that when a file
    ends with .ml or .mli the corresponding function is called.

This module implements custom parsers for OCaml source files using a class-based structure.
Standalone parsing functions have been removed in favor of the classes below.
"""

import re
from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.query_patterns.ocaml import OCAML_PATTERNS
from parsers.query_patterns.ocaml_interface import OCAML_INTERFACE_PATTERNS
from parsers.models import OcamlNode
from parsers.types import FileType, ParserType, PatternCategory
from utils.logger import log

def compute_offset(lines, line_no, col):
    """
    Compute the byte offset for a given (line, col) pair.
    We assume that each line is terminated by a single newline character.
    """
    return sum(len(lines[i]) + 1 for i in range(line_no)) + col

class OcamlParser(BaseParser):
    """Parser for OCaml files."""
    
    def __init__(self, language_id: str = "ocaml", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CODE, parser_type=ParserType.CUSTOM)
        self.is_interface = language_id == "ocaml_interface"
        # Use the shared helper from BaseParser to compile regex patterns.
        patterns_source = OCAML_INTERFACE_PATTERNS if self.is_interface else OCAML_PATTERNS
        self.patterns = self._compile_patterns(patterns_source)
    
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
    ) -> OcamlNode:
        """Create a standardized OCaml AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return OcamlNode(**node_dict)

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse OCaml content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "ocaml_module" if not self.is_interface else "ocaml_interface",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )

            # Use the original patterns dictionary for extraction.
            patterns = OCAML_INTERFACE_PATTERNS if self.is_interface else OCAML_PATTERNS
            current_doc = []
            
            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]
                
                line = line.strip()
                if not line:
                    continue

                # Process documentation
                if doc_match := self.patterns['doc_comment'].match(line):
                    node = self._create_node(
                        "doc_comment",
                        line_start,
                        line_end,
                        **patterns["documentation"]["doc_comment"]["extract"](doc_match)
                    )
                    current_doc.append(node)
                    continue

                # Process declarations
                for category in ["syntax", "structure", "semantics"]:
                    for pattern_name, pattern_info in patterns[category].items():
                        if match := self.patterns[pattern_name].match(line):
                            node = self._create_node(
                                pattern_name,
                                line_start,
                                line_end,
                                **pattern_info["extract"](match)
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
            log(f"Error parsing OCaml content: {e}", level="error")
            return OcamlNode(
                type="ocaml_module" if not self.is_interface else "ocaml_interface",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__ 