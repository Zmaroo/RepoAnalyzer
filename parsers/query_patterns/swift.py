"""Swift-specific Tree-sitter patterns."""

SWIFT_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_declaration)
          (closure_expression)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (function_declaration
            name: (identifier) @function.name
            parameters: (parameter_clause) @function.params
            body: (code_block) @function.body) @function.def,
          (closure_expression
            parameters: (parameter_clause)? @function.params
            body: (code_block) @function.body) @function.def
        ]
    """,
    # Class patterns
    "class": """
        [
          (class_declaration
            attributes: (attribute)* @class.attributes
            modifiers: (declaration_modifier)* @class.modifiers
            name: (type_identifier) @class.name
            type_parameters: (generic_parameter_clause)? @class.type_params
            inheritance: (type_inheritance_clause)? @class.inheritance
            body: (class_body) @class.body) @class.def
        ]
    """,
    # Protocol patterns
    "protocol": """
        [
          (protocol_declaration
            attributes: (attribute)* @protocol.attributes
            modifiers: (declaration_modifier)* @protocol.modifiers
            name: (type_identifier) @protocol.name
            type_parameters: (generic_parameter_clause)? @protocol.type_params
            inheritance: (type_inheritance_clause)? @protocol.inheritance
            body: (protocol_body) @protocol.body) @protocol.def
        ]
    """,
    # Extension patterns
    "extension": """
        [
          (extension_declaration
            attributes: (attribute)* @extension.attributes
            modifiers: (declaration_modifier)* @extension.modifiers
            type: (type_identifier) @extension.type
            inheritance: (type_inheritance_clause)? @extension.inheritance
            where: (generic_where_clause)? @extension.where
            body: (extension_body) @extension.body) @extension.def
        ]
    """,
    # Property patterns
    "property": """
        [
          (variable_declaration
            attributes: (attribute)* @property.attributes
            modifiers: (declaration_modifier)* @property.modifiers
            name: (pattern) @property.name
            type: (type_annotation)? @property.type
            value: (code_block)? @property.value) @property.def,
          (computed_property
            attributes: (attribute)* @property.computed.attributes
            modifiers: (declaration_modifier)* @property.computed.modifiers
            name: (pattern) @property.computed.name
            type: (type_annotation)? @property.computed.type
            getter: (getter_clause) @property.computed.getter
            setter: (setter_clause)? @property.computed.setter) @property.computed.def
        ]
    """,
    # Method patterns
    "method": """
        [
          (instance_method
            attributes: (attribute)* @method.attributes
            modifiers: (declaration_modifier)* @method.modifiers
            name: (identifier) @method.name
            parameters: (parameter_clause) @method.params
            return_type: (return_clause)? @method.return
            body: (code_block) @method.body) @method.def,
          (class_method
            attributes: (attribute)* @method.class.attributes
            modifiers: (declaration_modifier)* @method.class.modifiers
            name: (identifier) @method.class.name
            parameters: (parameter_clause) @method.class.params
            return_type: (return_clause)? @method.class.return
            body: (code_block) @method.class.body) @method.class.def
        ]
    """,
    # Type patterns
    "type": """
        [
          (typealias_declaration
            attributes: (attribute)* @type.alias.attributes
            modifiers: (declaration_modifier)* @type.alias.modifiers
            name: (type_identifier) @type.alias.name
            type_parameters: (generic_parameter_clause)? @type.alias.type_params
            value: (type) @type.alias.value) @type.alias.def,
          (struct_declaration
            attributes: (attribute)* @type.struct.attributes
            modifiers: (declaration_modifier)* @type.struct.modifiers
            name: (type_identifier) @type.struct.name
            type_parameters: (generic_parameter_clause)? @type.struct.type_params
            inheritance: (type_inheritance_clause)? @type.struct.inheritance
            body: (struct_body) @type.struct.body) @type.struct.def
        ]
    """,
    # Enum patterns
    "enum": """
        [
          (enum_declaration
            attributes: (attribute)* @enum.attributes
            modifiers: (declaration_modifier)* @enum.modifiers
            name: (type_identifier) @enum.name
            type_parameters: (generic_parameter_clause)? @enum.type_params
            inheritance: (type_inheritance_clause)? @enum.inheritance
            body: (enum_body
              (enum_case
                attributes: (attribute)* @enum.case.attributes
                modifiers: (declaration_modifier)* @enum.case.modifiers
                name: (identifier) @enum.case.name
                parameters: (parameter_clause)? @enum.case.params)*) @enum.body) @enum.def
        ]
    """,
    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (condition_list) @if.condition
            body: (code_block) @if.body
            else: (else_clause)? @if.else) @if,
          (guard_statement
            condition: (condition_list) @guard.condition
            body: (code_block) @guard.body) @guard,
          (switch_statement
            expression: (_) @switch.expr
            cases: (switch_case_list
              (case_item
                pattern: (_) @case.pattern
                where: (where_clause)? @case.where
                body: (code_block) @case.body)*) @switch.cases) @switch
        ]
    """,
    # Error handling patterns
    "error_handling": """
        [
          (do_statement
            body: (code_block) @do.body
            catch: (catch_clause
              pattern: (_)? @catch.pattern
              where: (where_clause)? @catch.where
              body: (code_block) @catch.body)*) @do,
          (throw_statement
            expression: (_) @throw.expr) @throw
        ]
    """,
    # Concurrency patterns
    "concurrency": """
        [
          (async_let_declaration
            pattern: (_) @async.let.pattern
            type: (type_annotation)? @async.let.type
            value: (_) @async.let.value) @async.let,
          (await_expression
            expression: (_) @await.expr) @await
        ]
    """,
    # Property wrapper patterns
    "property_wrapper": """
        [
          (property_wrapper_declaration
            attributes: (attribute)* @wrapper.attributes
            modifiers: (declaration_modifier)* @wrapper.modifiers
            name: (type_identifier) @wrapper.name
            type_parameters: (generic_parameter_clause)? @wrapper.type_params
            wrapped_type: (type) @wrapper.wrapped_type
            body: (property_wrapper_body) @wrapper.body) @wrapper.def
        ]
    """,
    # Result builder patterns
    "result_builder": """
        [
          (result_builder_declaration
            attributes: (attribute)* @builder.attributes
            modifiers: (declaration_modifier)* @builder.modifiers
            name: (type_identifier) @builder.name
            type_parameters: (generic_parameter_clause)? @builder.type_params
            body: (result_builder_body) @builder.body) @builder.def
        ]
    """
} 