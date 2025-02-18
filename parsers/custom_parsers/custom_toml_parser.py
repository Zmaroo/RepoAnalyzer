"""Custom parser for TOML with enhanced documentation and configuration features."""

from typing import Dict, List, Any
from parsers.common_parser_utils import build_parser_output
import re
import tomli
from utils.logger import log

def parse_toml_code(source_code: str) -> dict:
    """
    Parse TOML content as structured code while preserving documentation features.
    
    Handles:
    - Document structure (tables, arrays)
    - Documentation (comments, descriptions)
    - Configuration (key-value pairs)
    - Metadata and schema
    """
    features: Dict[str, Any] = {
        "syntax": {
            "tables": [],       # TOML tables
            "arrays": [],       # Array tables
            "values": [],       # Key-value pairs
            "inline": []        # Inline tables/arrays
        },
        "structure": {
            "sections": [],     # Top-level tables
            "subsections": [],  # Nested tables
            "references": []    # Cross-references
        },
        "semantics": {
            "definitions": [], # Value definitions
            "types": [],      # Data types
            "paths": []       # Dotted keys
        },
        "documentation": {
            "comments": [],    # TOML comments
            "metadata": {},    # Document metadata
            "descriptions": [] # Value descriptions
        }
    }
    
    # Enhanced patterns for TOML parsing
    patterns = {
        'comment': re.compile(r'#\s*(.+)$', re.MULTILINE),
        'table': re.compile(r'^\s*\[(.*?)\]\s*$', re.MULTILINE),
        'array_table': re.compile(r'^\s*\[\[(.*?)\]\]\s*$', re.MULTILINE),
        'key_value': re.compile(r'^\s*([\w.-]+)\s*=\s*(.+)$', re.MULTILINE),
        'doc_comment': re.compile(r'#\s*@\w+\s*(.+)$', re.MULTILINE)
    }
    
    def process_value(value: Any, path: List[str]) -> Dict:
        """Process a TOML value and extract its features."""
        value_data = {
            "type": "value",
            "path": '.'.join(path),
            "value_type": type(value).__name__
        }
        
        if isinstance(value, dict):
            value_data["type"] = "table"
            value_data["keys"] = list(value.keys())
            features["syntax"]["tables"].append(value_data)
            
            for key, val in value.items():
                process_value(val, path + [key])
                
        elif isinstance(value, list):
            value_data["type"] = "array"
            value_data["length"] = len(value)
            features["syntax"]["arrays"].append(value_data)
            
            for i, item in enumerate(value):
                process_value(item, path + [f"[{i}]"])
                
        else:
            features["syntax"]["values"].append(value_data)
            features["semantics"]["types"].append({
                "path": value_data["path"],
                "type": value_data["value_type"]
            })
        
        return value_data
    
    try:
        # Process comments first
        lines = source_code.splitlines()
        current_comments = []
        
        for i, line in enumerate(lines):
            # Handle comments
            comment_match = patterns['comment'].match(line)
            if comment_match:
                comment_content = comment_match.group(1)
                
                # Check for documentation comments
                doc_match = patterns['doc_comment'].match(line)
                if doc_match:
                    features["documentation"]["descriptions"].append({
                        "content": doc_match.group(1),
                        "line": i + 1
                    })
                else:
                    current_comments.append({
                        "content": comment_content,
                        "line": i + 1
                    })
                continue
            
            # Process accumulated comments
            if current_comments:
                features["documentation"]["comments"].extend(current_comments)
                current_comments = []
            
            # Track table headers
            table_match = patterns['table'].match(line)
            if table_match:
                table_name = table_match.group(1)
                features["structure"]["sections"].append({
                    "name": table_name,
                    "line": i + 1
                })
            
            # Track array tables
            array_match = patterns['array_table'].match(line)
            if array_match:
                array_name = array_match.group(1)
                features["structure"]["sections"].append({
                    "name": array_name,
                    "is_array": True,
                    "line": i + 1
                })
        
        # Parse TOML content
        try:
            data = tomli.loads(source_code)
        except Exception as e:
            log(f"Error parsing TOML content: {e}", level="error")
            data = {}
        
        # Process the parsed data
        ast = {
            "type": "toml_document",
            "root": process_value(data, []),
            "start_point": [0, 0],
            "end_point": [len(lines) - 1, len(lines[-1]) if lines else 0],
            "start_byte": 0,
            "end_byte": len(source_code)
        }
        
        # Extract documentation
        documentation = "\n".join(
            comment["content"] for comment in features["documentation"]["comments"]
        )
        
        # Calculate complexity
        complexity = (
            len(features["syntax"]["tables"]) +
            len(features["syntax"]["arrays"]) +
            len(features["structure"]["sections"])
        )
        
        return build_parser_output(
            source_code=source_code,
            language="toml",
            ast=ast,
            features=features,
            total_lines=len(lines),
            documentation=documentation,
            complexity=complexity
        )
        
    except Exception as e:
        log(f"Error in TOML parser: {e}", level="error")
        return build_parser_output(
            source_code=source_code,
            language="toml",
            ast={"type": "error", "message": str(e)},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        ) 