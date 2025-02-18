"""Python-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

PYTHON_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_definition) @syntax.function,
          
          ; Rich function patterns
          (function_definition
            decorators: (decorator
              name: (_) @syntax.function.decorator.name
              arguments: (argument_list)? @syntax.function.decorator.args)* @syntax.function.decorators
            name: (identifier) @syntax.function.name
            parameters: (parameters
              [(identifier) @syntax.function.param.name
               (typed_parameter
                 name: (identifier) @syntax.function.param.name
                 type: (type) @syntax.function.param.type)
               (default_parameter
                 name: (identifier) @syntax.function.param.name
                 value: (_) @syntax.function.param.default)
               (typed_default_parameter
                 name: (identifier) @syntax.function.param.name
                 type: (type) @syntax.function.param.type
                 value: (_) @syntax.function.param.default)
               (list_splat_pattern
                 name: (identifier) @syntax.function.param.args)
               (dictionary_splat_pattern
                 name: (identifier) @syntax.function.param.kwargs)]*) @syntax.function.params
            return_type: (type)? @syntax.function.return_type
            body: (block) @syntax.function.body) @syntax.function.def,
            
          ; Method patterns
          (class_definition
            body: (block
              (function_definition
                decorators: (decorator
                  name: [(identifier) (attribute) (call)]
                  (#match? @name "^(classmethod|staticmethod|property)$"))? @syntax.function.method.decorator
                name: (identifier) @syntax.function.method.name
                parameters: (parameters
                  (identifier) @syntax.function.method.self) @syntax.function.method.params
                body: (block) @syntax.function.method.body) @syntax.function.method))
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_definition) @syntax.class,
          
          ; Rich class patterns
          (class_definition
            decorators: (decorator)* @syntax.class.decorators
            name: (identifier) @syntax.class.name
            arguments: (argument_list
              [(identifier) @syntax.class.base
               (keyword_argument
                 name: (identifier) @syntax.class.metaclass.name
                 value: (_) @syntax.class.metaclass.value)]*) @syntax.class.bases
            body: (block
              [(function_definition) @syntax.class.method
               (class_definition) @syntax.class.nested
               (expression_statement
                 (assignment
                   left: (identifier) @syntax.class.field.name
                   right: (_) @syntax.class.field.value)) @syntax.class.field]*) @syntax.class.body) @syntax.class.def
        ]
    """,
    
    # Structure category with rich patterns
    "module": """
        [
          ; Basic import (from common)
          (import_statement) @structure.import,
          (import_from_statement) @structure.import.from,
          
          ; Rich import patterns
          (import_statement
            name: (dotted_name
              [(identifier) @structure.import.module
               (identifier) @structure.import.name])) @structure.import,
               
          (import_from_statement
            module_name: (dotted_name)? @structure.import.from.module
            name: (dotted_name) @structure.import.from.name
            alias: (identifier)? @structure.import.from.alias) @structure.import.from,
            
          ; Module level attributes
          (expression_statement
            (assignment
              left: (identifier) @structure.module.attr.name
              (#match? @structure.module.attr.name "^(__[a-zA-Z0-9_]+__)$")
              right: (_) @structure.module.attr.value)) @structure.module.attr
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; Rich documentation patterns
          (comment) @documentation.comment,
          
          ; Docstring patterns
          (module
            (expression_statement
              (string) @documentation.module.docstring)) @documentation.module,
              
          (function_definition
            body: (block
              (expression_statement
                (string) @documentation.function.docstring))) @documentation.function,
                
          (class_definition
            body: (block
              (expression_statement
                (string) @documentation.class.docstring))) @documentation.class,
                
          ; Type hints
          (type) @documentation.type_hint,
          (type_comment) @documentation.type_comment
        ]
    """,
    
    # Type system patterns
    "typing": """
        [
          (type_parameter
            name: (identifier) @semantics.typing.param.name
            bound: (type)? @semantics.typing.param.bound) @semantics.typing.param,
            
          (union_type
            types: (type)+ @semantics.typing.union.member) @semantics.typing.union,
            
          (optional_type
            type: (type) @semantics.typing.optional.type) @semantics.typing.optional,
            
          (generic_type
            name: (identifier) @semantics.typing.generic.name
            arguments: (type_parameter_list
              (type)+ @semantics.typing.generic.arg)) @semantics.typing.generic
        ]
    """,
    
    # Decorator patterns
    "decorator": """
        [
          (decorator
            name: [(identifier) (attribute) (call)] @semantics.decorator.name
            arguments: (argument_list
              [(positional_argument) @semantics.decorator.arg.pos
               (keyword_argument
                 name: (identifier) @semantics.decorator.arg.name
                 value: (_) @semantics.decorator.arg.value)]*) @semantics.decorator.args) @semantics.decorator
        ]
    """
} 