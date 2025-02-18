"""
Query patterns for Markdown files with enhanced documentation support.
"""

MARKDOWN_PATTERNS = {
    "syntax": {
        "header": """
            (header
                level: (_) @syntax.header.level
                content: (_) @syntax.header.content) @syntax.header
        """,
        "code_block": """
            (code_block
                language: (_)? @syntax.code_block.language
                content: (_) @syntax.code_block.content) @syntax.code_block
        """,
        "emphasis": """
            (emphasis
                content: (_) @syntax.emphasis.content) @syntax.emphasis
        """
    },
    "structure": {
        "section": """
            (section
                header: (_)? @structure.section.header
                children: (_)* @structure.section.children) @structure.section
        """,
        "list": """
            (list
                items: (_)* @structure.list.items
                indent_level: (_) @structure.list.indent) @structure.list
        """,
        "table": """
            (table
                rows: (_)* @structure.table.rows) @structure.table
        """
    },
    "semantics": {
        "link": """
            (link
                text: (_) @semantics.link.text
                url: (_) @semantics.link.url) @semantics.link
        """,
        "reference": """
            (reference
                text: (_) @semantics.reference.text
                id: (_) @semantics.reference.id) @semantics.reference
        """,
        "definition": """
            (definition
                term: (_) @semantics.definition.term
                description: (_) @semantics.definition.description) @semantics.definition
        """
    },
    "documentation": {
        "metadata": """
            (metadata
                key: (_) @documentation.metadata.key
                value: (_) @documentation.metadata.value) @documentation.metadata
        """,
        "comment": """
            (comment
                content: (_) @documentation.comment.content) @documentation.comment
        """,
        "blockquote": """
            (blockquote
                content: (_) @documentation.blockquote.content) @documentation.blockquote
        """
    }
}

def extract_markdown_features(ast: dict) -> dict:
    """Extract features that align with pattern categories."""
    features = {
        "syntax": {
            "headers": [],
            "code_blocks": [],
            "emphasis": []
        },
        "structure": {
            "sections": [],
            "lists": [],
            "tables": []
        },
        "semantics": {
            "links": [],
            "references": [],
            "definitions": []
        },
        "documentation": {
            "metadata": {},
            "comments": [],
            "blockquotes": []
        }
    }
    
    def process_node(node: dict):
        """Process a node and extract its features."""
        if not isinstance(node, dict):
            return
            
        node_type = node.get("type")
        
        # Syntax features
        if node_type == "header":
            features["syntax"]["headers"].append({
                "level": node.get("level"),
                "content": node.get("content"),
                "line": node.get("line")
            })
        elif node_type == "code_block":
            features["syntax"]["code_blocks"].append({
                "language": node.get("language"),
                "content": node.get("content"),
                "start_line": node.get("start_line"),
                "end_line": node.get("end_line")
            })
        elif node_type == "emphasis":
            features["syntax"]["emphasis"].append({
                "content": node.get("content"),
                "line": node.get("line")
            })
            
        # Structure features
        elif node_type == "list":
            features["structure"]["lists"].append({
                "items": node.get("items", []),
                "indent_level": node.get("indent_level"),
                "start_line": node.get("start_line"),
                "end_line": node.get("end_line")
            })
            
        # Semantic features
        elif node_type == "link":
            features["semantics"]["links"].append({
                "text": node.get("text"),
                "url": node.get("url"),
                "line": node.get("line")
            })
            
        # Documentation features
        elif node_type == "blockquote":
            features["documentation"]["blockquotes"].append({
                "content": node.get("content"),
                "line": node.get("line")
            })
        
        # Process children recursively
        for child in node.get("children", []):
            process_node(child)
    
    process_node(ast)
    return features

# Helper functions for specific feature extraction
def extract_markdown_headings(ast: dict) -> list:
    """Extract all headings with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["syntax"]["headers"]

def extract_markdown_code_blocks(ast: dict) -> list:
    """Extract all code blocks with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["syntax"]["code_blocks"]

def extract_markdown_links(ast: dict) -> list:
    """Extract all links with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["semantics"]["links"]

def extract_markdown_lists(ast: dict) -> list:
    """Extract all lists with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["structure"]["lists"]

def extract_markdown_blockquotes(ast: dict) -> list:
    """Extract all blockquotes with enhanced metadata."""
    features = extract_markdown_features(ast)
    return features["documentation"]["blockquotes"]
