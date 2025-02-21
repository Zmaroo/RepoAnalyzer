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
from dataclasses import dataclass
from parsers.base_parser import CustomParser
from parsers.file_classification import FileClassification
from parsers.query_patterns.ocaml import OCAML_PATTERNS
from parsers.query_patterns.ocaml_interface import OCAML_INTERFACE_PATTERNS
from utils.logger import log

def compute_offset(lines, line_no, col):
    """
    Compute the byte offset for a given (line, col) pair.
    We assume that each line is terminated by a single newline character.
    """
    return sum(len(lines[i]) + 1 for i in range(line_no)) + col

# Define regex patterns for .ml files.
ML_PATTERNS = {
    "let_binding": re.compile(r'^\s*(let(?:\s+rec)?\s+[a-zA-Z0-9_\'-]+)'),
    "type_definition": re.compile(r'^\s*type\s+([a-zA-Z0-9_\'-]+)'),
    "module_declaration": re.compile(r'^\s*module\s+([A-Z][a-zA-Z0-9_\'-]*)'),
    "open_statement": re.compile(r'^\s*open\s+([A-Z][a-zA-Z0-9_.]*)'),
    "exception_declaration": re.compile(r'^\s*exception\s+([A-Z][a-zA-Z0-9_\'-]*)')
}

# Define regex patterns for .mli files.
MLI_PATTERNS = {
    "val_declaration": re.compile(r'^\s*val\s+([a-zA-Z0-9_\'-]+)'),
    "type_definition": re.compile(r'^\s*type\s+([a-zA-Z0-9_\'-]+)'),
    "module_declaration": re.compile(r'^\s*module\s+([A-Z][a-zA-Z0-9_\'-]*)')
}

@dataclass
class OcamlNode:
    """Base class for OCaml AST nodes."""
    type: str
    start_point: List[int]
    end_point: List[int]
    children: List[Any]

class OcamlParser(CustomParser):
    """Parser for OCaml files."""
    
    def __init__(self, language_id: str = "ocaml", classification: Optional[FileClassification] = None):
        super().__init__(language_id, classification)
        self.is_interface = language_id == "ocaml_interface"
        self.patterns = {
            name: re.compile(pattern_info["pattern"])
            for category in (OCAML_INTERFACE_PATTERNS if self.is_interface else OCAML_PATTERNS).values()
            for name, pattern_info in category.items()
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

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse OCaml content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "ocaml_module" if not self.is_interface else "ocaml_interface",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0],
                children=[]
            )

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
                                node["documentation"] = current_doc
                                current_doc = []
                            ast["children"].append(node)
                            break

            # Add any remaining documentation
            if current_doc:
                ast["trailing_documentation"] = current_doc

            return ast
            
        except Exception as e:
            log(f"Error parsing OCaml content: {e}", level="error")
            return {
                "type": "ocaml_module" if not self.is_interface else "ocaml_interface",
                "error": str(e),
                "children": []
            }

class OCamlmlParser(CustomParser):
    def parse(self, source_code: str) -> dict:
        """
        Parse OCaml implementation files (.ml) and generate a structured AST.
        """
        lines = source_code.splitlines()
        total_lines = len(lines)
        children = []
        # Insert OCaml .ml parsing logic here.
        
        ast = {"type": "ocaml_module", "children": children}
        features = {
            "documentation": {},
            "syntax": {},
            "structure": {}
        }
        documentation = "\n".join(
            node["content"] for node in children if node.get("type") == "documentation"
        )
        complexity = 1  # Placeholder; compute based on your parsing details.
        
        return {
            "type": "ocaml_module",
            "ast": ast,
            "features": features,
            "total_lines": total_lines,
            "documentation": documentation,
            "complexity": complexity
        }

class OCamlmliParser(CustomParser):
    def parse(self, source_code: str) -> dict:
        """
        Parse OCaml interface files (.mli) and generate a structured AST.
        """
        lines = source_code.splitlines()
        total_lines = len(lines)
        children = []
        # Insert OCaml .mli parsing logic here.
        
        ast = {"type": "ocaml_interface", "children": children}
        features = {
            "documentation": {},
            "syntax": {},
            "structure": {}
        }
        documentation = "Extracted OCaml interface documentation"
        complexity = 1  # Placeholder; compute as needed.
        
        return {
            "type": "ocaml_interface",
            "ast": ast,
            "features": features,
            "total_lines": total_lines,
            "documentation": documentation,
            "complexity": complexity
        } 