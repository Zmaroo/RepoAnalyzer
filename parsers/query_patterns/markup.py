"""Tree-sitter patterns for markup and configuration languages."""

HTML_PATTERNS = {
    "element": """
        [
          ; Regular elements
          (element
            (start_tag
              (tag_name) @element.name
              (attribute
                (attribute_name) @element.attr.name
                [
                  (attribute_value) @element.attr.value
                  (quoted_attribute_value
                    (attribute_value) @element.attr.value)
                  ])* @element.attrs)
            (_)* @element.children
            (end_tag)?) @element.def
          
          ; Self-closing elements
          (element
            (self_closing_tag
              (tag_name) @element.name
              (attribute
                (attribute_name) @element.attr.name
                [
                  (attribute_value) @element.attr.value
                  (quoted_attribute_value
                    (attribute_value) @element.attr.value)
                  ])* @element.attrs)) @element.self_closing
        ] @element.any
    """,
    "document": """
        (document
          (doctype)? @document.doctype
          (_)* @document.content) @document
    """,
    "comment": """
        (comment) @comment
    """,
    "attribute": """
        (attribute
          name: (attribute_name) @attribute.name
          value: (attribute_value)? @attribute.value) @attribute
    """
}

YAML_PATTERNS = {
    "mapping": """
        (block_mapping_pair
          key: (_) @mapping.key
          value: (_) @mapping.value) @mapping
    """,
    "sequence": """
        (block_sequence
          (block_sequence_item
            (_) @sequence.item)*) @sequence
    """,
    "anchor": """
        (anchor
          name: (anchor_name) @anchor.name) @anchor
    """,
    "alias": """
        (alias
          name: (alias_name) @alias.name) @alias
    """
}

TOML_PATTERNS = {
    "table": """
        (table
          header: (table_header) @table.header
          entries: (pair
            key: (_) @table.key
            value: (_) @table.value)*) @table
    """,
    "array": """
        (array
          value: (_)* @array.value) @array
    """,
    "inline_table": """
        (inline_table
          (pair
            key: (_) @table.key
            value: (_) @table.value)*) @inline_table
    """
}

DOCKERFILE_PATTERNS = {
    "instruction": """
        (instruction
          cmd: (_) @instruction.cmd
          value: (_)* @instruction.value) @instruction
    """,
    "from": """
        (from_instruction
          image: (_) @from.image
          tag: (_)? @from.tag
          platform: (_)? @from.platform) @from
    """,
    "run": """
        (run_instruction
          command: (_) @run.command) @run
    """
}

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
            url: (_) @link.url) @link,
          (image
            text: (_) @image.text
            url: (_) @image.url) @image
        ]
    """,
    "code_block": """
        [
          (fenced_code_block
            language: (_)? @code.language
            content: (_) @code.content) @code.block,
          (indented_code_block) @code.indented
        ]
    """,
    "blockquote": """
        (block_quote
          content: (_) @quote.content) @quote
    """
}

REQUIREMENTS_PATTERNS = {
    "requirement": """
        [
          (requirement
            name: (_) @requirement.name
            version: (_)? @requirement.version
            extras: (_)? @requirement.extras) @requirement,
          (requirement_options
            option: (_) @requirement.option)* @requirement.options
        ]
    """
}

GITIGNORE_PATTERNS = {
    "pattern": """
        [
          (pattern
            negated: (_)? @pattern.negated
            value: (_) @pattern.value) @pattern,
          (comment) @comment
        ]
    """
}

MAKEFILE_PATTERNS = {
    "rule": """
        [
          (rule
            targets: (_) @rule.targets
            prerequisites: (_)? @rule.prerequisites
            recipe: (_)* @rule.recipe) @rule,
          (variable_definition
            name: (_) @variable.name
            value: (_) @variable.value) @variable
        ]
    """
} 