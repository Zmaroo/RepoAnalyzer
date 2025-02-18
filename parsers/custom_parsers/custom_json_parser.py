"""Custom parser for JSON with enhanced documentation and structure features."""

from typing import Dict, List, Any
from parsers.common_parser_utils import build_parser_output
import json
import re
from utils.logger import log

def parse_json_code(source_code: str) -> dict:
    """
    Parse JSON content as structured code while preserving documentation features.
    
    Handles:
    - Document structure (objects, arrays)
    - Documentation (JSON5 comments, schema)
    - Configuration (key-value pairs)
    - References and definitions
    """
    features: Dict[str, Any] = {
        "syntax": {
            "objects": [],      # JSON objects
            "arrays": [],       # JSON arrays
            "values": [],       # Primitive values
            "types": []         # Value types
        },
        "structure": {
            "root": None,       # Root object/array
            "paths": [],        # JSON paths
            "references": []    # $ref references
        },
        "semantics": {
            "definitions": [], # Schema definitions
            "variables": [],   # Environment variables
            "patterns": []     # Regex patterns
        },
        "documentation": {
            "comments": [],    # JSON5 comments
            "schema": {},      # JSON Schema metadata
            "descriptions": [] # Property descriptions
        }
    }
    
    # Enhanced patterns for JSON parsing
    patterns = {
        'comment_single': re.compile(r'//\s*(.+)$', re.MULTILINE),
        'comment_multi': re.compile(r'/\*.*?\*/', re.DOTALL),
        'env_var': re.compile(r'\${([^}]+)}'),
        'json_ref': re.compile(r'"\$ref"\s*:\s*"([^"]+)"'),
        'schema_desc': re.compile(r'"description"\s*:\s*"([^"]+)"')
    }
    
    def process_value(value: Any, path: List[str], parent_key: str = None) -> Dict:
        """Process a JSON value and extract its features."""
        value_data = {
            "type": type(value).__name__,
            "path": '.'.join(path),
            "parent_key": parent_key
        }
        
        if isinstance(value, dict):
            value_data["type"] = "object"
            value_data["keys"] = list(value.keys())
            features["syntax"]["objects"].append(value_data)
            
            # Check for schema descriptions
            if "description" in value:
                features["documentation"]["descriptions"].append({
                    "path": value_data["path"],
                    "content": value["description"]
                })
            
            # Check for references
            if "$ref" in value:
                features["structure"]["references"].append({
                    "path": value_data["path"],
                    "target": value["$ref"]
                })
            
            # Process children
            for key, val in value.items():
                process_value(val, path + [key], key)
                
        elif isinstance(value, list):
            value_data["type"] = "array"
            value_data["length"] = len(value)
            features["syntax"]["arrays"].append(value_data)
            
            for i, item in enumerate(value):
                process_value(item, path + [f"[{i}]"])
                
        else:
            features["syntax"]["values"].append(value_data)
            features["syntax"]["types"].append({
                "path": value_data["path"],
                "type": value_data["type"]
            })
            
            # Check for environment variables
            if isinstance(value, str):
                env_vars = patterns['env_var'].findall(value)
                for var in env_vars:
                    features["semantics"]["variables"].append({
                        "path": value_data["path"],
                        "name": var
                    })
        
        return value_data
    
    try:
        # Extract comments (JSON5 style)
        lines = source_code.splitlines()
        
        # Process single-line comments
        for i, line in enumerate(lines):
            comment_match = patterns['comment_single'].search(line)
            if comment_match:
                features["documentation"]["comments"].append({
                    "content": comment_match.group(1),
                    "line": i + 1,
                    "type": "single"
                })
        
        # Process multi-line comments
        for match in patterns['comment_multi'].finditer(source_code):
            features["documentation"]["comments"].append({
                "content": match.group(0)[2:-2].strip(),
                "start": match.start(),
                "end": match.end(),
                "type": "multi"
            })
        
        # Remove comments for parsing
        clean_source = patterns['comment_single'].sub('', source_code)
        clean_source = patterns['comment_multi'].sub('', clean_source)
        
        # Parse JSON content
        try:
            data = json.loads(clean_source)
        except Exception as e:
            log(f"Error parsing JSON content: {e}", level="error")
            data = {}
        
        # Process schema information
        if isinstance(data, dict):
            if "$schema" in data:
                features["documentation"]["schema"]["schema"] = data["$schema"]
            if "title" in data:
                features["documentation"]["schema"]["title"] = data["title"]
            if "description" in data:
                features["documentation"]["schema"]["description"] = data["description"]
        
        # Build AST
        ast = {
            "type": "json_document",
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
        if features["documentation"]["schema"].get("description"):
            documentation = f"{features['documentation']['schema']['description']}\n{documentation}"
        
        # Calculate complexity
        complexity = (
            len(features["syntax"]["objects"]) +
            len(features["syntax"]["arrays"]) +
            len(features["structure"]["references"])
        )
        
        return build_parser_output(
            source_code=source_code,
            language="json",
            ast=ast,
            features=features,
            total_lines=len(lines),
            documentation=documentation,
            complexity=complexity
        )
        
    except Exception as e:
        log(f"Error in JSON parser: {e}", level="error")
        return build_parser_output(
            source_code=source_code,
            language="json",
            ast={"type": "error", "message": str(e)},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        ) 