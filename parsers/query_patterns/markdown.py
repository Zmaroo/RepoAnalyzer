"""
Custom query patterns for Markdown files processed with our custom Markdown parser.

These functions traverse the custom Markdown AST (which is a plain dict)
and extract semantic elements such as headings, code blocks, and paragraphs.
"""

def extract_markdown_headings(ast: dict) -> list:
    """
    Extract all headings from the custom Markdown AST.
    
    Returns:
        A list of dictionaries with keys 'level' and 'text'.
    """
    headings = []
    for node in ast.get("children", []):
        if node.get("type") == "heading":
            headings.append({
                "level": node.get("level"),
                "text": node.get("text"),
            })
    return headings

def extract_markdown_code_blocks(ast: dict) -> list:
    """
    Extract all code blocks from the custom Markdown AST.
    
    Returns:
        A list of dictionaries with keys 'language' and 'text'.
    """
    code_blocks = []
    for node in ast.get("children", []):
        if node.get("type") == "code_block":
            code_blocks.append({
                "language": node.get("language"),
                "text": node.get("text"),
            })
    return code_blocks

def extract_markdown_paragraphs(ast: dict) -> list:
    """
    Extract all paragraphs from the custom Markdown AST.
    
    Returns:
        A list of paragraph texts.
    """
    paragraphs = []
    for node in ast.get("children", []):
        if node.get("type") == "paragraph":
            paragraphs.append(node.get("text"))
    return paragraphs

# Map semantic keys to extraction functions.
CUSTOM_MARKDOWN_PATTERNS = {
    "heading": extract_markdown_headings,
    "code_block": extract_markdown_code_blocks,
    "paragraph": extract_markdown_paragraphs,
}
