from typing import Dict, Any
from tree_sitter import Node, Tree
from utils.logger import log

def extract_ast_features(node: Node, language: Any, query_string: str, source_bytes: bytes) -> Dict[str, Any]:
    """
    Extract specific features from an AST using a Tree-sitter query.
    
    Args:
        node: The root AST node
        language: Tree-sitter language object
        query_string: The query pattern to match
        source_bytes: Original source code as bytes for accurate text extraction
    
    Returns:
        Dictionary of extracted features
    """
    try:
        query = language.query(query_string)
        captures = query.captures(node)
        
        results = {}
        for capture_node, capture_name in captures:
            # Extract text accurately using byte offsets
            start_byte = capture_node.start_byte
            end_byte = capture_node.end_byte
            text = source_bytes[start_byte:end_byte].decode('utf-8', errors='replace')
            
            # Organize captures by their names
            if '.' in capture_name:
                # Handle nested capture names (e.g., "function.name")
                parts = capture_name.split('.')
                current = results
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = text
            else:
                results[capture_name] = text
                
        return results
        
    except Exception as e:
        log(f"Error extracting AST features: {e}", level="error")
        return {} 