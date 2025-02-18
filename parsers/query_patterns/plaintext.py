"""Enhanced query patterns for plain text files."""

PLAINTEXT_PATTERNS = {
    # Structure patterns
    "section": """
        (section
            header: (_)? @structure.section.header
            content: (_)+ @structure.section.content
        ) @structure.section
    """,
    
    "paragraph": """
        (paragraph
            content: (_)+ @structure.paragraph.content
        ) @structure.paragraph
    """,
    
    # Syntax patterns
    "list": """
        [
            (bullet_list
                items: (list_item)+ @syntax.list.bullet_items
            ) @syntax.list.bullet
            
            (numbered_list
                items: (list_item)+ @syntax.list.numbered_items
            ) @syntax.list.numbered
        ]
    """,
    
    "code_block": """
        (code_block
            language: (_)? @syntax.code_block.language
            content: (_)+ @syntax.code_block.content
        ) @syntax.code_block
    """,
    
    "table": """
        (table
            header: (table_row) @syntax.table.header
            rows: (table_row)+ @syntax.table.rows
        ) @syntax.table
    """,
    
    # Semantic patterns
    "reference": """
        [
            (url) @semantics.reference.url
            (email) @semantics.reference.email
            (path) @semantics.reference.path
        ]
    """,
    
    # Documentation patterns
    "header": """
        (header
            level: (_) @documentation.header.level
            content: (_) @documentation.header.content
        ) @documentation.header
    """,
    
    "metadata": """
        (metadata
            key: (_) @documentation.metadata.key
            value: (_) @documentation.metadata.value
        ) @documentation.metadata
    """
}

def extract_plaintext_features(node: dict) -> dict:
    """Extract features from plaintext AST nodes."""
    features = {
        "structure": {
            "sections": [],
            "paragraphs": []
        },
        "syntax": {
            "lists": [],
            "code_blocks": [],
            "tables": []
        },
        "semantics": {
            "references": []
        },
        "documentation": {
            "headers": [],
            "metadata": {}
        }
    }
    
    def process_node(node: dict):
        if not isinstance(node, dict):
            return
            
        node_type = node.get("type")
        if node_type == "section":
            features["structure"]["sections"].append(node)
        elif node_type == "paragraph":
            features["structure"]["paragraphs"].append(node)
        elif node_type in ("bullet_list", "numbered_list"):
            features["syntax"]["lists"].append(node)
        elif node_type == "code_block":
            features["syntax"]["code_blocks"].append(node)
        elif node_type == "table":
            features["syntax"]["tables"].append(node)
        elif node_type in ("url", "email", "path"):
            features["semantics"]["references"].append(node)
        elif node_type == "header":
            features["documentation"]["headers"].append(node)
        elif node_type == "metadata":
            features["documentation"]["metadata"][node["key"]] = node["value"]
        
        # Process children
        for child in node.get("children", []):
            process_node(child)
    
    process_node(node)
    return features 