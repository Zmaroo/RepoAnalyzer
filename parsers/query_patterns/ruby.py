"""Ruby-specific Tree-sitter patterns."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

RUBY_PATTERNS_FOR_LEARNING = {
    "metaprogramming": {
        "pattern": """
        [
            (call
                method: (identifier) @meta.def_method.name
                (#match? @meta.def_method.name "^define_method$")
                arguments: (argument_list
                    (_) @meta.def_method.method_name
                    (_)? @meta.def_method.block)) @meta.def_method,
                    
            (call
                method: (identifier) @meta.attr.name
                (#match? @meta.attr.name "^(attr_reader|attr_writer|attr_accessor)$")
                arguments: (argument_list
                    (symbol)* @meta.attr.symbols)) @meta.attr,
                    
            (method
                name: (identifier) @meta.method_missing.name
                (#match? @meta.method_missing.name "^method_missing$")
                parameters: (method_parameters
                    [(identifier) (rest_parameter) (optional_parameter)]* @meta.method_missing.params)
                body: (body_statement) @meta.method_missing.body) @meta.method_missing,
                
            (call
                method: (identifier) @meta.send.name
                (#match? @meta.send.name "^send$|^public_send$|^__send__$")
                arguments: (argument_list) @meta.send.args) @meta.send
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "metaprogramming",
            "is_define_method": "meta.def_method" in node["captures"],
            "is_attr_definition": "meta.attr" in node["captures"],
            "is_method_missing": "meta.method_missing" in node["captures"],
            "is_dynamic_dispatch": "meta.send" in node["captures"],
            "method_name": node["captures"].get("meta.def_method.method_name", {}).get("text", "") or 
                         node["captures"].get("meta.method_missing.name", {}).get("text", ""),
            "attr_type": node["captures"].get("meta.attr.name", {}).get("text", ""),
            "attr_symbols": node["captures"].get("meta.attr.symbols", {}).get("text", ""),
            "metaprogramming_type": (
                "dynamic_method_definition" if "meta.def_method" in node["captures"] else
                "attribute_definition" if "meta.attr" in node["captures"] else
                "method_missing" if "meta.method_missing" in node["captures"] else
                "dynamic_dispatch" if "meta.send" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "ruby_idioms": {
        "pattern": """
        [
            (block
                call: (call
                    method: (identifier) @idiom.block.method
                    (#match? @idiom.block.method "^(each|map|select|reject|reduce|inject|times|tap)$"))
                parameters: (block_parameters
                    [(identifier) (destructured_parameter)]* @idiom.block.params)
                body: (body_statement) @idiom.block.body) @idiom.block,
                
            (if_modifier
                condition: (_) @idiom.modifier.if.condition
                statement: (_) @idiom.modifier.if.statement) @idiom.modifier.if,
                
            (unless_modifier
                condition: (_) @idiom.modifier.unless.condition
                statement: (_) @idiom.modifier.unless.statement) @idiom.modifier.unless,
                
            (binary
                operator: (identifier) @idiom.op.name
                (#match? @idiom.op.name "^(\\|\\||&&|and|or)$")
                left: (_) @idiom.op.left
                right: (_) @idiom.op.right) @idiom.op
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "ruby_idioms",
            "is_block_usage": "idiom.block" in node["captures"],
            "is_modifier_if": "idiom.modifier.if" in node["captures"],
            "is_modifier_unless": "idiom.modifier.unless" in node["captures"],
            "is_short_circuit": "idiom.op" in node["captures"],
            "block_method": node["captures"].get("idiom.block.method", {}).get("text", ""),
            "param_count": len((node["captures"].get("idiom.block.params", {}).get("text", "") or "").split(","))
                          if node["captures"].get("idiom.block.params", {}).get("text", "") else 0,
            "operator": node["captures"].get("idiom.op.name", {}).get("text", ""),
            "idiomatic_construct": (
                "block_iteration" if "idiom.block" in node["captures"] else
                "statement_modifier" if ("idiom.modifier.if" in node["captures"] or "idiom.modifier.unless" in node["captures"]) else
                "short_circuit_evaluation" if "idiom.op" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "rails_patterns": {
        "pattern": """
        [
            (class
                name: (constant) @rails.class.name
                (#match? @rails.class.name ".*Controller$|.*Helper$|.*Mailer$|.*Job$|.*Model$|.*Serializer$")
                superclass: (superclass
                    name: (constant) @rails.class.superclass)
                body: (body_statement) @rails.class.body) @rails.class,
                
            (call
                receiver: (constant) @rails.assoc.receiver
                (#match? @rails.assoc.receiver "^(has_many|belongs_to|has_one|has_and_belongs_to_many)$")
                method: (identifier) @rails.assoc.method
                arguments: (argument_list
                    (_) @rails.assoc.args)) @rails.assoc,
                    
            (call
                receiver: (constant) @rails.validation.receiver
                (#match? @rails.validation.receiver "^validates$|^validate$")
                method: (identifier) @rails.validation.method
                arguments: (argument_list) @rails.validation.args) @rails.validation,
                
            (call
                method: (identifier) @rails.route.method
                (#match? @rails.route.method "^(resources|resource|get|post|put|patch|delete)$")
                arguments: (argument_list) @rails.route.args) @rails.route
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "rails_patterns",
            "is_rails_class": "rails.class" in node["captures"],
            "is_association": "rails.assoc" in node["captures"],
            "is_validation": "rails.validation" in node["captures"],
            "is_route": "rails.route" in node["captures"],
            "class_name": node["captures"].get("rails.class.name", {}).get("text", ""),
            "superclass": node["captures"].get("rails.class.superclass", {}).get("text", ""),
            "association_type": node["captures"].get("rails.assoc.receiver", {}).get("text", ""),
            "validation_method": node["captures"].get("rails.validation.method", {}).get("text", ""),
            "route_method": node["captures"].get("rails.route.method", {}).get("text", ""),
            "rails_component_type": (
                "controller" if "rails.class" in node["captures"] and "Controller" in node["captures"].get("rails.class.name", {}).get("text", "") else
                "model" if "rails.class" in node["captures"] and "Model" in node["captures"].get("rails.class.name", {}).get("text", "") else
                "model_association" if "rails.assoc" in node["captures"] else
                "model_validation" if "rails.validation" in node["captures"] else
                "routing" if "rails.route" in node["captures"] else
                "other_rails_component" if "rails.class" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (begin
                body: (body_statement) @error.begin.body
                [(rescue) (ensure)]* @error.begin.handler) @error.begin,
                
            (rescue
                exceptions: (exceptions
                    [(constant) (scope_resolution) (array)]* @error.rescue.exceptions)?
                exception_variable: (exception_variable
                    name: (identifier) @error.rescue.variable)?
                body: (body_statement) @error.rescue.body) @error.rescue,
                
            (ensure
                body: (body_statement) @error.ensure.body) @error.ensure,
                
            (raise
                expression: (_)? @error.raise.expr) @error.raise
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "error_handling",
            "is_begin_block": "error.begin" in node["captures"],
            "is_rescue": "error.rescue" in node["captures"],
            "is_ensure": "error.ensure" in node["captures"],
            "is_raise": "error.raise" in node["captures"],
            "exception_types": node["captures"].get("error.rescue.exceptions", {}).get("text", ""),
            "exception_variable": node["captures"].get("error.rescue.variable", {}).get("text", ""),
            "raise_expression": node["captures"].get("error.raise.expr", {}).get("text", ""),
            "error_handling_pattern": (
                "begin_rescue_ensure" if "error.begin" in node["captures"] else
                "standalone_rescue" if "error.rescue" in node["captures"] else
                "standalone_ensure" if "error.ensure" in node["captures"] else
                "raise" if "error.raise" in node["captures"] else
                "unknown"
            )
        }
    }
}

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
    },
    
    "REPOSITORY_LEARNING": RUBY_PATTERNS_FOR_LEARNING
} 