"""Rust-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

RUST_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_item) @syntax.function,
          
          ; Rich function patterns
          (function_item
            attributes: (attribute_item)* @syntax.function.attributes
            visibility: (visibility_modifier)? @syntax.function.visibility
            qualifiers: [(async) (const) (unsafe) (extern)]* @syntax.function.qualifier
            name: (identifier) @syntax.function.name
            generic_params: (type_parameters
              [(lifetime_parameter
                 name: (lifetime) @syntax.function.type_param.lifetime)
               (type_parameter
                 name: (identifier) @syntax.function.type_param.name
                 bounds: (type_bound_clause)? @syntax.function.type_param.bounds
                 default: (_)? @syntax.function.type_param.default)
               (const_parameter
                 name: (identifier) @syntax.function.type_param.const.name
                 type: (_) @syntax.function.type_param.const.type)]*) @syntax.function.type_params
            parameters: (parameters
              [(parameter
                 pattern: (_) @syntax.function.param.pattern
                 type: (_) @syntax.function.param.type)
               (self_parameter
                 reference: (reference)? @syntax.function.param.self.ref
                 mutable: (mutable_specifier)? @syntax.function.param.self.mut)]*) @syntax.function.params
            return_type: (function_return_type
              type: (_) @syntax.function.return_type)? @syntax.function.return
            body: (block) @syntax.function.body) @syntax.function.def,
            
          ; Implementation methods
          (impl_item
            attributes: (attribute_item)* @syntax.function.impl.attributes
            visibility: (visibility_modifier)? @syntax.function.impl.visibility
            qualifiers: [(async) (const) (unsafe)]* @syntax.function.impl.qualifier
            name: (identifier) @syntax.function.impl.name) @syntax.function.impl
        ]
    """,
    
    "type": """
        [
          ; Basic type (from common)
          (type_item) @syntax.type,
          
          ; Rich type patterns
          (struct_item
            attributes: (attribute_item)* @syntax.type.struct.attributes
            visibility: (visibility_modifier)? @syntax.type.struct.visibility
            name: (identifier) @syntax.type.struct.name
            generic_params: (type_parameters)? @syntax.type.struct.type_params
            fields: [(field_declaration_list
                      (field_declaration
                        attributes: (attribute_item)* @syntax.type.struct.field.attributes
                        visibility: (visibility_modifier)? @syntax.type.struct.field.visibility
                        name: (identifier) @syntax.type.struct.field.name
                        type: (_) @syntax.type.struct.field.type)*) @syntax.type.struct.fields
                    (ordered_field_declaration_list)]) @syntax.type.struct,
                    
          ; Enum patterns
          (enum_item
            attributes: (attribute_item)* @syntax.type.enum.attributes
            visibility: (visibility_modifier)? @syntax.type.enum.visibility
            name: (identifier) @syntax.type.enum.name
            generic_params: (type_parameters)? @syntax.type.enum.type_params
            variants: (enum_variant_list
              (enum_variant
                attributes: (attribute_item)* @syntax.type.enum.variant.attributes
                name: (identifier) @syntax.type.enum.variant.name
                fields: [(field_declaration_list) (ordered_field_declaration_list)]? @syntax.type.enum.variant.fields
                discriminant: (_)? @syntax.type.enum.variant.discriminant)*) @syntax.type.enum.variants) @syntax.type.enum,
                
          ; Trait patterns
          (trait_item
            attributes: (attribute_item)* @syntax.type.trait.attributes
            visibility: (visibility_modifier)? @syntax.type.trait.visibility
            qualifiers: (unsafe)? @syntax.type.trait.qualifier
            name: (identifier) @syntax.type.trait.name
            generic_params: (type_parameters)? @syntax.type.trait.type_params
            bounds: (type_bound_clause)? @syntax.type.trait.bounds
            body: (declaration_list) @syntax.type.trait.body) @syntax.type.trait
        ]
    """,
    
    # Structure category with rich patterns
    "module": """
        [
          (mod_item
            attributes: (attribute_item)* @structure.module.attributes
            visibility: (visibility_modifier)? @structure.module.visibility
            name: (identifier) @structure.module.name
            body: (declaration_list)? @structure.module.body) @structure.module,
            
          (use_declaration
            visibility: (visibility_modifier)? @structure.use.visibility
            tree: (use_tree
              path: (identifier)+ @structure.use.path
              alias: (identifier)? @structure.use.alias)) @structure.use
        ]
    """,
    
    # Macro patterns
    "macro": """
        [
          (macro_definition
            name: (identifier) @semantics.macro.name
            parameters: (macro_parameters)? @semantics.macro.params
            body: (macro_body) @semantics.macro.body) @semantics.macro.def,
            
          (macro_invocation
            path: (identifier) @semantics.macro.call.name
            arguments: (token_tree) @semantics.macro.call.args) @semantics.macro.call
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (line_comment) @documentation.comment,
          
          ; Rich documentation patterns
          (line_comment) @documentation.comment {
            match: "^//[!/]"
          },
          
          ; Documentation attributes
          (attribute_item
            path: (identifier) @documentation.attr.name
            (#match? @documentation.attr.name "^doc$")
            arguments: (token_tree) @documentation.attr.args) @documentation.attr
        ]
    """,
    
    # Lifetime patterns
    "lifetime": """
        [
          (lifetime
            name: (_) @semantics.lifetime.name) @semantics.lifetime,
            
          (lifetime_constraint
            lifetime: (lifetime) @semantics.lifetime.constraint.lifetime
            bounds: (lifetime)+ @semantics.lifetime.constraint.bounds) @semantics.lifetime.constraint
        ]
    """,
    
    # Error handling patterns
    "error": """
        [
          (match_expression
            value: (try_expression) @semantics.error.try
            arms: (match_arm
              pattern: (or_pattern
                (pattern) @semantics.error.match.pattern)
              expression: (block) @semantics.error.match.block)*) @semantics.error.match,
              
          (result_type
            success_type: (_) @semantics.error.result.ok
            error_type: (_) @semantics.error.result.err) @semantics.error.result
        ]
    """
} 