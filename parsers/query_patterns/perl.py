"""
Query patterns for Perl files.
"""

from .common import COMMON_PATTERNS

PERL_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "subroutine": """
        [
          ; Basic subroutine (from common)
          (subroutine_declaration) @syntax.subroutine,
          
          ; Rich subroutine patterns
          (subroutine_declaration
            attributes: (attribute_list)? @syntax.subroutine.attributes
            name: [(bare_word) @syntax.subroutine.name
                  (package_qualified_word) @syntax.subroutine.qualified_name]
            prototype: (prototype)? @syntax.subroutine.prototype
            signature: (signature
              parameters: (parameter_list
                [(scalar_parameter
                   name: (scalar) @syntax.subroutine.param.name
                   type: (_)? @syntax.subroutine.param.type
                   default: (_)? @syntax.subroutine.param.default)
                 (array_parameter
                   name: (array) @syntax.subroutine.param.array)
                 (hash_parameter
                   name: (hash) @syntax.subroutine.param.hash)]*) @syntax.subroutine.params)? @syntax.subroutine.signature
            body: (block) @syntax.subroutine.body) @syntax.subroutine.def,
            
          ; Method patterns
          (subroutine_declaration
            attributes: (attribute_list
              (attribute
                name: (bare_word) @syntax.subroutine.method.attr
                (#match? @syntax.subroutine.method.attr "^method$"))) @syntax.subroutine.method.attributes) @syntax.subroutine.method
        ]
    """,
    
    # Package patterns
    "package": """
        [
          (package_statement
            name: (package_qualified_word) @structure.package.name
            version: (version_number)? @structure.package.version
            block: (block)? @structure.package.body) @structure.package,
            
          (use_statement
            module: (package_qualified_word) @structure.use.module
            version: (version_number)? @structure.use.version
            imports: (import_list)? @structure.use.imports) @structure.use,
            
          (require_statement
            module: (package_qualified_word) @structure.require.module
            version: (version_number)? @structure.require.version) @structure.require
        ]
    """,
    
    # Object-oriented patterns
    "class": """
        [
          ; Class definition via use base
          (use_statement
            module: (bare_word) @syntax.class.base
            (#match? @syntax.class.base "^base$")
            imports: (import_list
              (package_qualified_word) @syntax.class.parent)) @syntax.class.inheritance,
              
          ; Moose class patterns
          (use_statement
            module: (bare_word) @syntax.class.moose
            (#match? @syntax.class.moose "^Moose$")) @syntax.class.moose.use,
            
          (function_call
            function: (bare_word) @syntax.class.moose.attr
            (#match? @syntax.class.moose.attr "^(has|extends|with)$")
            arguments: (argument_list) @syntax.class.moose.args) @syntax.class.moose.def
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; POD documentation
          (pod_statement
            content: (_)* @documentation.pod.content) @documentation.pod,
            
          ; POD directives
          (pod_statement
            content: /^=\\w+.*/) @documentation.pod.directive
        ]
    """,
    
    # Regular expression patterns
    "regex": """
        [
          (regex
            pattern: (_) @semantics.regex.pattern
            modifiers: (_)? @semantics.regex.modifiers) @semantics.regex,
            
          (substitution
            pattern: (_) @semantics.regex.sub.pattern
            replacement: (_) @semantics.regex.sub.replacement
            modifiers: (_)? @semantics.regex.sub.modifiers) @semantics.regex.sub,
            
          (transliteration
            from: (_) @semantics.regex.tr.from
            to: (_) @semantics.regex.tr.to
            modifiers: (_)? @semantics.regex.tr.modifiers) @semantics.regex.tr
        ]
    """,
    
    # Special variable patterns
    "variable": """
        [
          (scalar
            sigil: "$" @semantics.var.scalar.sigil
            name: (_) @semantics.var.scalar.name) @semantics.var.scalar,
            
          (array
            sigil: "@" @semantics.var.array.sigil
            name: (_) @semantics.var.array.name) @semantics.var.array,
            
          (hash
            sigil: "%" @semantics.var.hash.sigil
            name: (_) @semantics.var.hash.name) @semantics.var.hash,
            
          (special_scalar
            name: (_) @semantics.var.special.name) @semantics.var.special
        ]
    """,
    
    # Error handling patterns
    "error": """
        [
          (eval_expression
            block: (block) @semantics.error.eval.block) @semantics.error.eval,
            
          (function_call
            function: (bare_word) @semantics.error.func
            (#match? @semantics.error.func "^(die|croak|confess|warn|carp|cluck)$")
            arguments: (argument_list) @semantics.error.args) @semantics.error.call
        ]
    """,
    
    # Pragmas and attributes
    "pragma": """
        [
          (use_statement
            module: (bare_word) @semantics.pragma.name
            (#match? @semantics.pragma.name "^(strict|warnings|feature|utf8|autodie)$")
            imports: (import_list)? @semantics.pragma.args) @semantics.pragma,
            
          (attribute
            name: (bare_word) @semantics.attr.name
            arguments: (argument_list)? @semantics.attr.args) @semantics.attr
        ]
    """,
    
    "syntax": {
        "function": [
            """
            (subroutine_declaration
                name: (identifier) @name
                block: (block) @body) @function
            """
        ],
        "class": [
            """
            (package_declaration
                name: (package_name) @name) @class
            """
        ]
    },
    
    "structure": {
        "namespace": [
            """
            (package_statement
                name: (package_name) @name) @namespace
            """
        ],
        "import": [
            """
            (use_statement
                module: (module_name) @module) @import
            """,
            """
            (require_statement
                module: (module_name) @module) @import
            """
        ]
    },
    
    "semantics": {
        "variable": [
            """
            (scalar_declaration
                name: (scalar) @name
                value: (_)? @value) @variable
            """,
            """
            (array_declaration
                name: (array) @name) @variable
            """,
            """
            (hash_declaration
                name: (hash) @name) @variable
            """
        ],
        "expression": [
            """
            (function_call
                name: (identifier) @name
                arguments: (argument_list)? @args) @expression
            """
        ]
    },
    
    "documentation": {
        "docstring": [
            """
            (pod_statement) @docstring
            """
        ],
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
} 