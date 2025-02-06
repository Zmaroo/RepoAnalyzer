"""TypeScript-specific Tree-sitter patterns."""

TS_PATTERNS = {
    "interface": """
        (interface_declaration
          name: (type_identifier) @interface.name
          extends_clause: (extends_type_clause
            types: (type_list
              (type_identifier) @interface.extends)*
          )? @interface.extends
          body: (object_type [
            (property_signature
              name: (property_identifier) @interface.property.name
              type: (type_annotation
                (type_identifier) @interface.property.type)?)
            (method_signature
              name: (property_identifier) @interface.method.name
              parameters: (formal_parameters) @interface.method.params
              type: (type_annotation)? @interface.method.return)?
          ]*) @interface.body) @interface.def
    """,
    "type": """
        [
          ; Type alias
          (type_alias_declaration
            name: (type_identifier) @type.name
            value: (_) @type.value) @type.def
            
          ; Union type
          (union_type
            types: (type_list) @type.union.types) @type.union
            
          ; Intersection type
          (intersection_type
            types: (type_list) @type.intersection.types) @type.intersection
            
          ; Generic type
          (generic_type
            name: (type_identifier) @type.generic.name
            arguments: (type_arguments
              (type_identifier) @type.generic.arg)*) @type.generic
        ]
    """,
    "enum": """
        (enum_declaration
          name: (identifier) @enum.name
          body: (enum_body
            (enum_member
              name: (property_identifier) @enum.member.name
              value: (_)? @enum.member.value)*) @enum.body) @enum.def
    """,
    "decorator": """
        (decorator
          name: [
            (identifier) @decorator.name
            (call_expression
              function: (identifier) @decorator.name
              arguments: (arguments) @decorator.args)
          ]) @decorator
    """
} 