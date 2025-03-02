"""Rust-specific Tree-sitter patterns."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

RUST_PATTERNS_FOR_LEARNING = {
    "ownership_patterns": {
        "pattern": """
        [
            (reference_expression
                reference_type: "#ref_type" @ownership.ref.type
                (#is? @ownership.ref.type "&mut" "&")) @ownership.ref,
                
            (parameter
                pattern: (_) @ownership.param.name
                type: [(reference_type) (mutable_reference_type)] @ownership.param.ref_type) @ownership.param,
                
            (move_expression
                arguments: (_) @ownership.move.args
                body: (_) @ownership.move.body) @ownership.move,
                
            (let_declaration
                pattern: (_) @ownership.let.pattern
                value: (_) @ownership.let.value
                (#match? @ownership.let.value ".*(clone|to_owned)\\(\\)")) @ownership.let.clone
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "ownership_patterns",
            "is_reference": "ownership.ref" in node["captures"],
            "is_reference_parameter": "ownership.param" in node["captures"],
            "is_move_closure": "ownership.move" in node["captures"],
            "is_clone": "ownership.let.clone" in node["captures"],
            "ref_type": node["captures"].get("ownership.ref.type", {}).get("text", ""),
            "param_ref_type": node["captures"].get("ownership.param.ref_type", {}).get("text", ""),
            "ownership_pattern": (
                "immutable_borrow" if "ownership.ref" in node["captures"] and "&" in node["captures"].get("ownership.ref.type", {}).get("text", "") else
                "mutable_borrow" if "ownership.ref" in node["captures"] and "&mut" in node["captures"].get("ownership.ref.type", {}).get("text", "") else
                "ref_parameter" if "ownership.param" in node["captures"] else
                "move_closure" if "ownership.move" in node["captures"] else
                "clone" if "ownership.let.clone" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "error_handling": {
        "pattern": """
        [
            (try_expression
                expression: (_) @error.try.expr) @error.try,
                
            (result_type
                success_type: (_) @error.result.ok
                error_type: (_) @error.result.err) @error.result,
                
            (match_expression
                value: [(try_expression) (call_expression)] @error.match.value
                arms: (match_arms
                    (match_arm
                        pattern: (_) @error.match.pattern)) @error.match.arms) @error.match,
                
            (macro_invocation
                path: (identifier) @error.macro.name
                (#match? @error.macro.name "^(panic|unreachable|unimplemented)$")) @error.macro
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "error_handling",
            "is_try_operator": "error.try" in node["captures"],
            "is_result_type": "error.result" in node["captures"],
            "is_error_match": "error.match" in node["captures"],
            "is_panic_macro": "error.macro" in node["captures"],
            "try_expression": node["captures"].get("error.try.expr", {}).get("text", ""),
            "ok_type": node["captures"].get("error.result.ok", {}).get("text", ""),
            "err_type": node["captures"].get("error.result.err", {}).get("text", ""),
            "macro_name": node["captures"].get("error.macro.name", {}).get("text", ""),
            "error_pattern": (
                "try_operator" if "error.try" in node["captures"] else
                "result_type" if "error.result" in node["captures"] else
                "match_error_handling" if "error.match" in node["captures"] else
                "panic" if "error.macro" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "concurrency_patterns": {
        "pattern": """
        [
            (call_expression
                function: (field_expression
                    field: (field_identifier) @concur.thread.field
                    (#match? @concur.thread.field "^spawn$")) @concur.thread.expr
                arguments: (arguments) @concur.thread.args) @concur.thread,
                
            (call_expression
                function: (field_expression
                    field: (field_identifier) @concur.async.field
                    (#match? @concur.async.field "^(await|then|and_then|map|map_err)$")) @concur.async.expr) @concur.async,
                
            (macro_invocation
                path: (identifier) @concur.sync.name
                (#match? @concur.sync.name "^(mutex|lock|arc)$")) @concur.sync,
                
            (trait_item
                name: (identifier) @concur.trait.name
                (#match? @concur.trait.name "^(Send|Sync)$")) @concur.trait
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "concurrency_patterns",
            "is_threading": "concur.thread" in node["captures"],
            "is_async": "concur.async" in node["captures"],
            "is_sync_primitive": "concur.sync" in node["captures"],
            "is_concurrency_trait": "concur.trait" in node["captures"],
            "thread_function": node["captures"].get("concur.thread.field", {}).get("text", ""),
            "async_function": node["captures"].get("concur.async.field", {}).get("text", ""),
            "sync_primitive": node["captures"].get("concur.sync.name", {}).get("text", ""),
            "trait_name": node["captures"].get("concur.trait.name", {}).get("text", ""),
            "concurrency_pattern": (
                "threading" if "concur.thread" in node["captures"] else
                "async_await" if "concur.async" in node["captures"] and node["captures"].get("concur.async.field", {}).get("text", "") == "await" else
                "future_combinators" if "concur.async" in node["captures"] else
                "sync_primitives" if "concur.sync" in node["captures"] else
                "concurrency_traits" if "concur.trait" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "type_safety": {
        "pattern": """
        [
            (generic_type
                type: (_) @type.generic.base
                type_arguments: (type_arguments) @type.generic.args) @type.generic,
                
            (trait_bounds
                bounds: (type_bound_list) @type.trait.bounds) @type.trait,
                
            (where_clause
                predicates: (where_predicate_list) @type.where.predicates) @type.where,
                
            (type_cast_expression
                value: (_) @type.cast.value
                type: (_) @type.cast.type) @type.cast
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "type_safety",
            "is_generic": "type.generic" in node["captures"],
            "is_trait_bounds": "type.trait" in node["captures"],
            "is_where_clause": "type.where" in node["captures"],
            "is_type_cast": "type.cast" in node["captures"],
            "generic_base": node["captures"].get("type.generic.base", {}).get("text", ""),
            "generic_args": node["captures"].get("type.generic.args", {}).get("text", ""),
            "trait_bounds": node["captures"].get("type.trait.bounds", {}).get("text", ""),
            "where_predicates": node["captures"].get("type.where.predicates", {}).get("text", ""),
            "cast_type": node["captures"].get("type.cast.type", {}).get("text", ""),
            "type_safety_pattern": (
                "generic_type" if "type.generic" in node["captures"] else
                "trait_bounds" if "type.trait" in node["captures"] else
                "where_clause" if "type.where" in node["captures"] else
                "type_cast" if "type.cast" in node["captures"] else
                "unknown"
            )
        }
    }
}

RUST_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
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
                
                (impl_item
                    attributes: (attribute_item)* @syntax.function.impl.attributes
                    visibility: (visibility_modifier)? @syntax.function.impl.visibility
                    qualifiers: [(async) (const) (unsafe)]* @syntax.function.impl.qualifier
                    name: (identifier) @syntax.function.impl.name) @syntax.function.impl
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "visibility": node["captures"].get("syntax.function.visibility", {}).get("text", ""),
                "qualifiers": [q.text.decode('utf8') for q in node["captures"].get("syntax.function.qualifier", [])]
            }
        },
        "type": {
            "pattern": """
            [
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
            "extract": lambda node: {
                "name": node["captures"].get("syntax.type.struct.name", {}).get("text", "") or
                       node["captures"].get("syntax.type.enum.name", {}).get("text", "") or
                       node["captures"].get("syntax.type.trait.name", {}).get("text", ""),
                "kind": ("struct" if "syntax.type.struct.name" in node["captures"] else
                        "enum" if "syntax.type.enum.name" in node["captures"] else
                        "trait")
            }
        }
    },
    
    "semantics": {
        "type_system": {
            "pattern": """
            [
                (lifetime
                    name: (_) @semantics.lifetime.name) @semantics.lifetime,
                
                (lifetime_constraint
                    lifetime: (lifetime) @semantics.lifetime.constraint.lifetime
                    bounds: (lifetime)+ @semantics.lifetime.constraint.bounds) @semantics.lifetime.constraint,
                
                (result_type
                    success_type: (_) @semantics.error.result.ok
                    error_type: (_) @semantics.error.result.err) @semantics.error.result,
                
                (match_expression
                    value: (try_expression) @semantics.error.try
                    arms: (match_arm
                        pattern: (or_pattern
                            (pattern) @semantics.error.match.pattern)
                        expression: (block) @semantics.error.match.block)*) @semantics.error.match
            ]
            """,
            "extract": lambda node: {
                "lifetime": node["captures"].get("semantics.lifetime.name", {}).get("text", ""),
                "error_handling": "try" if "semantics.error.try" in node["captures"] else
                                "result" if "semantics.error.result" in node["captures"] else None
            }
        },
        "macro": {
            "pattern": """
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
            "extract": lambda node: {
                "name": node["captures"].get("semantics.macro.name", {}).get("text", "") or
                       node["captures"].get("semantics.macro.call.name", {}).get("text", ""),
                "kind": "definition" if "semantics.macro.name" in node["captures"] else "invocation"
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (line_comment) @documentation.comment {
                    match: "^//[!/]"
                },
                
                (attribute_item
                    path: (identifier) @documentation.attr.name
                    (#match? @documentation.attr.name "^doc$")
                    arguments: (token_tree) @documentation.attr.args) @documentation.attr
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                "is_doc_comment": bool(node["captures"].get("documentation.attr.name", None))
            }
        }
    },
    
    "structure": {
        "module": {
            "pattern": """
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
            "extract": lambda node: {
                "name": node["captures"].get("structure.module.name", {}).get("text", ""),
                "visibility": node["captures"].get("structure.module.visibility", {}).get("text", ""),
                "imports": [p.text.decode('utf8') for p in node["captures"].get("structure.use.path", [])]
            }
        }
    },
    
    "REPOSITORY_LEARNING": RUST_PATTERNS_FOR_LEARNING
} 