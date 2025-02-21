"""Swift-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

SWIFT_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    attributes: (attribute)* @syntax.function.attributes
                    modifiers: [(private) (public) (internal) (fileprivate) (static) (class) (final)]* @syntax.function.modifier
                    name: (identifier) @syntax.function.name
                    generic_parameter_clause: (generic_parameter_clause
                        (generic_parameter
                            name: (type_identifier) @syntax.function.type_param.name
                            type_constraints: (type_constraints
                                (inheritance_constraint
                                    type: (_) @syntax.function.type_param.constraint))*) @syntax.function.type_param)* @syntax.function.type_params
                    parameter_clause: (parameter_clause
                        (parameter
                            attributes: (attribute)* @syntax.function.param.attributes
                            modifiers: [(inout)]* @syntax.function.param.modifier
                            name: (identifier) @syntax.function.param.name
                            type: (_) @syntax.function.param.type
                            default_value: (_)? @syntax.function.param.default)*) @syntax.function.params
                    return_type: (type_annotation
                        type: (_) @syntax.function.return_type)? @syntax.function.return
                    generic_where_clause: (generic_where_clause)? @syntax.function.where
                    body: (code_block) @syntax.function.body) @syntax.function.def,
                
                (method_declaration
                    modifiers: [(mutating) (override)]* @syntax.method.modifier
                    name: (identifier) @syntax.method.name) @syntax.method.def
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
                (class_declaration
                    attributes: (attribute)* @syntax.class.attributes
                    modifiers: [(private) (public) (internal) (fileprivate) (final)]* @syntax.class.modifier
                    name: (type_identifier) @syntax.class.name
                    generic_parameter_clause: (generic_parameter_clause)? @syntax.class.type_params
                    type_inheritance_clause: (type_inheritance_clause
                        [(class_requirement) @syntax.class.superclass
                         (type_identifier) @syntax.class.protocol]*) @syntax.class.inheritance
                    generic_where_clause: (generic_where_clause)? @syntax.class.where
                    members: (class_body) @syntax.class.body) @syntax.class.def,
                
                (protocol_declaration
                    attributes: (attribute)* @syntax.protocol.attributes
                    modifiers: [(private) (public) (internal) (fileprivate)]* @syntax.protocol.modifier
                    name: (type_identifier) @syntax.protocol.name
                    type_inheritance_clause: (type_inheritance_clause)? @syntax.protocol.inheritance
                    members: (protocol_body) @syntax.protocol.body) @syntax.protocol.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.class.name", {}).get("text", "") or
                       node["captures"].get("syntax.protocol.name", {}).get("text", ""),
                "kind": "class" if "syntax.class.def" in node["captures"] else "protocol"
            }
        }
    },
    
    "semantics": {
        "property": {
            "pattern": """
            [
                (property_declaration
                    attributes: (attribute)* @semantics.property.attributes
                    modifiers: [(private) (public) (internal) (fileprivate) (static) (class)]* @semantics.property.modifier
                    name: (identifier) @semantics.property.name
                    type: (type_annotation
                        type: (_) @semantics.property.type)? @semantics.property.type_annotation
                    getter_setter_block: (getter_setter_block
                        [(getter_clause) @semantics.property.getter
                         (setter_clause) @semantics.property.setter])? @semantics.property.accessors) @semantics.property.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.property.name", {}).get("text", ""),
                "modifiers": [m.text.decode('utf8') for m in node["captures"].get("semantics.property.modifier", [])]
            }
        },
        
        "concurrency": {
            "pattern": """
            [
                (actor_declaration
                    name: (type_identifier) @semantics.concurrency.actor.name
                    members: (actor_body) @semantics.concurrency.actor.body) @semantics.concurrency.actor,
                
                (async_function
                    modifiers: (async) @semantics.concurrency.async.modifier) @semantics.concurrency.async,
                
                (await_expression
                    expression: (_) @semantics.concurrency.await.expr) @semantics.concurrency.await
            ]
            """,
            "extract": lambda node: {
                "type": ("actor" if "semantics.concurrency.actor" in node["captures"] else
                        "async" if "semantics.concurrency.async" in node["captures"] else
                        "await")
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment,
                
                (documentation_comment
                    text: /\\/\\/\\/.*/) @documentation.doc.line,
                
                (documentation_comment
                    text: /\\/\\*\\*.*?\\*\\// @documentation.doc.block),
                
                (documentation_comment
                    text: /- [a-zA-Z]+:.*/) @documentation.doc.keyword
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "") or
                       node["captures"].get("documentation.doc.line", {}).get("text", "") or
                       node["captures"].get("documentation.doc.block", {}).get("text", ""),
                "type": ("line" if "documentation.doc.line" in node["captures"] else
                        "block" if "documentation.doc.block" in node["captures"] else
                        "comment")
            }
        }
    },
    
    "structure": {
        "module": {
            "pattern": """
            [
                (import_declaration
                    path: (identifier)+ @structure.import.path
                    attributes: (attribute)* @structure.import.attributes) @structure.import,
                
                (extension_declaration
                    type: (type_identifier) @structure.extension.type
                    type_inheritance_clause: (type_inheritance_clause)? @structure.extension.protocols
                    generic_where_clause: (generic_where_clause)? @structure.extension.where
                    members: (extension_body) @structure.extension.body) @structure.extension
            ]
            """,
            "extract": lambda node: {
                "path": [p.get("text", "") for p in node["captures"].get("structure.import.path", [])],
                "type": "import" if "structure.import" in node["captures"] else "extension"
            }
        }
    }
} 