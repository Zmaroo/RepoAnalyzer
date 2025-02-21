"""
Query patterns for Prisma schema files.
"""

PRISMA_PATTERNS = {
    "syntax": {
        "class": {
            "pattern": """
            [
                (model_declaration
                    name: (identifier) @syntax.class.model.name
                    properties: (property_declarations) @syntax.class.model.properties) @syntax.class.model,
                (enum_declaration
                    name: (identifier) @syntax.class.enum.name
                    values: (enum_value_declarations) @syntax.class.enum.values) @syntax.class.enum,
                (type_declaration
                    name: (identifier) @syntax.class.type.name
                    properties: (property_declarations) @syntax.class.type.properties) @syntax.class.type
            ]
            """
        },
        "field": {
            "pattern": """
            [
                (field_declaration
                    name: (identifier) @syntax.field.name
                    type: (field_type) @syntax.field.type
                    attributes: (attribute_list)? @syntax.field.attributes) @syntax.field.def,
                (block_attribute
                    name: (identifier) @syntax.field.block.name
                    properties: (property_declarations)? @syntax.field.block.properties) @syntax.field.block
            ]
            """
        }
    },
    "structure": {
        "namespace": {
            "pattern": """
            [
                (datasource_declaration
                    name: (identifier) @structure.namespace.datasource.name
                    properties: (property_declarations) @structure.namespace.datasource.props) @structure.namespace.datasource,
                (generator_declaration
                    name: (identifier) @structure.namespace.generator.name
                    properties: (property_declarations) @structure.namespace.generator.props) @structure.namespace.generator
            ]
            """
        },
        "attribute": {
            "pattern": """
            [
                (attribute
                    name: (identifier) @structure.attribute.name
                    arguments: (attribute_arguments)? @structure.attribute.args) @structure.attribute.def,
                (attribute_list
                    attributes: (attribute)*) @structure.attribute.list
            ]
            """
        }
    },
    "semantics": {
        "variable": {
            "pattern": """
            (property_declaration
                name: (identifier) @semantics.variable.name
                value: (_) @semantics.variable.value) @semantics.variable.def
            """
        },
        "type": {
            "pattern": """
            [
                (field_type) @semantics.type.field,
                (type_declaration
                    name: (identifier) @semantics.type.name) @semantics.type.def
            ]
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (doc_comment) @documentation.docstring
            ]
            """
        }
    }
} 