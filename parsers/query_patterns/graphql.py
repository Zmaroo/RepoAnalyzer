"""GraphQL-specific Tree-sitter patterns."""

GRAPHQL_PATTERNS = {
    # Document patterns
    "document": """
        [
          (document
            (definition)* @document.definitions) @document
        ]
    """,

    # Operation patterns
    "operation": """
        [
          (operation_definition
            type: (operation_type) @operation.type
            name: (name)? @operation.name
            variables: (variable_definitions)? @operation.vars
            directives: (directives)? @operation.directives
            selections: (selection_set) @operation.selections) @operation
        ]
    """,

    # Fragment patterns
    "fragment": """
        [
          (fragment_definition
            name: (fragment_name) @fragment.name
            type_condition: (type_condition) @fragment.type
            directives: (directives)? @fragment.directives
            selections: (selection_set) @fragment.selections) @fragment.def,
          (fragment_spread
            name: (fragment_name) @fragment.spread.name
            directives: (directives)? @fragment.spread.directives) @fragment.spread,
          (inline_fragment
            type_condition: (type_condition)? @fragment.inline.type
            directives: (directives)? @fragment.inline.directives
            selections: (selection_set) @fragment.inline.selections) @fragment.inline
        ]
    """,

    # Type definition patterns
    "type_definition": """
        [
          (object_type_definition
            description: (description)? @type.object.desc
            name: (name) @type.object.name
            interfaces: (implements_interfaces)? @type.object.interfaces
            directives: (directives)? @type.object.directives
            fields: (fields_definition) @type.object.fields) @type.object,
          (interface_type_definition
            description: (description)? @type.interface.desc
            name: (name) @type.interface.name
            directives: (directives)? @type.interface.directives
            fields: (fields_definition) @type.interface.fields) @type.interface,
          (enum_type_definition
            description: (description)? @type.enum.desc
            name: (name) @type.enum.name
            directives: (directives)? @type.enum.directives
            values: (enum_values_definition) @type.enum.values) @type.enum,
          (scalar_type_definition
            description: (description)? @type.scalar.desc
            name: (name) @type.scalar.name
            directives: (directives)? @type.scalar.directives) @type.scalar
        ]
    """,

    # Field patterns
    "field": """
        [
          (field
            alias: (alias)? @field.alias
            name: (name) @field.name
            arguments: (arguments)? @field.args
            directives: (directives)? @field.directives
            selections: (selection_set)? @field.selections) @field
        ]
    """,

    # Input patterns
    "input": """
        [
          (input_object_type_definition
            description: (description)? @input.desc
            name: (name) @input.name
            directives: (directives)? @input.directives
            fields: (input_fields_definition) @input.fields) @input.def,
          (input_value_definition
            description: (description)? @input.value.desc
            name: (name) @input.value.name
            type: (type) @input.value.type
            default: (default_value)? @input.value.default
            directives: (directives)? @input.value.directives) @input.value
        ]
    """,

    # Directive patterns
    "directive": """
        [
          (directive_definition
            description: (description)? @directive.desc
            name: (name) @directive.name
            arguments: (arguments_definition)? @directive.args
            locations: (directive_locations) @directive.locations) @directive.def,
          (directive
            name: (name) @directive.use.name
            arguments: (arguments)? @directive.use.args) @directive.use
        ]
    """,

    # Schema patterns
    "schema": """
        [
          (schema_definition
            directives: (directives)? @schema.directives
            operations: (root_operation_type_definition)* @schema.operations) @schema,
          (schema_extension
            directives: (directives)? @schema.ext.directives
            operations: (root_operation_type_definition)* @schema.ext.operations) @schema.ext
        ]
    """,

    # Value patterns
    "value": """
        [
          (int_value) @value.int,
          (float_value) @value.float,
          (string_value) @value.string,
          (boolean_value) @value.boolean,
          (null_value) @value.null,
          (enum_value) @value.enum,
          (list_value) @value.list,
          (object_value) @value.object
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (description) @doc.description,
          (comment) @doc.comment
        ]
    """
} 