"""Rust-specific Tree-sitter patterns."""

RUST_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_item)
          (closure_expression)
          (async_block_expression)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
        (function_item
           name: (identifier) @function.name
            parameters: (parameters
              (parameter
                pattern: (_) @function.param.name
                type: (_) @function.param.type)*) @function.params
            return_type: (_)? @function.return_type
            body: (block) @function.body
            [
              (attribute_item)* @function.attributes
              (comment)* @function.doc
            ]?) @function.def,
          (closure_expression
            parameters: (parameters)? @function.params
            return_type: (_)? @function.return_type
            body: (block) @function.body) @function.closure,
          (async_block_expression
            body: (block) @function.async.body) @function.async
        ]
    """,
    # Trait patterns
    "trait": """
        (trait_item
          name: (identifier) @trait.name
          type_parameters: (type_parameters)? @trait.type_params
          bounds: (trait_bounds)? @trait.bounds
          body: (declaration_list
            [
              (function_item)* @trait.methods
              (type_item)* @trait.types
              (const_item)* @trait.constants
              (macro_invocation)* @trait.macros
            ])) @trait.def
    """,
    # Implementation patterns
    "impl": """
        [
          (impl_item
            type: (type_identifier) @impl.type
            trait: (type_identifier)? @impl.trait
            body: (declaration_list
              [
                (function_item)* @impl.methods
                (type_item)* @impl.types
                (const_item)* @impl.constants
                (macro_invocation)* @impl.macros
              ])) @impl.def,
          (impl_item
            type: (generic_type) @impl.generic.type
            trait: (generic_type)? @impl.generic.trait
            body: (declaration_list)) @impl.generic
        ]
    """,
    # Macro patterns
    "macro": """
        [
          (macro_definition
            name: (identifier) @macro.name
            parameters: (macro_parameters)? @macro.params
            body: (macro_body) @macro.body) @macro.def,
          (macro_invocation
            macro: (identifier) @macro.call.name
            arguments: (token_tree) @macro.call.args) @macro.call
        ]
    """,
    # Lifetime patterns
    "lifetime": """
        [
          (lifetime
            (identifier) @lifetime.name) @lifetime,
          (lifetime_constraint
            lifetime: (lifetime) @lifetime.constrained
            bounds: (lifetime_bounds
              (lifetime)* @lifetime.bound)) @lifetime.constraint
        ]
    """,
    # Type patterns
    "type": """
        [
          (type_item
            name: (type_identifier) @type.name
            type_parameters: (type_parameters)? @type.params
            body: (_) @type.body) @type.def,
          (type_identifier) @type.ref,
          (generic_type
            type: (type_identifier) @type.generic.base
            arguments: (type_arguments
              (_)* @type.generic.args)) @type.generic
        ]
    """,
    # Module patterns
    "module": """
        [
          (mod_item
            name: (identifier) @module.name
            body: (declaration_list)? @module.body) @module,
          (extern_crate
            name: (identifier) @crate.name
            alias: (identifier)? @crate.alias) @crate
        ]
    """,
    # Attribute patterns
    "attribute": """
        [
          (attribute_item
            path: (identifier) @attribute.name
            arguments: (token_tree)? @attribute.args) @attribute,
          (inner_attribute_item
            path: (identifier) @attribute.inner.name
            arguments: (token_tree)? @attribute.inner.args) @attribute.inner
        ]
    """,
    # Documentation patterns
    "documentation": """
        [
          (line_comment) @doc.line,
          (block_comment) @doc.block,
          (attribute_item
            path: (identifier) @doc.attr.name
            (#match? @doc.attr.name "^doc$")
            arguments: (token_tree) @doc.attr.content) @doc.attr
        ]
    """
} 