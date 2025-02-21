"""Ruby-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

RUBY_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (method
                    name: (identifier) @syntax.function.name
                    parameters: (method_parameters
                        [(identifier) @syntax.function.param.name
                         (optional_parameter
                             name: (identifier) @syntax.function.param.optional.name
                             value: (_) @syntax.function.param.optional.default)
                         (rest_parameter
                             name: (identifier) @syntax.function.param.rest.name)
                         (keyword_parameter
                             name: (identifier) @syntax.function.param.keyword.name
                             value: (_)? @syntax.function.param.keyword.default)
                         (hash_splat_parameter
                             name: (identifier) @syntax.function.param.kwargs.name)]*) @syntax.function.params
                    body: (body_statement) @syntax.function.body) @syntax.function.def,
                
                (singleton_method
                    object: (_) @syntax.function.singleton.object
                    name: (identifier) @syntax.function.singleton.name
                    parameters: (method_parameters)? @syntax.function.singleton.params
                    body: (body_statement) @syntax.function.singleton.body) @syntax.function.singleton
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                       node["captures"].get("syntax.function.singleton.name", {}).get("text", ""),
                "params": [p.get("text", "") for p in node["captures"].get("syntax.function.param.name", [])]
            }
        },
        
        "class": {
            "pattern": """
            [
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
                
                (module
                    name: (constant) @syntax.module.name
                    body: (body_statement) @syntax.module.body) @syntax.module.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.class.name", {}).get("text", "") or
                       node["captures"].get("syntax.module.name", {}).get("text", ""),
                "kind": "class" if "syntax.class.def" in node["captures"] else "module"
            }
        }
    },
    
    "semantics": {
        "meta": {
            "pattern": """
            [
                (method
                    name: (identifier) @semantics.meta.method_missing
                    (#match? @semantics.meta.method_missing "^method_missing$")) @semantics.meta.method_missing.def,
                
                (call
                    method: (identifier) @semantics.meta.define_method
                    (#match? @semantics.meta.define_method "^define_method$")
                    arguments: (argument_list
                        name: (_) @semantics.meta.define_method.name
                        block: (block) @semantics.meta.define_method.body)) @semantics.meta.define_method.call,
                
                (call
                    method: [(identifier) (constant)]
                    (#match? @method "^(attr_reader|attr_writer|attr_accessor)$")
                    arguments: (argument_list
                        (_)* @semantics.meta.attr.name)) @semantics.meta.attr
            ]
            """,
            "extract": lambda node: {
                "type": ("method_missing" if "semantics.meta.method_missing" in node["captures"] else
                        "define_method" if "semantics.meta.define_method" in node["captures"] else
                        "attr")
            }
        },
        
        "block": {
            "pattern": """
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
            "extract": lambda node: {
                "params": [p.get("text", "") for p in node["captures"].get("semantics.block.param.name", [])]
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment,
                
                (comment
                    text: /^#\\s*@.*/) @documentation.rdoc.directive,
                
                (comment
                    text: /^#\\s*@[a-zA-Z]+.*/) @documentation.yard.tag
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                "type": ("rdoc" if "documentation.rdoc.directive" in node["captures"] else
                        "yard" if "documentation.yard.tag" in node["captures"] else
                        "comment")
            }
        }
    },
    
    "structure": {
        "module": {
            "pattern": """
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
            "extract": lambda node: {
                "name": node["captures"].get("structure.module.name", {}).get("text", ""),
                "requires": [r.get("text", "") for r in node["captures"].get("structure.require.name", [])]
            }
        }
    }
} 