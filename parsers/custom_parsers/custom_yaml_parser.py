"""Custom parser for YAML with enhanced documentation and configuration features."""

from typing import Dict, List, Any
from parsers.common_parser_utils import build_parser_output
import re
import yaml
from utils.logger import log

def parse_yaml_code(source_code: str) -> dict:
    """
    Parse YAML content as structured code while preserving documentation features.
    
    Handles both configuration and documentation use cases:
    - Configuration: Preserves structure and relationships
    - Documentation: Captures metadata and content organization
    - Comments: Maintains documentation within configuration
    """
    try:
        # Track document structure and features
        features: Dict[str, Any] = {
            "syntax": {
                "mappings": [],    # key-value pairs
                "sequences": [],   # lists/arrays
                "scalars": [],     # simple values
                "anchors": []      # YAML anchors and aliases
            },
            "structure": {
                "documents": [],   # multiple docs in single file
                "sections": [],    # top-level keys
                "includes": []     # external references
            },
            "semantics": {
                "definitions": [], # schema definitions
                "references": [],  # internal references
                "environment": []  # env var references
            },
            "documentation": {
                "comments": [],    # Regular comments
                "metadata": {},    # Document metadata
                "descriptions": [] # Key descriptions
            }
        }
        
        # Regex patterns for YAML elements
        patterns = {
            'comment': re.compile(r'^\s*#\s*(.+)$'),
            'key_value': re.compile(r'^\s*([^:]+):\s*(.*)$'),
            'list_item': re.compile(r'^\s*-\s+(.+)$'),
            'anchor': re.compile(r'&([^\s]+)\s'),
            'alias': re.compile(r'\*([^\s]+)'),
            'env_var': re.compile(r'\$\{([^}]+)\}'),
            'include': re.compile(r'!include\s+(.+)$')
        }
        
        def process_node(node: Any, path: List[str], line_number: int) -> Dict:
            """Process a YAML node and extract its features."""
            if isinstance(node, dict):
                return process_mapping(node, path, line_number)
            elif isinstance(node, list):
                return process_sequence(node, path, line_number)
            else:
                return process_scalar(node, path, line_number)
        
        def process_mapping(mapping: Dict, path: List[str], line_number: int) -> Dict:
            """Process a YAML mapping (dictionary)."""
            mapping_features = {
                "type": "mapping",
                "path": path,
                "line": line_number,
                "keys": [],
                "children": []
            }
            
            for key, value in mapping.items():
                key_path = path + [str(key)]
                
                # Check for documentation in key names
                if str(key).endswith('_doc') or str(key).endswith('_description'):
                    features["documentation"]["descriptions"].append({
                        "path": '.'.join(key_path[:-1]),
                        "content": str(value),
                        "line": line_number
                    })
                
                mapping_features["keys"].append({
                    "key": key,
                    "path": '.'.join(key_path),
                    "line": line_number
                })
                
                child_node = process_node(value, key_path, line_number)
                mapping_features["children"].append(child_node)
            
            features["syntax"]["mappings"].append(mapping_features)
            return mapping_features
        
        def process_sequence(sequence: List, path: List[str], line_number: int) -> Dict:
            """Process a YAML sequence (list)."""
            sequence_features = {
                "type": "sequence",
                "path": path,
                "line": line_number,
                "items": []
            }
            
            for i, item in enumerate(sequence):
                item_path = path + [str(i)]
                child_node = process_node(item, item_path, line_number)
                sequence_features["items"].append(child_node)
            
            features["syntax"]["sequences"].append(sequence_features)
            return sequence_features
        
        def process_scalar(value: Any, path: List[str], line_number: int) -> Dict:
            """Process a YAML scalar (simple value)."""
            scalar_feature = {
                "type": "scalar",
                "path": path,
                "value": str(value),
                "line": line_number
            }
            
            # Check for environment variables
            env_vars = patterns['env_var'].findall(str(value))
            if env_vars:
                features["semantics"]["environment"].extend([
                    {"name": var, "path": '.'.join(path), "line": line_number}
                    for var in env_vars
                ])
            
            features["syntax"]["scalars"].append(scalar_feature)
            return scalar_feature
        
        # Parse comments and structure first
        lines = source_code.splitlines()
        current_comment_block = []
        
        for i, line in enumerate(lines):
            comment_match = patterns['comment'].match(line)
            if comment_match:
                comment_content = comment_match.group(1)
                current_comment_block.append(comment_content)
                continue
            
            if current_comment_block:
                features["documentation"]["comments"].append({
                    "content": "\n".join(current_comment_block),
                    "line": i
                })
                current_comment_block = []
            
            # Check for includes
            include_match = patterns['include'].search(line)
            if include_match:
                features["structure"]["includes"].append({
                    "path": include_match.group(1),
                    "line": i + 1
                })
            
            # Check for anchors and aliases
            anchor_match = patterns['anchor'].search(line)
            if anchor_match:
                features["syntax"]["anchors"].append({
                    "name": anchor_match.group(1),
                    "line": i + 1
                })
        
        # Parse YAML content
        try:
            docs = list(yaml.safe_load_all(source_code))
        except Exception as e:
            log(f"Error parsing YAML content: {e}", level="error")
            docs = []
        
        # Process each document
        ast_children = []
        for doc_index, doc in enumerate(docs):
            doc_node = process_node(doc, [f"doc_{doc_index}"], 0)
            ast_children.append(doc_node)
            features["structure"]["documents"].append({
                "index": doc_index,
                "root": doc_node
            })
        
        # Build the AST
        ast = {
            "type": "yaml_file",
            "children": ast_children,
            "start_point": [0, 0],
            "end_point": [len(lines) - 1, len(lines[-1]) if lines else 0],
            "start_byte": 0,
            "end_byte": len(source_code)
        }
        
        return build_parser_output(
            source_code=source_code,
            language="yaml",
            ast=ast,
            features=features,
            total_lines=len(lines),
            documentation="\n".join(comment["content"] 
                                  for comment in features["documentation"]["comments"]),
            complexity=len(features["syntax"]["mappings"]) + 
                      len(features["syntax"]["sequences"])
        )
        
    except Exception as e:
        log(f"Error in YAML parser: {e}", level="error")
        return build_parser_output(
            source_code=source_code,
            language="yaml",
            ast={"type": "error", "message": str(e)},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        )