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