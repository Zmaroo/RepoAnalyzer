"""
Query patterns for Haskell files.
"""

from .common import COMMON_PATTERNS

HASKELL_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function
                name: (variable) @name
                rhs: (_) @body) @function
            """,
            """
            (signature
                names: (variables) @name
                type: (_) @type) @function
            """
        ],
        "class": [
            """
            (class_declaration
                name: (type_constructor) @name
                vars: (_)* @type_vars) @class
            """,
            """
            (data_declaration
                name: (type_constructor) @name
                constructors: (_)* @constructors) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (module_declaration
                name: (module_name) @name) @namespace
            """
        ],
        "import": [
            """
            (import_declaration
                name: (module_name) @module
                qualified: (qualified)? @qualified
                as: (module_name)? @alias) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (pattern_binding
                name: (variable) @name
                rhs: (_) @value) @variable
            """
        ],
        "type": [
            """
            (type_signature
                name: (variable) @name
                type: (_) @type) @type_decl
            """
        ]
    },
    "documentation": {
        "docstring": [
            """
            (module_docstring) @docstring
            """,
            """
            (function_docstring) @docstring
            """
        ],
        "comment": [
            """
            (comment) @comment
            """,
            """
            (block_comment) @comment
            """
        ]
    },
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_declaration) @syntax.function,
          
          ; Rich function patterns
          (function_declaration
            name: (variable) @syntax.function.name
            type_signature: (type_signature
              name: (variable) @syntax.function.type.name
              type: (_) @syntax.function.type.signature)? @syntax.function.type
            patterns: [(pattern) @syntax.function.pattern]*
            rhs: (rhs
              body: (_) @syntax.function.body
              where_clause: (where_clause
                declarations: [(function_declaration) @syntax.function.where.function
                             (pattern_binding) @syntax.function.where.binding]*) @syntax.function.where)?) @syntax.function.def,
                             
          ; Operator patterns
          (operator_declaration
            name: (variable_symbol) @syntax.function.operator.name
            type_signature: (type_signature
              type: (_) @syntax.function.operator.type)? @syntax.function.operator.type
            patterns: [(pattern) @syntax.function.operator.pattern]*
            rhs: (rhs
              body: (_) @syntax.function.operator.body)) @syntax.function.operator
        ]
    """,
    
    # Type patterns
    "type": """
        [
          ; Data type patterns
          (data_declaration
            name: (type_constructor) @syntax.type.data.name
            type_variables: [(type_variable) @syntax.type.data.var]* @syntax.type.data.vars
            constructors: (constructor_declarations
              [(constructor_declaration
                 name: (constructor) @syntax.type.data.ctor.name
                 fields: [(type) @syntax.type.data.ctor.field]* @syntax.type.data.ctor.fields)]*) @syntax.type.data.ctors
            deriving: (deriving_clause
              classes: [(constructor) @syntax.type.data.deriving.class]*) @syntax.type.data.deriving?) @syntax.type.data,
                
          ; Type class patterns
          (class_declaration
            context: (context
              constraints: [(class_constraint
                            class: (constructor) @syntax.type.class.constraint.class
                            types: [(type_variable) @syntax.type.class.constraint.var]*) @syntax.type.class.constraint]*) @syntax.type.class.context?
            name: (constructor) @syntax.type.class.name
            type_variables: [(type_variable) @syntax.type.class.var]* @syntax.type.class.vars
            declarations: [(type_signature) @syntax.type.class.signature
                         (function_declaration) @syntax.type.class.function]* @syntax.type.class.decls) @syntax.type.class,
                         
          ; Type instance patterns
          (instance_declaration
            context: (context)? @syntax.type.instance.context
            class: (constructor) @syntax.type.instance.class
            types: [(type) @syntax.type.instance.type]*
            declarations: [(function_declaration) @syntax.type.instance.function]*) @syntax.type.instance
        ]
    """,
    
    # Module patterns
    "module": """
        [
          (module_declaration
            name: (module) @structure.module.name
            exports: (export_spec_list
              exports: [(export_spec
                         names: [(variable) @structure.module.export.var
                                (constructor) @structure.module.export.ctor])*])? @structure.module.exports) @structure.module,
                                
          (import_declaration
            qualified: (qualified)? @structure.import.qualified
            module: (module) @structure.import.module
            alias: (module)? @structure.import.alias
            imports: (import_spec_list
              imports: [(import_spec
                         names: [(variable) @structure.import.name
                                (constructor) @structure.import.ctor])*])? @structure.import.specs) @structure.import
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; Haddock documentation
          (comment) @documentation.haddock {
            match: "^--\\s*[|^*$]"
          },
          
          ; Haddock sections
          (comment) @documentation.haddock.section {
            match: "^--\\s*[=#]"
          },
          
          ; Haddock references
          (comment) @documentation.haddock.reference {
            match: "'[^']+'|\"[^\"]+\""
          }
        ]
    """,
    
    # Pattern matching patterns
    "pattern": """
        [
          (case_expression
            expression: (_) @semantics.pattern.case.expr
            alternatives: [(case_alternative
                           pattern: (_) @semantics.pattern.case.pattern
                           body: (_) @semantics.pattern.case.body)]*) @semantics.pattern.case,
                           
          (lambda_expression
            patterns: [(pattern) @semantics.pattern.lambda.pattern]*
            body: (_) @semantics.pattern.lambda.body) @semantics.pattern.lambda,
            
          (list_comprehension
            expression: (_) @semantics.pattern.comp.expr
            qualifiers: [(generator
                         pattern: (_) @semantics.pattern.comp.pattern
                         expression: (_) @semantics.pattern.comp.gen)
                        (pattern_binding
                         pattern: (_) @semantics.pattern.comp.let.pattern
                         expression: (_) @semantics.pattern.comp.let.expr)]*) @semantics.pattern.comp
        ]
    """,
    
    # Type class patterns
    "typeclass": """
        [
          (class_declaration
            context: (context)? @semantics.typeclass.context
            name: (constructor) @semantics.typeclass.name
            fundeps: (fundeps
              dependencies: [(fundep
                             vars: [(type_variable) @semantics.typeclass.fundep.var]*) @semantics.typeclass.fundep]*) @semantics.typeclass.fundeps?) @semantics.typeclass,
                             
          (default_declaration
            types: [(type) @semantics.typeclass.default.type]*) @semantics.typeclass.default
        ]
    """,
    
    # Monad patterns
    "monad": """
        [
          (do_expression
            statements: [(generator
                         pattern: (_) @semantics.monad.do.pattern
                         expression: (_) @semantics.monad.do.expr)
                        (expression_binding
                         expression: (_) @semantics.monad.do.bind)]*
            return: (_) @semantics.monad.do.return) @semantics.monad.do,
                         
          (function_call
            function: (variable) @semantics.monad.func
            (#match? @semantics.monad.func "^(return|>>=|>>|=<<)$")
            arguments: (_)* @semantics.monad.args) @semantics.monad.call
        ]
    """
} 