"""
Query patterns for Scala files.
"""

from .common import COMMON_PATTERNS

SCALA_PATTERNS_FOR_LEARNING = {
    "functional_programming": {
        "pattern": """
        [
            (function_definition
                name: (identifier) @fp.function.name
                parameters: (parameters)? @fp.function.params
                body: (_) @fp.function.body) @fp.function,
                
            (call_expression
                function: [
                    (identifier) @fp.call.func.id
                    (field_expression 
                        field: (identifier) @fp.call.func.field)
                ]
                arguments: (arguments
                    (_)+ @fp.call.args.exp) @fp.call.args
                (#match? @fp.call.func.id "^(map|flatMap|filter|fold|reduce|collect|foreach)$" @fp.call.func.field)) @fp.call,
                
            (lambda_expression
                parameters: (_) @fp.lambda.params
                body: (_) @fp.lambda.body) @fp.lambda,
                
            (pattern_match
                value: (_) @fp.match.value
                cases: (case_block)+ @fp.match.cases) @fp.match,
                
            (infix_expression
                left: (_) @fp.infix.left
                operator: (_) @fp.infix.op
                right: (_) @fp.infix.right) @fp.infix
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional_programming",
            "is_function_def": "fp.function" in node["captures"],
            "is_higher_order_call": "fp.call" in node["captures"],
            "is_lambda": "fp.lambda" in node["captures"],
            "is_pattern_match": "fp.match" in node["captures"],
            "is_infix_operation": "fp.infix" in node["captures"],
            "function_name": node["captures"].get("fp.function.name", {}).get("text", ""),
            "higher_order_func": (
                node["captures"].get("fp.call.func.id", {}).get("text", "") or 
                node["captures"].get("fp.call.func.field", {}).get("text", "")
            ),
            "infix_operator": node["captures"].get("fp.infix.op", {}).get("text", ""),
            "functional_pattern": (
                "function_definition" if "fp.function" in node["captures"] else
                "higher_order_function" if "fp.call" in node["captures"] else
                "lambda_expression" if "fp.lambda" in node["captures"] else
                "pattern_matching" if "fp.match" in node["captures"] else
                "infix_operation" if "fp.infix" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "object_oriented": {
        "pattern": """
        [
            (class_definition
                name: (identifier) @oo.class.name
                type_parameters: (type_parameters)? @oo.class.type_params
                parameters: (parameters)? @oo.class.params
                extends: (extends_clause)? @oo.class.extends
                body: (template_body)? @oo.class.body) @oo.class,
                
            (object_definition
                name: (identifier) @oo.object.name
                extends: (extends_clause)? @oo.object.extends
                body: (template_body)? @oo.object.body) @oo.object,
                
            (trait_definition
                name: (identifier) @oo.trait.name
                type_parameters: (type_parameters)? @oo.trait.type_params
                extends: (extends_clause)? @oo.trait.extends
                body: (template_body)? @oo.trait.body) @oo.trait,
                
            (method_definition
                annotations: (annotation)* @oo.method.annotations
                modifiers: (modifier)* @oo.method.modifiers
                name: (identifier) @oo.method.name
                type_parameters: (type_parameters)? @oo.method.type_params
                parameters: (parameters)? @oo.method.params
                return_type: (_)? @oo.method.return_type
                body: (_)? @oo.method.body) @oo.method
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "object_oriented",
            "is_class": "oo.class" in node["captures"],
            "is_object": "oo.object" in node["captures"],
            "is_trait": "oo.trait" in node["captures"],
            "is_method": "oo.method" in node["captures"],
            "name": (
                node["captures"].get("oo.class.name", {}).get("text", "") or
                node["captures"].get("oo.object.name", {}).get("text", "") or
                node["captures"].get("oo.trait.name", {}).get("text", "") or
                node["captures"].get("oo.method.name", {}).get("text", "")
            ),
            "has_inheritance": (
                "oo.class.extends" in node["captures"] or
                "oo.object.extends" in node["captures"] or
                "oo.trait.extends" in node["captures"]
            ),
            "modifiers": [mod.text.decode('utf8') for mod in node["captures"].get("oo.method.modifiers", [])],
            "oo_pattern": (
                "class_definition" if "oo.class" in node["captures"] else
                "object_definition" if "oo.object" in node["captures"] else
                "trait_definition" if "oo.trait" in node["captures"] else
                "method_definition" if "oo.method" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "type_system": {
        "pattern": """
        [
            (type_definition
                name: (identifier) @type.def.name
                type_parameters: (type_parameters)? @type.def.params
                body: (_) @type.def.body) @type.def,
                
            (function_definition
                type_parameters: (type_parameters
                    (type_parameter
                        name: (identifier) @type.func.param.name
                        bounds: (_)? @type.func.param.bounds)*) @type.func.params) @type.func,
                
            (implicit_parameter
                name: (identifier) @type.implicit.name
                type: (_) @type.implicit.type) @type.implicit,
                
            (type_class_definition
                name: (identifier) @type.class.name
                type_parameters: (type_parameters)? @type.class.params
                body: (_) @type.class.body) @type.class,
                
            (infix_type
                left: (_) @type.infix.left
                operator: (_) @type.infix.op
                right: (_) @type.infix.right) @type.infix
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "type_system",
            "is_type_def": "type.def" in node["captures"],
            "is_generic_function": "type.func.params" in node["captures"],
            "is_implicit_param": "type.implicit" in node["captures"],
            "is_type_class": "type.class" in node["captures"],
            "is_type_operator": "type.infix" in node["captures"],
            "name": (
                node["captures"].get("type.def.name", {}).get("text", "") or
                node["captures"].get("type.class.name", {}).get("text", "") or
                node["captures"].get("type.implicit.name", {}).get("text", "")
            ),
            "type_param_names": [param.text.decode('utf8') for param in node["captures"].get("type.func.param.name", [])],
            "type_infix_op": node["captures"].get("type.infix.op", {}).get("text", ""),
            "type_system_pattern": (
                "type_definition" if "type.def" in node["captures"] else
                "generic_function" if "type.func.params" in node["captures"] else
                "implicit_parameter" if "type.implicit" in node["captures"] else
                "type_class" if "type.class" in node["captures"] else
                "type_operator" if "type.infix" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "concurrency": {
        "pattern": """
        [
            (call_expression
                function: [
                    (identifier) @concur.call.func.id
                    (field_expression 
                        field: (identifier) @concur.call.func.field)
                ]
                (#match? @concur.call.func.id "^(Future|Promise|async|Await|blocking)$" @concur.call.func.field)) @concur.future,
                
            (import_declaration
                importers: (import_importers
                    (importer
                        name: (_) @concur.import.name
                        (#match? @concur.import.name ".*\\.concurrent.*")))) @concur.import,
                
            (call_expression
                function: [
                    (identifier) @concur.actor.id
                    (field_expression 
                        field: (identifier) @concur.actor.field)
                ]
                (#match? @concur.actor.id "^(Actor|Props|ActorRef)$" @concur.actor.field)) @concur.actor,
                
            (call_expression
                function: [
                    (identifier) @concur.stream.id
                    (field_expression 
                        field: (identifier) @concur.stream.field)
                ]
                (#match? @concur.stream.id "^(Source|Flow|Sink|RunnableGraph)$" @concur.stream.field)) @concur.stream
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "concurrency",
            "is_future": "concur.future" in node["captures"],
            "is_concurrent_import": "concur.import" in node["captures"],
            "is_actor": "concur.actor" in node["captures"],
            "is_stream": "concur.stream" in node["captures"],
            "future_function": (
                node["captures"].get("concur.call.func.id", {}).get("text", "") or 
                node["captures"].get("concur.call.func.field", {}).get("text", "")
            ),
            "actor_function": (
                node["captures"].get("concur.actor.id", {}).get("text", "") or 
                node["captures"].get("concur.actor.field", {}).get("text", "")
            ),
            "stream_function": (
                node["captures"].get("concur.stream.id", {}).get("text", "") or 
                node["captures"].get("concur.stream.field", {}).get("text", "")
            ),
            "concurrent_import": node["captures"].get("concur.import.name", {}).get("text", ""),
            "concurrency_pattern": (
                "future_promise" if "concur.future" in node["captures"] else
                "concurrent_import" if "concur.import" in node["captures"] else
                "actor_model" if "concur.actor" in node["captures"] else
                "streaming" if "concur.stream" in node["captures"] else
                "unknown"
            )
        }
    }
}

SCALA_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    modifiers: [(annotation) (modifier)]* @syntax.function.modifier
                    name: (identifier) @syntax.function.name
                    type_parameters: (type_parameters
                        (type_parameter
                            name: (identifier) @syntax.function.type_param.name
                            bounds: (upper_bound)? @syntax.function.type_param.bound)*)? @syntax.function.type_params
                    parameters: (parameters
                        [(parameter
                            name: (identifier) @syntax.function.param.name
                            type: (_) @syntax.function.param.type
                            default: (_)? @syntax.function.param.default)
                         (implicit_parameter
                            name: (identifier) @syntax.function.param.implicit.name
                            type: (_) @syntax.function.param.implicit.type)]*) @syntax.function.params
                    return_type: (_)? @syntax.function.return_type
                    body: (_) @syntax.function.body) @syntax.function.def,
                
                (method_definition
                    modifiers: [(annotation) (modifier)]* @syntax.method.modifier
                    name: (identifier) @syntax.method.name
                    type_parameters: (type_parameters)? @syntax.method.type_params
                    parameters: (parameters)? @syntax.method.params
                    return_type: (_)? @syntax.method.return_type
                    body: (_) @syntax.method.body) @syntax.method.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                       node["captures"].get("syntax.method.name", {}).get("text", ""),
                "modifiers": [m.text.decode('utf8') for m in 
                            node["captures"].get("syntax.function.modifier", []) +
                            node["captures"].get("syntax.method.modifier", [])]
            }
        },
        
        "class": {
            "pattern": """
            [
                (class_definition
                    modifiers: [(annotation) (modifier)]* @syntax.class.modifier
                    name: (identifier) @syntax.class.name
                    type_parameters: (type_parameters
                        (type_parameter
                            name: (identifier) @syntax.class.type_param.name
                            bounds: [(upper_bound) (lower_bound)]? @syntax.class.type_param.bound)*)? @syntax.class.type_params
                    constructor_parameters: (parameters)? @syntax.class.constructor_params
                    extends_clause: (extends_clause)? @syntax.class.extends
                    body: (_)? @syntax.class.body) @syntax.class.def,
                
                (object_definition
                    modifiers: [(annotation) (modifier)]* @syntax.object.modifier
                    name: (identifier) @syntax.object.name
                    extends_clause: (extends_clause)? @syntax.object.extends
                    body: (_)? @syntax.object.body) @syntax.object.def,
                
                (trait_definition
                    modifiers: [(annotation) (modifier)]* @syntax.trait.modifier
                    name: (identifier) @syntax.trait.name
                    type_parameters: (type_parameters)? @syntax.trait.type_params
                    extends_clause: (extends_clause)? @syntax.trait.extends
                    body: (_)? @syntax.trait.body) @syntax.trait.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.class.name", {}).get("text", "") or
                       node["captures"].get("syntax.object.name", {}).get("text", "") or
                       node["captures"].get("syntax.trait.name", {}).get("text", ""),
                "kind": ("class" if "syntax.class.def" in node["captures"] else
                        "object" if "syntax.object.def" in node["captures"] else
                        "trait")
            }
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (val_definition
                    modifiers: [(annotation) (modifier)]* @semantics.val.modifier
                    pattern: (identifier) @semantics.val.name
                    type: (_)? @semantics.val.type
                    value: (_) @semantics.val.value) @semantics.val.def,
                
                (var_definition
                    modifiers: [(annotation) (modifier)]* @semantics.var.modifier
                    pattern: (identifier) @semantics.var.name
                    type: (_)? @semantics.var.type
                    value: (_) @semantics.var.value) @semantics.var.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.val.name", {}).get("text", "") or
                       node["captures"].get("semantics.var.name", {}).get("text", ""),
                "kind": "val" if "semantics.val.def" in node["captures"] else "var"
            }
        },
        
        "type": {
            "pattern": """
            [
                (type_definition
                    modifiers: [(annotation) (modifier)]* @semantics.type.modifier
                    name: (identifier) @semantics.type.name
                    type_parameters: (type_parameters)? @semantics.type.params
                    type: (_) @semantics.type.value) @semantics.type.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                "modifiers": [m.text.decode('utf8') for m in node["captures"].get("semantics.type.modifier", [])]
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (doc_comment) @documentation.doc,
                (comment) @documentation.comment,
                (block_comment) @documentation.block
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.doc", {}).get("text", "") or
                       node["captures"].get("documentation.comment", {}).get("text", "") or
                       node["captures"].get("documentation.block", {}).get("text", "")
            }
        }
    },
    
    "structure": {
        "module": {
            "pattern": """
            [
                (package_clause
                    name: (identifier) @structure.package.name) @structure.package,
                
                (import_declaration
                    importers: (import_importers
                        (importer
                            name: (_) @structure.import.name
                            selector: (import_selector)? @structure.import.selector))) @structure.import
            ]
            """,
            "extract": lambda node: {
                "package": node["captures"].get("structure.package.name", {}).get("text", ""),
                "imports": [imp.get("text", "") for imp in node["captures"].get("structure.import.name", [])]
            }
        }
    },
    
    "REPOSITORY_LEARNING": SCALA_PATTERNS_FOR_LEARNING
} 