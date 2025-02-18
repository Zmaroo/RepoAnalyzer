from typing import Dict, Any
from tree_sitter import Node, Tree
from utils.logger import log
from parsers.query_patterns import PATTERN_CATEGORIES, validate_pattern_category
from parsers.language_mapping import get_file_extension
from indexer.file_config import MARKUP_CLASSIFICATION

def extract_ast_features(node: Node, language: str, query_patterns: dict, source_bytes: bytes) -> Dict[str, Any]:
    """Extract features from AST using query patterns"""
    try:
        results = {category: {} for category in PATTERN_CATEGORIES.keys()}
        
        # Apply query patterns to extract features
        for category, pattern in query_patterns.items():
            query = language.query(pattern)
            captures = query.captures(node)
            for capture_node, capture_name in captures:
                text = source_bytes[capture_node.start_byte:capture_node.end_byte].decode('utf-8')
                category_dict = results[validate_pattern_category(capture_name.split('.')[0])]
                category_dict[capture_name] = text

        return results
        
    except Exception as e:
        log(f"Error extracting AST features: {e}", level="error")
        return {category: {} for category in PATTERN_CATEGORIES.keys()}

def extract_doc_features(node: Node, source_bytes: bytes) -> Dict[str, Any]:
    """Extract features from documentation-type markup files."""
    results = {category: {} for category in PATTERN_CATEGORIES.keys()}
    
    try:
        # Extract structural elements
        results['structure'] = {
            'headers': [],
            'lists': [],
            'code_blocks': [],
            'links': [],
            'tables': [],
            'blockquotes': []
        }
        
        # Extract semantic elements
        results['semantics'] = {
            'references': [],
            'definitions': [],
            'metadata': {}
        }
        
        # Process the node tree
        def process_node(node, depth=0):
            if not hasattr(node, 'type'):
                return
                
            node_text = source_bytes[node.start_byte:node.end_byte].decode('utf-8')
            
            # Map node types to our categories
            if node.type in {'heading', 'atx_heading', 'setext_heading'}:
                results['structure']['headers'].append({
                    'level': depth,
                    'content': node_text,
                    'position': (node.start_point, node.end_point)
                })
            elif node.type in {'list', 'bullet_list', 'ordered_list'}:
                results['structure']['lists'].append({
                    'type': node.type,
                    'content': node_text,
                    'position': (node.start_point, node.end_point)
                })
            elif node.type in {'code_block', 'fenced_code_block'}:
                results['structure']['code_blocks'].append({
                    'content': node_text,
                    'language': node.child_by_field_name('language'),
                    'position': (node.start_point, node.end_point)
                })
            elif node.type == 'link':
                results['structure']['links'].append({
                    'text': node_text,
                    'url': node.child_by_field_name('url'),
                    'position': (node.start_point, node.end_point)
                })
            
            # Process child nodes
            if hasattr(node, 'children'):
                for child in node.children:
                    process_node(child, depth + 1)
        
        process_node(node)
        return results
        
    except Exception as e:
        log(f"Error extracting doc features: {e}", level="error")
        return results 