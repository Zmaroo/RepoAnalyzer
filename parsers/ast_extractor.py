from tree_sitter import Query, QueryCursor

def extract_ast_features(root_node, language, query_pattern: str, source_code: bytes) -> dict:
    """
    Extracts specific AST features based on a Tree-sitter query pattern.

    Args:
        root_node: The root AST node returned from parse_code.
        language: The Tree-sitter Language object.
        query_pattern: The query pattern string defining the nodes to capture.
        source_code: The original source code as bytes.

    Returns:
        A dictionary mapping capture names to lists of text snippets.
    """
    query = Query(language, query_pattern)
    cursor = QueryCursor()
    # Execute the query on the root node.
    cursor.exec(query, root_node)

    features = {}
    # Iterate over all captures returned by the query.
    for node, capture_name in cursor.captures(root_node):
        snippet = source_code[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        features.setdefault(capture_name, []).append(snippet)
    return features 