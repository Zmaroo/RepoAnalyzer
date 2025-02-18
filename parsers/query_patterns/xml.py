"""Query patterns for XML files with enhanced documentation support."""

XML_PATTERNS = {
    "syntax": {
        "element": """
            (element
                tag: (_) @syntax.element.tag
                namespace: (_)? @syntax.element.namespace
                attributes: (_)* @syntax.element.attributes
                children: (_)* @syntax.element.children) @syntax.element
        """,
        "attribute": """
            (attribute
                name: (_) @syntax.attribute.name
                value: (_) @syntax.attribute.value) @syntax.attribute
        """,
        "namespace": """
            (namespace
                prefix: (_)? @syntax.namespace.prefix
                uri: (_) @syntax.namespace.uri) @syntax.namespace
        """,
        "entity": """
            (entity
                name: (_) @syntax.entity.name
                value: (_) @syntax.entity.value) @syntax.entity
        """
    },
    "structure": {
        "hierarchy": """
            (element
                path: (_) @structure.hierarchy.path
                depth: (_) @structure.hierarchy.depth) @structure.hierarchy
        """,
        "reference": """
            (attribute
                [ends-with "ref"]
                value: (_) @structure.reference.value) @structure.reference
        """,
        "include": """
            (processing_instruction
                [contains "include"]
                content: (_) @structure.include.content) @structure.include
        """
    },
    "semantics": {
        "identifier": """
            [
                (attribute
                    name: ["id" "xml:id"]
                    value: (_) @semantics.identifier.value) @semantics.identifier
                
                (attribute
                    [ends-with "ref"]
                    value: (_) @semantics.identifier.reference) @semantics.identifier.ref
            ]
        """,
        "schema": """
            (processing_instruction
                [contains "schemaLocation"]
                content: (_) @semantics.schema.location) @semantics.schema
        """,
        "datatype": """
            (attribute
                name: ["type" "xsi:type"]
                value: (_) @semantics.datatype.value) @semantics.datatype
        """
    },
    "documentation": {
        "comment": """
            (comment
                content: (_) @documentation.comment.content) @documentation.comment
        """,
        "processing": """
            (processing_instruction
                content: (_) @documentation.processing.content) @documentation.processing
        """,
        "doctype": """
            (doctype
                content: (_) @documentation.doctype.content) @documentation.doctype
        """,
        "cdata": """
            (cdata
                content: (_) @documentation.cdata.content) @documentation.cdata
        """
    }
} 