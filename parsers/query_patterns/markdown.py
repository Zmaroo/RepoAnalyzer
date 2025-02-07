MARKDOWN_PATTERNS = {
    "heading": """
        (atx_heading
          marker: (_) @heading.marker
          content: (_) @heading.content) @heading
    """,
    "list": """
        (list
          item: (list_item
            content: (_) @list.item.content)*) @list
    """,
    "link": """
        [
          (link
            text: (_) @link.text
            url: (_) @link.url) @link
          (image
            text: (_) @image.text
            url: (_) @image.url) @image
        ]
    """,
    "code_block": """
        [
          (fenced_code_block
            language: (_)? @code.language
            content: (_) @code.content) @code.block
          (indented_code_block) @code.indented
        ]
    """,
    "blockquote": """
        (block_quote
          content: (_) @quote.content) @quote
    """
}
