"""TypeScript-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS
from .js_base import JS_BASE_PATTERNS

TYPESCRIPT_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    **JS_BASE_PATTERNS,  # Include JavaScript base patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_declaration) @syntax.function,
          
          ; Rich function patterns
          (function_declaration
            modifiers: [(async) (declare) (export) (default)]* @syntax.function.modifier
            name: (identifier) @syntax.function.name
            type_parameters: (type_parameters
              (type_parameter
                name: (type_identifier) @syntax.function.type_param.name
                constraint: (type_constraint)? @syntax.function.type_param.constraint
                default: (type_reference)? @syntax.function.type_param.default)*) @syntax.function.type_params
            parameters: (formal_parameters
              [(required_parameter
                 pattern: (_) @syntax.function.param.pattern
                 type: (type_annotation)? @syntax.function.param.type)
               (optional_parameter
                 pattern: (_) @syntax.function.param.pattern
                 type: (type_annotation)? @syntax.function.param.type
                 value: (_)? @syntax.function.param.default)
               (rest_parameter
                 pattern: (_) @syntax.function.param.pattern
                 type: (type_annotation)? @syntax.function.param.type)]*) @syntax.function.params
            return_type: (type_annotation)? @syntax.function.return_type
            body: (statement_block) @syntax.function.body) @syntax.function.def,
            
          ; Method patterns
          (method_definition
            modifiers: [(public) (private) (protected) (static) (abstract) (override)]* @syntax.function.method.modifier
            name: (property_identifier) @syntax.function.method.name
            type_parameters: (type_parameters)? @syntax.function.method.type_params
            parameters: (formal_parameters) @syntax.function.method.params
            return_type: (type_annotation)? @syntax.function.method.return_type
            body: (statement_block)? @syntax.function.method.body) @syntax.function.method
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_declaration) @syntax.class,
          
          ; Rich class patterns
          (class_declaration
            modifiers: [(abstract) (declare) (export) (default)]* @syntax.class.modifier
            name: (type_identifier) @syntax.class.name
            type_parameters: (type_parameters)? @syntax.class.type_params
            extends: (class_heritage
              (extends_clause
                value: (type_reference) @syntax.class.extends.type)? @syntax.class.extends
              (implements_clause
                value: (type_reference)+ @syntax.class.implements.type)? @syntax.class.implements) @syntax.class.heritage
            body: (class_body
              [(method_definition) @syntax.class.method
               (public_field_definition) @syntax.class.field.public
               (private_field_definition) @syntax.class.field.private
               (index_signature) @syntax.class.index]*) @syntax.class.body) @syntax.class.def,
               
          ; Interface patterns
          (interface_declaration
            modifiers: [(declare) (export)]* @syntax.interface.modifier
            name: (type_identifier) @syntax.interface.name
            type_parameters: (type_parameters)? @syntax.interface.type_params
            extends: (extends_clause
              value: (type_reference)+ @syntax.interface.extends.type)? @syntax.interface.extends
            body: (object_type) @syntax.interface.body) @syntax.interface.def
        ]
    """,
    
    # Type system patterns
    "type": """
        [
          (type_alias_declaration
            modifiers: [(declare) (export)]* @semantics.type.modifier
            name: (type_identifier) @semantics.type.name
            type_parameters: (type_parameters)? @semantics.type.params
            value: (_) @semantics.type.value) @semantics.type.alias,
            
          (union_type
            types: (type_reference)+ @semantics.type.union.member) @semantics.type.union,
            
          (intersection_type
            types: (type_reference)+ @semantics.type.intersection.member) @semantics.type.intersection,
            
          (mapped_type_clause
            type_parameter: (type_parameter) @semantics.type.mapped.param
            type: (_) @semantics.type.mapped.value) @semantics.type.mapped
        ]
    """,
    
    # Decorator patterns
    "decorator": """
        [
          (decorator
            name: (_) @semantics.decorator.name
            arguments: (arguments
              (argument
                name: (property_identifier)? @semantics.decorator.arg.name
                value: (_) @semantics.decorator.arg.value)*) @semantics.decorator.args) @semantics.decorator
        ]
    """,
    
    # Module system patterns
    "import": """
        [
          ; Basic import (from common)
          (import_statement) @structure.import,
          
          ; Rich import patterns
          (import_statement
            modifiers: (import_kind)? @structure.import.kind
            source: (string) @structure.import.source
            imports: [(named_imports
                       (import_specifier
                         name: (identifier) @structure.import.name
                         alias: (identifier)? @structure.import.alias)*)
                     (namespace_import
                       name: (identifier) @structure.import.namespace)]) @structure.import.clause,
                       
          (export_statement
            declaration: (_)? @structure.export.declaration
            source: (string)? @structure.export.source) @structure.export
        ]
    """
}