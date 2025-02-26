"""TypeScript-specific Tree-sitter patterns."""

from parsers.types import FileType
from .js_ts_shared import JS_TS_SHARED_PATTERNS

TYPESCRIPT_PATTERNS_FOR_LEARNING = {
    "type_system": {
        "pattern": """
        [
            (interface_declaration
                name: (type_identifier) @type.interface.name
                type_parameters: (type_parameters
                    (type_parameter
                        name: (type_identifier) @type.interface.generic.param
                        constraint: (_)? @type.interface.generic.constraint
                        value: (_)? @type.interface.generic.default)* @type.interface.generic.params)? @type.interface.generics
                extends: (extends_type_clause
                    (type_reference)+ @type.interface.extends)? @type.interface.extends_clause
                body: (interface_body) @type.interface.body) @type.interface,
                
            (type_alias_declaration
                name: (type_identifier) @type.alias.name
                type_parameters: (type_parameters)? @type.alias.generics
                value: [(object_type) (union_type) (intersection_type) (function_type)] @type.alias.value) @type.alias,
                
            (enum_declaration
                name: (identifier) @type.enum.name
                body: (enum_body
                    (enum_member
                        name: (property_identifier) @type.enum.member)* @type.enum.members) @type.enum.body) @type.enum,
                
            (method_signature
                name: (property_identifier) @type.func_sig.name
                parameters: (formal_parameters
                    (required_parameter
                        name: (_) @type.func_sig.param.name
                        type: (type_annotation) @type.func_sig.param.type)* @type.func_sig.params)
                return_type: (type_annotation) @type.func_sig.return) @type.func_sig
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "type_system",
            "is_interface": "type.interface" in node["captures"],
            "is_type_alias": "type.alias" in node["captures"],
            "is_enum": "type.enum" in node["captures"],
            "is_function_signature": "type.func_sig" in node["captures"],
            "type_name": (
                node["captures"].get("type.interface.name", {}).get("text", "") or
                node["captures"].get("type.alias.name", {}).get("text", "") or
                node["captures"].get("type.enum.name", {}).get("text", "") or
                node["captures"].get("type.func_sig.name", {}).get("text", "")
            ),
            "is_generic": (
                "type.interface.generics" in node["captures"] and node["captures"].get("type.interface.generics", {}).get("text", "") != "" or
                "type.alias.generics" in node["captures"] and node["captures"].get("type.alias.generics", {}).get("text", "") != ""
            ),
            "extends_types": [ext.get("text", "") for ext in node["captures"].get("type.interface.extends", [])],
            "enum_members": [member.get("text", "") for member in node["captures"].get("type.enum.member", [])],
            "type_kind": (
                "interface" if "type.interface" in node["captures"] else
                "type_alias" if "type.alias" in node["captures"] else
                "enum" if "type.enum" in node["captures"] else
                "function_signature" if "type.func_sig" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "advanced_types": {
        "pattern": """
        [
            (union_type
                (_)+ @adv.union.member) @adv.union,
                
            (intersection_type
                (_)+ @adv.intersection.member) @adv.intersection,
                
            (conditional_type
                check: (_) @adv.conditional.check
                extends: (_) @adv.conditional.extends
                true_type: (_) @adv.conditional.true
                false_type: (_) @adv.conditional.false) @adv.conditional,
                
            (mapped_type
                parameter: (type_parameter
                    name: (type_identifier) @adv.mapped.param.name
                    constraint: (_) @adv.mapped.param.constraint) @adv.mapped.param
                type: (_) @adv.mapped.type) @adv.mapped,
                
            (index_signature
                name: (identifier) @adv.index.name
                type: (type_annotation
                    type: (_) @adv.index.key_type) @adv.index.key
                value_type: (type_annotation
                    type: (_) @adv.index.value_type) @adv.index.value) @adv.index,
                
            (lookup_type
                object: (_) @adv.lookup.object
                index: (_) @adv.lookup.index) @adv.lookup
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "advanced_types",
            "is_union": "adv.union" in node["captures"],
            "is_intersection": "adv.intersection" in node["captures"],
            "is_conditional": "adv.conditional" in node["captures"],
            "is_mapped": "adv.mapped" in node["captures"],
            "is_index_signature": "adv.index" in node["captures"],
            "is_lookup": "adv.lookup" in node["captures"],
            "union_members": [member.get("text", "") for member in node["captures"].get("adv.union.member", [])],
            "intersection_members": [member.get("text", "") for member in node["captures"].get("adv.intersection.member", [])],
            "conditional_check": node["captures"].get("adv.conditional.check", {}).get("text", ""),
            "conditional_true": node["captures"].get("adv.conditional.true", {}).get("text", ""),
            "conditional_false": node["captures"].get("adv.conditional.false", {}).get("text", ""),
            "mapped_param": node["captures"].get("adv.mapped.param.name", {}).get("text", ""),
            "index_key_type": node["captures"].get("adv.index.key_type", {}).get("text", ""),
            "index_value_type": node["captures"].get("adv.index.value_type", {}).get("text", ""),
            "lookup_object": node["captures"].get("adv.lookup.object", {}).get("text", ""),
            "lookup_index": node["captures"].get("adv.lookup.index", {}).get("text", ""),
            "type_kind": (
                "union" if "adv.union" in node["captures"] else
                "intersection" if "adv.intersection" in node["captures"] else
                "conditional" if "adv.conditional" in node["captures"] else
                "mapped" if "adv.mapped" in node["captures"] else
                "index_signature" if "adv.index" in node["captures"] else
                "lookup" if "adv.lookup" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "type_manipulations": {
        "pattern": """
        [
            (generic_type
                name: (type_identifier) @util.type.name {
                    match: "^(Partial|Required|Readonly|Pick|Omit|Extract|Exclude|Parameters|ReturnType|InstanceType|ThisType|Record)$"
                }
                type_arguments: (type_arguments
                    (_)+ @util.type.arg) @util.type.args) @util.type,
                
            (property_signature
                readonly: "readonly"? @manip.readonly
                name: (property_identifier) @manip.prop.name
                optional: "?"? @manip.optional
                type: (type_annotation
                    type: (_) @manip.prop.type) @manip.prop.annotation) @manip.prop,
                
            (generic_type
                name: (type_identifier) @manip.generic.name
                type_arguments: (type_arguments
                    (_)+ @manip.generic.arg) @manip.generic.args) @manip.generic,
                
            (type_predicate
                 name: (identifier) @manip.predicate.name
                 type: (type_annotation)? @manip.predicate.type) @manip.predicate
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "type_manipulations",
            "is_utility_type": "util.type" in node["captures"],
            "is_property_signature": "manip.prop" in node["captures"],
            "is_generic_type": "manip.generic" in node["captures"],
            "is_type_predicate": "manip.predicate" in node["captures"],
            "utility_name": node["captures"].get("util.type.name", {}).get("text", ""),
            "utility_args": [arg.get("text", "") for arg in node["captures"].get("util.type.arg", [])],
            "property_name": node["captures"].get("manip.prop.name", {}).get("text", ""),
            "property_type": node["captures"].get("manip.prop.type", {}).get("text", ""),
            "is_readonly": "manip.readonly" in node["captures"] and node["captures"].get("manip.readonly", {}).get("text", "") != "",
            "is_optional": "manip.optional" in node["captures"] and node["captures"].get("manip.optional", {}).get("text", "") != "",
            "generic_name": node["captures"].get("manip.generic.name", {}).get("text", ""),
            "generic_args": [arg.get("text", "") for arg in node["captures"].get("manip.generic.arg", [])],
            "predicate_name": node["captures"].get("manip.predicate.name", {}).get("text", ""),
            "manipulation_type": (
                "utility_type" if "util.type" in node["captures"] else
                "property_signature" if "manip.prop" in node["captures"] else
                "generic_type" if "manip.generic" in node["captures"] else
                "type_predicate" if "manip.predicate" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "decorators": {
        "pattern": """
        [
            (decorator
                name: (identifier) @decorator.name
                arguments: (arguments
                    (_)* @decorator.arg) @decorator.args) @decorator,
                
            (class_declaration
                decorators: (decorator)+ @class.decorators
                name: (identifier) @class.name) @class.decorated,
                
            (method_definition
                decorators: (decorator)+ @method.decorators
                name: (property_identifier) @method.name) @method.decorated,
                
            (property_definition
                decorators: (decorator)+ @property.decorators
                name: (property_identifier) @property.name) @property.decorated,
                
            (parameter
                decorators: (decorator)+ @param.decorators
                name: (identifier) @param.name) @param.decorated
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "decorators",
            "is_decorator": "decorator" in node["captures"],
            "is_decorated_class": "class.decorated" in node["captures"],
            "is_decorated_method": "method.decorated" in node["captures"],
            "is_decorated_property": "property.decorated" in node["captures"],
            "is_decorated_parameter": "param.decorated" in node["captures"],
            "decorator_name": node["captures"].get("decorator.name", {}).get("text", ""),
            "decorated_name": (
                node["captures"].get("class.name", {}).get("text", "") or
                node["captures"].get("method.name", {}).get("text", "") or
                node["captures"].get("property.name", {}).get("text", "") or
                node["captures"].get("param.name", {}).get("text", "")
            ),
            "has_args": "decorator.args" in node["captures"] and len([arg for arg in node["captures"].get("decorator.arg", [])]) > 0,
            "decorator_target": (
                "class" if "class.decorated" in node["captures"] else
                "method" if "method.decorated" in node["captures"] else
                "property" if "property.decorated" in node["captures"] else
                "parameter" if "param.decorated" in node["captures"] else
                "unknown" if "decorator" in node["captures"] else
                "unknown"
            )
        }
    }
}

TYPESCRIPT_PATTERNS = {
    **JS_TS_SHARED_PATTERNS,  # Include shared patterns
    
    "syntax": {
        **JS_TS_SHARED_PATTERNS["syntax"],  # Keep shared syntax patterns
        "interface": {
            "pattern": """
            (interface_declaration
                modifiers: [(declare) (export)]* @syntax.interface.modifier
                name: (type_identifier) @syntax.interface.name
                type_parameters: (type_parameters
                    (type_parameter
                        name: (type_identifier) @syntax.interface.type_param.name
                        constraint: (constraint)? @syntax.interface.type_param.constraint
                        value: (default_type)? @syntax.interface.type_param.default)*
                )? @syntax.interface.type_params
                extends: (extends_type_clause
                    value: (type_reference)+ @syntax.interface.extends.type)? @syntax.interface.extends
                body: (interface_body
                    [(method_signature
                        name: (property_identifier) @syntax.interface.method.name
                        parameters: (formal_parameters) @syntax.interface.method.params
                        return_type: (type_annotation)? @syntax.interface.method.return_type)
                     (property_signature
                        name: (property_identifier) @syntax.interface.property.name
                        type: (type_annotation) @syntax.interface.property.type)
                     (index_signature) @syntax.interface.index]*
                ) @syntax.interface.body) @syntax.interface.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.interface.name", {}).get("text", ""),
                "modifiers": [m.text.decode('utf8') for m in node["captures"].get("syntax.interface.modifier", [])]
            }
        },
        "type": {
            "pattern": """
            [
                (type_alias_declaration
                    modifiers: [(declare) (export)]* @syntax.type.modifier
                    name: (type_identifier) @syntax.type.name
                    type_parameters: (type_parameters)? @syntax.type.type_params
                    value: (_) @syntax.type.value) @syntax.type.def,
                
                (enum_declaration
                    modifiers: [(declare) (export) (const)]* @syntax.enum.modifier
                    name: (identifier) @syntax.enum.name
                    body: (enum_body
                        (enum_member
                            name: (property_identifier) @syntax.enum.member.name
                            value: (_)? @syntax.enum.member.value)*) @syntax.enum.body) @syntax.enum.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.type.name", {}).get("text", "") or
                       node["captures"].get("syntax.enum.name", {}).get("text", ""),
                "kind": "type_alias" if "syntax.type.name" in node["captures"] else "enum"
            }
        }
    },
    
    "semantics": {
        "type_system": {
            "pattern": """
            [
                (type_annotation
                    type: (_) @semantics.type.annotation) @semantics.type,
                
                (type_predicate
                    name: (_) @semantics.type.predicate.name
                    type: (_) @semantics.type.predicate.type) @semantics.type.predicate,
                
                (type_query
                    (_) @semantics.type.query.target) @semantics.type.query,
                
                (union_type
                    (_)+ @semantics.type.union.member) @semantics.type.union,
                
                (intersection_type
                    (_)+ @semantics.type.intersection.member) @semantics.type.intersection,
                
                (tuple_type
                    (_)* @semantics.type.tuple.member) @semantics.type.tuple,
                
                (type_assertion
                    type: (_) @semantics.type_assertion.type
                    value: (_) @semantics.type_assertion.value) @semantics.type_assertion,
                
                (as_expression
                    value: (_) @semantics.as.value
                    type: (_) @semantics.as.type) @semantics.as
            ]
            """,
            "extract": lambda node: {
                "type": node["captures"].get("semantics.type.annotation", {}).get("text", "") or
                       node["captures"].get("semantics.type_assertion.type", {}).get("text", "") or
                       node["captures"].get("semantics.as.type", {}).get("text", ""),
                "kind": ("type_annotation" if "semantics.type.annotation" in node["captures"] else
                        "type_assertion" if "semantics.type_assertion" in node["captures"] else
                        "as_expression")
            }
        }
    },
    
    "REPOSITORY_LEARNING": TYPESCRIPT_PATTERNS_FOR_LEARNING
}