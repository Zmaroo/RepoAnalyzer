def parse_markdown_code(source_code: str) -> dict:
    """
    Parse a Markdown file to generate a richer AST.

    This parser detects headings, code blocks, and paragraphs.
    The resulting AST (with nodes for 'heading', 'code_block', and 'paragraph')
    along with extracted features is returned in a standardized dictionary format.
    
    Returns a dictionary with:
      - content: the original markdown source,
      - language: "markdown",
      - ast_data: the constructed AST,
      - ast_features: features extracted from the AST,
      - lines_of_code: total number of lines,
      - documentation: (empty by default),
      - complexity: a placeholder value (set to 1).
    """
    import re
    from parsers.common_parser_utils import extract_features_from_ast, build_parser_output

    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    current_paragraph = []
    in_code_block = False
    code_block_lines = []
    code_block_lang = ""
    
    def flush_paragraph():
        nonlocal current_paragraph
        if current_paragraph:
            paragraph_text = "\n".join(current_paragraph).strip()
            if paragraph_text:
                children.append({
                    "type": "paragraph",
                    "text": paragraph_text
                })
            current_paragraph = []
    
    # Regex patterns for detecting code blocks and headings.
    code_block_delim_re = re.compile(r'^```(\w+)?\s*$')
    heading_re = re.compile(r'^(#{1,6})\s+(.*)$')
    
    for line in lines:
        if in_code_block:
            # Check for end of code block.
            if line.strip().startswith("```"):
                children.append({
                    "type": "code_block",
                    "language": code_block_lang,
                    "text": "\n".join(code_block_lines)
                })
                in_code_block = False
                code_block_lines = []
                code_block_lang = ""
            else:
                code_block_lines.append(line)
        else:
            m_code = code_block_delim_re.match(line)
            if m_code:
                flush_paragraph()
                in_code_block = True
                code_block_lang = m_code.group(1) if m_code.group(1) else ""
                code_block_lines = []
                continue
            m_heading = heading_re.match(line)
            if m_heading:
                flush_paragraph()
                children.append({
                    "type": "heading",
                    "level": len(m_heading.group(1)),
                    "text": m_heading.group(2).strip()
                })
            elif line.strip() == "":
                flush_paragraph()
            else:
                current_paragraph.append(line)
    
    flush_paragraph()
    
    ast = {
        "type": "markdown",
        "children": children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }
    features = extract_features_from_ast(ast)
    return build_parser_output(
        source_code=source_code,
        language="markdown",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation="",
        complexity=1
    ) 