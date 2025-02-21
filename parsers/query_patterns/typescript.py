"""TypeScript-specific Tree-sitter patterns."""

from .js_ts_shared import JS_TS_SHARED_PATTERNS

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
    }
}