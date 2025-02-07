"""XML-specific Tree-sitter patterns."""

XML_PATTERNS = {
    # Document patterns
    "document": """
        [
          (document
            (prolog)? @document.prolog
            (element) @document.root
            (comment)* @document.comments) @document
        ]
    """,

    # Prolog patterns
    "prolog": """
        [
          (prolog
            (xml_decl)? @prolog.xml_decl
            (doctype)? @prolog.doctype
            (processing_instruction)* @prolog.instructions) @prolog
        ]
    """,

    # Element patterns
    "element": """
        [
          (element
            (start_tag
              name: (_) @element.name
              (attribute)* @element.attributes) @element.start
            (_)* @element.content
            (end_tag)? @element.end) @element,
          (empty_element
            name: (_) @element.empty.name
            (attribute)* @element.empty.attributes) @element.empty
        ]
    """,

    # Attribute patterns
    "attribute": """
        [
          (attribute
            name: (_) @attr.name
            value: (quoted_attribute_value) @attr.value) @attr
        ]
    """,

    # Content patterns
    "content": """
        [
          (text) @content.text,
          (cdata) @content.cdata,
          (comment) @content.comment,
          (processing_instruction) @content.instruction
        ]
    """,

    # DTD patterns
    "dtd": """
        [
          (doctype
            name: (_) @dtd.name
            external_id: (external_id)? @dtd.external_id
            (dtd_content)? @dtd.content) @dtd,
          (element_declaration
            name: (_) @dtd.element.name
            content: (_) @dtd.element.content) @dtd.element,
          (attlist_declaration
            name: (_) @dtd.attlist.name
            (attribute_declaration)* @dtd.attlist.attributes) @dtd.attlist
        ]
    """,

    # Processing instruction patterns
    "processing_instruction": """
        [
          (processing_instruction
            name: (_) @pi.name
            value: (_)? @pi.value) @pi
        ]
    """,

    # Namespace patterns
    "namespace": """
        [
          (attribute
            name: (qualified_name
              prefix: (_) @ns.prefix
              local_name: (_) @ns.local) @ns.name) @ns.attr,
          (element
            name: (qualified_name
              prefix: (_) @ns.element.prefix
              local_name: (_) @ns.element.local) @ns.element.name) @ns.element
        ]
    """,

    # Entity patterns
    "entity": """
        [
          (entity_reference) @entity.reference,
          (character_reference) @entity.char,
          (parameter_entity_reference) @entity.parameter
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment,
          (processing_instruction
            name: "doc") @doc.instruction
        ]
    """
} 