"""Ruby-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

RUBY_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic method (from common)
          (method) @syntax.method,
          
          ; Rich method patterns
          (method
            name: (identifier) @syntax.function.name
            parameters: (method_parameters
              [(identifier) @syntax.function.param.name
               (optional_parameter
                 name: (identifier) @syntax.function.param.name
                 value: (_) @syntax.function.param.default)
               (rest_parameter
                 name: (identifier) @syntax.function.param.rest)
               (keyword_parameter
                 name: (identifier) @syntax.function.param.keyword
                 value: (_)? @syntax.function.param.default)
               (hash_splat_parameter
                 name: (identifier) @syntax.function.param.kwargs)]*) @syntax.function.params
            body: (body_statement) @syntax.function.body) @syntax.function.def,
            
          ; Singleton method patterns
          (singleton_method
            object: (_) @syntax.function.singleton.object
            name: (identifier) @syntax.function.singleton.name
            parameters: (method_parameters)? @syntax.function.singleton.params
            body: (body_statement) @syntax.function.singleton.body) @syntax.function.singleton
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class) @syntax.class,
          
          ; Rich class patterns
          (class
            name: (constant) @syntax.class.name
            superclass: (superclass
              name: (constant) @syntax.class.superclass)? @syntax.class.extends
            body: (body_statement
              [(method) @syntax.class.method
               (singleton_method) @syntax.class.singleton_method
               (class_variable) @syntax.class.class_var
               (instance_variable) @syntax.class.instance_var
               (constant) @syntax.class.constant]*) @syntax.class.body) @syntax.class.def,
               
          ; Module patterns
          (module
            name: (constant) @syntax.module.name
            body: (body_statement) @syntax.module.body) @syntax.module.def
        ]
    """,
    
    # Structure category with rich patterns
    "module": """
        [
          (module
            name: (constant) @structure.module.name
            body: (body_statement
              [(include) @structure.module.include
               (extend) @structure.module.extend
               (prepend) @structure.module.prepend]*) @structure.module.body) @structure.module,
               
          (require
            name: (string) @structure.require.name) @structure.require,
            
          (require_relative
            name: (string) @structure.require.relative.name) @structure.require.relative
        ]
    """,
    
    # Metaprogramming patterns
    "meta": """
        [
          ; Method missing
          (method
            name: (identifier) @semantics.meta.method_missing
            (#match? @semantics.meta.method_missing "^method_missing$")) @semantics.meta.method_missing.def,
            
          ; Dynamic method definition
          (call
            method: (identifier) @semantics.meta.define_method
            (#match? @semantics.meta.define_method "^define_method$")
            arguments: (argument_list
              name: (_) @semantics.meta.define_method.name
              block: (block) @semantics.meta.define_method.body)) @semantics.meta.define_method.call,
            
          ; Attribute accessors
          (call
            method: [(identifier) (constant)]
            (#match? @method "^(attr_reader|attr_writer|attr_accessor)$")
            arguments: (argument_list
              (_)* @semantics.meta.attr.name)) @semantics.meta.attr
        ]
    """,
    
    # Block patterns
    "block": """
        [
          (block
            parameters: (block_parameters
              [(identifier) @semantics.block.param.name
               (destructured_parameter
                 (identifier)+ @semantics.block.param.destructure)]*) @semantics.block.params
            body: (body_statement) @semantics.block.body) @semantics.block,
            
          (do_block
            parameters: (block_parameters)? @semantics.block.do.params
            body: (body_statement) @semantics.block.do.body) @semantics.block.do
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; RDoc patterns
          (comment
            text: /^#\\s*@.*/) @documentation.rdoc.directive,
            
          ; Yard patterns
          (comment
            text: /^#\\s*@[a-zA-Z]+.*/) @documentation.yard.tag
        ]
    """,
    
    # Rails patterns
    "rails": """
        [
          ; Active Record associations
          (call
            method: (identifier) @semantics.rails.association
            (#match? @semantics.rails.association "^(belongs_to|has_many|has_one|has_and_belongs_to_many)$")
            arguments: (argument_list
              name: (symbol) @semantics.rails.association.name
              options: (hash)? @semantics.rails.association.options)) @semantics.rails.association.def,
            
          ; Validations
          (call
            method: (identifier) @semantics.rails.validation
            (#match? @semantics.rails.validation "^validates?(_[a-z_]+)?$")
            arguments: (argument_list
              fields: (_)+ @semantics.rails.validation.fields
              options: (hash)? @semantics.rails.validation.options)) @semantics.rails.validation.def
        ]
    """
} 