"""
Query patterns for OCaml implementation files.

These patterns capture top-level declarations from the custom AST produced by our OCaml parser.
The custom parser produces an AST with a root of type "ocaml_stream" whose children have types
such as "let_binding", "type_definition", "module_declaration", "open_statement", and
"exception_declaration". The patterns below use capture names (e.g. @let_binding) so that our
downstream processing can store all key pieces of information.
"""

from .common import COMMON_PATTERNS

OCAML_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (let_binding
            pattern: (value_pattern) @syntax.function.function) @syntax.function.binding,
          
          ; Rich function patterns
          (let_binding
            rec: (rec)? @syntax.function.rec
            pattern: (value_pattern
              name: (value_name) @syntax.function.name
              parameters: [(pattern) @syntax.function.param.pattern
                         (typed_pattern
                           pattern: (pattern) @syntax.function.param.pattern
                           type: (_) @syntax.function.param.type)]* @syntax.function.params)
            type_constraint: (type_constraint
              type: (_) @syntax.function.return_type)? @syntax.function.type
            body: (_) @syntax.function.body
            attributes: (attribute)* @syntax.function.attributes) @syntax.function.def,
            
          ; Method patterns
          (method_definition
            name: (method_name) @syntax.function.method.name
            parameters: [(pattern) @syntax.function.method.param]* @syntax.function.method.params
            type_constraint: (type_constraint)? @syntax.function.method.type
            body: (_) @syntax.function.method.body) @syntax.function.method
        ]
    """,
    
    # Type patterns
    "type": """
        [
          ; Type definition patterns
          (type_definition
            params: (type_params
              params: [(type_param
                        variance: [(pos) (neg)]? @syntax.type.param.variance
                        name: (type_variable) @syntax.type.param.name)]* @syntax.type.params)?
            name: (type_constructor) @syntax.type.name
            manifest: (type_equation
              type: (_) @syntax.type.equation)? @syntax.type.manifest
            kind: [(variant_declaration
                    constructors: [(constructor_declaration
                                   name: (constructor_name) @syntax.type.variant.ctor.name
                                   arguments: [(constructor_argument
                                              type: (_) @syntax.type.variant.ctor.arg)]*) @syntax.type.variant.ctor]* @syntax.type.variant.ctors) @syntax.type.variant
                   (record_declaration
                    fields: [(field_declaration
                             mutable: (mutable)? @syntax.type.record.field.mut
                             name: (field_name) @syntax.type.record.field.name
                             type: (_) @syntax.type.record.field.type)]* @syntax.type.record.fields) @syntax.type.record]
            constraints: [(type_constraint
                          variable: (type_variable) @syntax.type.constraint.var
                          type: (_) @syntax.type.constraint.type)]* @syntax.type.constraints) @syntax.type.def,
                          
          ; Module type patterns
          (module_type_definition
            name: (module_type_name) @syntax.type.module.name
            body: (_) @syntax.type.module.body) @syntax.type.module
        ]
    """,
    
    # Module patterns
    "module": """
        [
          (module_definition
            name: (module_name) @structure.module.name
            type_constraint: (module_type_constraint
              type: (_) @structure.module.type)? @structure.module.constraint
            body: (_) @structure.module.body) @structure.module,
            
          (module_binding
            name: (module_name) @structure.module.binding.name
            body: (_) @structure.module.binding.body) @structure.module.binding,
            
          (open_statement
            module: (_) @structure.open.module) @structure.open
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; OCamldoc documentation
          (comment) @documentation.ocamldoc {
            match: "^(\\*\\*|\\*)"
          },
          
          ; OCamldoc tags
          (comment) @documentation.ocamldoc.tag {
            match: "@[a-zA-Z]+"
          }
        ]
    """,
    
    # Pattern matching patterns
    "pattern": """
        [
          (match_expression
            value: (_) @semantics.pattern.match.expr
            cases: [(match_case
                     pattern: (_) @semantics.pattern.match.pattern
                     guard: (when_clause
                       expr: (_) @semantics.pattern.match.guard)? @semantics.pattern.match.when
                     body: (_) @semantics.pattern.match.body)]*) @semantics.pattern.match,
                     
          (function_expression
            cases: [(match_case
                     pattern: (_) @semantics.pattern.function.pattern
                     body: (_) @semantics.pattern.function.body)]*) @semantics.pattern.function
        ]
    """,
    
    # Object-oriented patterns
    "object": """
        [
          (class_definition
            params: (class_params
              params: [(pattern) @syntax.object.class.param]*) @syntax.object.class.params
            name: (class_name) @syntax.object.class.name
            type_params: (type_params)? @syntax.object.class.type_params
            body: (class_body
              [(method_definition) @syntax.object.class.method
               (value_definition) @syntax.object.class.value
               (initializer_definition) @syntax.object.class.init]*) @syntax.object.class.body) @syntax.object.class,
               
          (object_expression
            body: (object_body
              [(method_definition) @syntax.object.method
               (value_definition) @syntax.object.value]*) @syntax.object.body) @syntax.object
        ]
    """,
    
    # Functor patterns
    "functor": """
        [
          (functor_definition
            params: [(functor_parameter
                      name: (module_name) @semantics.functor.param.name
                      type: (_) @semantics.functor.param.type)]* @semantics.functor.params
            body: (_) @semantics.functor.body) @semantics.functor,
            
          (functor_application
            functor: (_) @semantics.functor.app.name
            argument: (_) @semantics.functor.app.arg) @semantics.functor.app
        ]
    """,
    
    # Exception patterns
    "exception": """
        [
          (exception_definition
            name: (constructor_name) @semantics.exception.name
            arguments: [(constructor_argument
                        type: (_) @semantics.exception.arg)]*) @semantics.exception.def,
                        
          (try_expression
            body: (_) @semantics.exception.try.body
            cases: [(match_case
                     pattern: (_) @semantics.exception.try.pattern
                     body: (_) @semantics.exception.try.handler)]*) @semantics.exception.try
        ]
    """
} 