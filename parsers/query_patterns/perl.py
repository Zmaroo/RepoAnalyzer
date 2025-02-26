"""
Query patterns for Perl files.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

PERL_PATTERNS_FOR_LEARNING = {
    "idiomatic_perl": {
        "pattern": """
        [
            (function_call
                function: (bare_word) @idiom.func.name
                (#match? @idiom.func.name "^(map|grep|split|join|keys|values|each|sort)$")
                arguments: (argument_list) @idiom.func.args) @idiom.func,
                
            (list_expression 
                items: (_) @idiom.list.items) @idiom.list,
                
            (hash_expression
                pairs: (_) @idiom.hash.pairs) @idiom.hash,
                
            (regex
                pattern: (_) @idiom.regex.pattern
                modifiers: (_)? @idiom.regex.modifiers) @idiom.regex
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "idiomatic_perl",
            "is_functional_call": "idiom.func" in node["captures"],
            "is_list_expression": "idiom.list" in node["captures"],
            "is_hash_expression": "idiom.hash" in node["captures"],
            "is_regex": "idiom.regex" in node["captures"],
            "function_name": node["captures"].get("idiom.func.name", {}).get("text", ""),
            "uses_regex": "idiom.regex" in node["captures"],
            "regex_modifiers": node["captures"].get("idiom.regex.modifiers", {}).get("text", ""),
            "is_functional_style": "idiom.func" in node["captures"] and node["captures"].get("idiom.func.name", {}).get("text", "") in ["map", "grep", "sort"],
            "idiom_type": (
                "functional" if (
                    "idiom.func" in node["captures"] and 
                    node["captures"].get("idiom.func.name", {}).get("text", "") in ["map", "grep", "sort"]
                ) else
                "data_structure" if (
                    "idiom.list" in node["captures"] or "idiom.hash" in node["captures"]
                ) else
                "text_processing" if (
                    "idiom.regex" in node["captures"] or
                    ("idiom.func" in node["captures"] and node["captures"].get("idiom.func.name", {}).get("text", "") in ["split", "join"])
                ) else
                "other"
            )
        }
    },
    
    "oop_paradigms": {
        "pattern": """
        [
            (use_statement
                module: (bare_word) @oop.module
                (#match? @oop.module "^(Moose|Moo|Mouse|Class::Accessor|Object::Tiny)$")) @oop.use,
                
            (function_call
                function: (bare_word) @oop.func.name
                (#match? @oop.func.name "^(has|extends|with|method|before|after|around|override)$")
                arguments: (argument_list) @oop.func.args) @oop.func,
                
            (package_statement
                name: (package_qualified_word) @oop.pkg.name) @oop.pkg,
                
            (method_call
                invocant: (_) @oop.method.invocant
                method: (_) @oop.method.name
                arguments: (argument_list)? @oop.method.args) @oop.method
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "oop_paradigms",
            "is_class_definition": "oop.use" in node["captures"],
            "is_attribute_definition": "oop.func" in node["captures"] and node["captures"].get("oop.func.name", {}).get("text", "") == "has",
            "is_inheritance": "oop.func" in node["captures"] and node["captures"].get("oop.func.name", {}).get("text", "") == "extends",
            "is_role_consumption": "oop.func" in node["captures"] and node["captures"].get("oop.func.name", {}).get("text", "") == "with",
            "is_method_call": "oop.method" in node["captures"],
            "package_name": node["captures"].get("oop.pkg.name", {}).get("text", ""),
            "object_framework": node["captures"].get("oop.module", {}).get("text", ""),
            "method_name": node["captures"].get("oop.method.name", {}).get("text", ""),
            "uses_method_modifiers": "oop.func" in node["captures"] and node["captures"].get("oop.func.name", {}).get("text", "") in ["before", "after", "around", "override"]
        }
    },
    
    "data_structure_usage": {
        "pattern": """
        [
            (array
                sigil: "@" @data.array.sigil
                name: (_) @data.array.name) @data.array,
                
            (array_element
                array: (_) @data.array_elem.array
                index: (_) @data.array_elem.index) @data.array_elem,
                
            (hash
                sigil: "%" @data.hash.sigil
                name: (_) @data.hash.name) @data.hash,
                
            (hash_element
                hash: (_) @data.hash_elem.hash
                key: (_) @data.hash_elem.key) @data.hash_elem,
                
            (dereference_expression
                argument: (_) @data.deref.arg) @data.deref
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "data_structure_usage",
            "is_array": "data.array" in node["captures"],
            "is_array_element": "data.array_elem" in node["captures"],
            "is_hash": "data.hash" in node["captures"],
            "is_hash_element": "data.hash_elem" in node["captures"],
            "is_dereference": "data.deref" in node["captures"],
            "array_name": node["captures"].get("data.array.name", {}).get("text", ""),
            "hash_name": node["captures"].get("data.hash.name", {}).get("text", ""),
            "uses_array_indexing": "data.array_elem" in node["captures"],
            "uses_hash_keys": "data.hash_elem" in node["captures"],
            "uses_complex_references": "data.deref" in node["captures"],
            "data_structure_type": (
                "array" if "data.array" in node["captures"] or "data.array_elem" in node["captures"] else
                "hash" if "data.hash" in node["captures"] or "data.hash_elem" in node["captures"] else
                "reference" if "data.deref" in node["captures"] else
                "other"
            )
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (function_call
                function: (bare_word) @error.func.name
                (#match? @error.func.name "^(die|croak|confess|warn|carp|cluck)$")
                arguments: (argument_list) @error.func.args) @error.func,
                
            (binary_expression
                operator: "or" @error.or.op
                right: (function_call
                    function: (bare_word) @error.or.func
                    (#match? @error.or.func "^(die|croak|confess)$"))) @error.or,
                
            (eval_expression
                block: (block) @error.eval.block) @error.eval,
                
            (use_statement
                module: (bare_word) @error.module
                (#match? @error.module "^(Try::Tiny|TryCatch)$")) @error.try
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "error_handling",
            "is_error_function": "error.func" in node["captures"],
            "is_or_die_pattern": "error.or" in node["captures"],
            "is_eval_block": "error.eval" in node["captures"],
            "is_try_module": "error.try" in node["captures"],
            "error_function": node["captures"].get("error.func.name", {}).get("text", ""),
            "uses_stacktrace": "error.func" in node["captures"] and node["captures"].get("error.func.name", {}).get("text", "") in ["confess", "cluck"],
            "error_handling_style": (
                "exception" if "error.func" in node["captures"] else
                "short_circuit" if "error.or" in node["captures"] else
                "try_catch" if "error.try" in node["captures"] else
                "eval" if "error.eval" in node["captures"] else
                "unknown"
            )
        }
    }
}

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
        "function": {
            "pattern": """
            [
                (subroutine_declaration
                    attributes: (attribute_list)? @syntax.function.attributes
                    name: [(bare_word) @syntax.function.name
                          (package_qualified_word) @syntax.function.qualified_name]
                    prototype: (prototype)? @syntax.function.prototype
                    signature: (signature)? @syntax.function.signature
                    body: (block) @syntax.function.body) @syntax.function.def,
                (anonymous_subroutine
                    attributes: (attribute_list)? @syntax.function.anon.attributes
                    body: (block) @syntax.function.anon.body) @syntax.function.anon
            ]
            """
        },
        "class": {
            "pattern": """
            [
                (package_statement
                    name: (package_qualified_word) @syntax.class.name
                    version: (version_number)? @syntax.class.version
                    block: (block)? @syntax.class.body) @syntax.class.def,
                (use_statement
                    module: (bare_word) @syntax.class.moose
                    (#match? @syntax.class.moose "^(Moose|Moo|Mouse)$")) @syntax.class.moose.use
            ]
            """
        }
    },
    
    "structure": {
        "namespace": {
            "pattern": """
            [
                (package_statement
                    name: (package_qualified_word) @structure.namespace.name
                    version: (version_number)? @structure.namespace.version) @structure.namespace,
                (block) @structure.namespace.block
            ]
            """
        },
        "import": {
            "pattern": """
            [
                (use_statement
                    module: (package_qualified_word) @structure.import.module
                    version: (version_number)? @structure.import.version
                    imports: (import_list)? @structure.import.list) @structure.import.use,
                (require_statement
                    module: (package_qualified_word) @structure.import.require.module
                    version: (version_number)? @structure.import.require.version) @structure.import.require
            ]
            """
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (scalar
                    sigil: "$" @semantics.var.scalar.sigil
                    name: (_) @semantics.var.scalar.name) @semantics.var.scalar,
                (array
                    sigil: "@" @semantics.var.array.sigil
                    name: (_) @semantics.var.array.name) @semantics.var.array,
                (hash
                    sigil: "%" @semantics.var.hash.sigil
                    name: (_) @semantics.var.hash.name) @semantics.var.hash
            ]
            """
        },
        "expression": [
            """
            (function_call
                name: (identifier) @name
                arguments: (argument_list)? @args) @expression
            """
        ]
    },
    
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (pod_statement) @documentation.pod
            ]
            """
        }
    },
    
    "REPOSITORY_LEARNING": PERL_PATTERNS_FOR_LEARNING
} 