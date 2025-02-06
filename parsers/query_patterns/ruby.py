"""Ruby-specific Tree-sitter patterns."""

RUBY_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (method)
          (singleton_method)
          (block)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (method
            name: (identifier) @function.name
            parameters: (method_parameters
              [
                (identifier) @function.param.name
                (optional_parameter
                  name: (identifier) @function.param.name
                  value: (_) @function.param.default)
                (keyword_parameter
                  name: (identifier) @function.param.name
                  value: (_)? @function.param.default)
                (rest_parameter
                  name: (identifier) @function.param.rest)
                (block_parameter
                  name: (identifier) @function.param.block)
              ]*) @function.params
            [
              (body_statement) @function.body
              (comment)* @function.doc
            ]) @function.def,
          (singleton_method
            object: (_) @function.singleton
            name: (identifier) @function.name
            parameters: (method_parameters)? @function.params
            body: (body_statement) @function.body) @function.def,
          (block
            parameters: (block_parameters)? @block.params
            body: (body_statement) @block.body) @block.do
        ]
    """,
    # Class patterns
    "class": """
        [
          (class
            name: (constant) @class.name
            superclass: (superclass
              value: (constant) @class.superclass)?
            body: (body_statement
              [
                (comment)* @class.doc
                (method)* @class.methods
                (singleton_class
                  value: (self) @class.singleton
                  body: (body_statement))* @class.singleton_methods
              ])) @class.def,
          (singleton_class
            value: (_) @class.singleton.value
            body: (body_statement) @class.singleton.body) @class.singleton
        ]
    """,
    # Module patterns
    "module": """
        (module
          name: (constant) @module.name
          body: (body_statement
            [
              (comment)* @module.doc
              (method)* @module.methods
              (module_function
                (identifier)* @module.function)*
              ])) @module.def
    """,
    # Metaprogramming patterns
    "metaprogramming": """
        [
        (call
            receiver: (_)?
            method: [
              (identifier) @meta.method
              (#match? @meta.method "^(define_method|alias_method|attr_accessor|attr_reader|attr_writer|include|extend|prepend)$")
            ]
            arguments: (argument_list
              (_)* @meta.args)) @meta.call,
          (class_variable) @meta.class_var,
          (instance_variable) @meta.instance_var
        ]
    """,
    # Block patterns
    "block": """
        [
          (do_block
            parameters: (block_parameters)? @block.params
            body: (body_statement) @block.body) @block.do,
          (block
            parameters: (block_parameters)? @block.params
            body: (body_statement) @block.body) @block.brace
        ]
    """,
    # Control flow patterns
    "control_flow": """
        [
          (if
            condition: (_) @if.condition
            consequence: (_) @if.then
            alternative: (_)? @if.else) @if,
          (unless
            condition: (_) @unless.condition
            consequence: (_) @unless.then
            alternative: (_)? @unless.else) @unless,
          (while
            condition: (_) @while.condition
            body: (_) @while.body) @while,
          (until
            condition: (_) @until.condition
            body: (_) @until.body) @until,
          (for
            pattern: (_) @for.pattern
            collection: (_) @for.collection
            body: (_) @for.body) @for,
          (case
            value: (_)? @case.value
            (when
              pattern: (_) @when.pattern
              body: (_) @when.body)*
            else: (_)? @case.else) @case
        ]
    """,
    # Exception handling patterns
    "exception": """
        [
          (begin
            body: (_) @begin.body
            (rescue
              exception: (_)? @rescue.type
              variable: (_)? @rescue.var
              body: (_) @rescue.body)*
            (else
              body: (_) @rescue.else)?
            (ensure
              body: (_) @rescue.ensure)?) @begin,
          (rescue_modifier
            body: (_) @rescue_mod.body
            handler: (_) @rescue_mod.handler) @rescue_mod
        ]
    """,
    # String patterns
    "string": """
        [
          (string
            (string_content) @string.content) @string,
          (heredoc_beginning) @heredoc.start
          (heredoc_body
            (string_content) @heredoc.content) @heredoc,
          (interpolation
            (_) @string.interpolation) @interpolation
        ]
    """,
    # Symbol patterns
    "symbol": """
        [
          (simple_symbol) @symbol,
          (hash_key_symbol) @symbol.key,
          (symbol_array) @symbol.array
        ]
    """,
    "rails_patterns": """
        [
            (call
                method: (identifier) @rails.method
                (#match? @rails.method "^(belongs_to|has_many|has_one|validates|scope|before_action|after_action)$")
                arguments: (argument_list)? @rails.args) @rails.call,
            (class
                (constant) @model.name
                (superclass
                    (constant) @model.parent
                    (#match? @model.parent "^(ApplicationRecord|ActiveRecord::Base)$"))) @model
        ]
    """,
    "meta_programming": """
        [
            (call
                method: (identifier) @meta.method
                (#match? @meta.method "^(class_eval|instance_eval|define_method|method_missing|respond_to_missing\\?)$")
                arguments: (argument_list)? @meta.args) @meta.call,
            (singleton_class
                value: (_) @meta.target
                body: (body_statement) @meta.body) @meta.singleton
        ]
    """
} 