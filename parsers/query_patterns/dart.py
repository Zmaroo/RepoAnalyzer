"""Query patterns for Dart files."""

from .common import COMMON_PATTERNS

DART_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    metadata: (metadata)* @syntax.function.metadata
                    return_type: (_)? @syntax.function.return_type
                    name: (identifier) @syntax.function.name
                    parameters: (formal_parameter_list) @syntax.function.params
                    body: [(block) (arrow_body)]? @syntax.function.body) @syntax.function.def,
                
                (method_declaration
                    metadata: (metadata)* @syntax.function.method.metadata
                    modifiers: [(static) (abstract) (external)]* @syntax.function.method.modifier
                    return_type: (_)? @syntax.function.method.return_type
                    name: (identifier) @syntax.function.method.name
                    parameters: (formal_parameter_list) @syntax.function.method.params
                    body: [(block) (arrow_body)]? @syntax.function.method.body) @syntax.function.method
            ]
            """,
            "extract": lambda node: {
                "name": (node["captures"].get("syntax.function.name", {}).get("text", "") or 
                        node["captures"].get("syntax.function.method.name", {}).get("text", "")),
                "type": "method" if "syntax.function.method" in node["captures"] else "function"
            }
        },

        "class": {
            "pattern": """
            [
                (class_declaration
                    metadata: (metadata)* @syntax.class.metadata
                    modifiers: [(abstract)]* @syntax.class.modifier
                    name: (identifier) @syntax.class.name
                    type_parameters: (type_parameters)? @syntax.class.type_params
                    superclass: (superclass)? @syntax.class.extends
                    interfaces: (interfaces)? @syntax.class.implements
                    mixins: (mixins)? @syntax.class.with
                    body: (class_body) @syntax.class.body) @syntax.class.def,
                    
                (mixin_declaration
                    metadata: (metadata)* @syntax.mixin.metadata
                    name: (identifier) @syntax.mixin.name
                    on: (on_clause)? @syntax.mixin.on
                    interfaces: (interfaces)? @syntax.mixin.implements
                    body: (class_body) @syntax.mixin.body) @syntax.mixin.def
            ]
            """,
            "extract": lambda node: {
                "name": (node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.mixin.name", {}).get("text", "")),
                "type": "mixin" if "syntax.mixin.def" in node["captures"] else "class"
            }
        }
    },

    "semantics": {
        "async": {
            "pattern": """
            [
                (function_declaration
                    body: (block
                        (async_marker) @semantics.async.marker)) @semantics.async.function,
                        
                (method_declaration
                    body: (block
                        (async_marker) @semantics.async.method.marker)) @semantics.async.method,
                        
                (await_expression
                    expression: (_) @semantics.async.await.expr) @semantics.async.await,
                    
                (yield_statement
                    expression: (_)? @semantics.async.yield.expr) @semantics.async.yield
            ]
            """,
            "extract": lambda node: {
                "type": ("async" if "semantics.async.marker" in node["captures"] or
                        "semantics.async.method.marker" in node["captures"] else
                        "await" if "semantics.async.await" in node["captures"] else "yield")
            }
        },

        "widget": {
            "pattern": """
            [
                (class_declaration
                    metadata: (metadata
                        (identifier) @semantics.widget.annotation
                        (#match? @semantics.widget.annotation "^Widget$")) @semantics.widget.metadata
                    name: (identifier) @semantics.widget.name) @semantics.widget.class,
                    
                (method_declaration
                    name: (identifier) @semantics.widget.build
                    (#match? @semantics.widget.build "^build$")
                    body: (block
                        (return_statement
                            expression: (_) @semantics.widget.build.return))) @semantics.widget.build_method
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.widget.name", {}).get("text", ""),
                "type": "widget"
            }
        }
    },

    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (documentation_comment
                    content: (_)* @documentation.doc.content) @documentation.doc,
                (documentation_comment
                    reference: (identifier) @documentation.doc.reference) @documentation.doc.ref
            ]
            """,
            "extract": lambda node: {
                "text": (node["captures"].get("documentation.comment", {}).get("text", "") or
                        node["captures"].get("documentation.doc.content", {}).get("text", "")),
                "type": ("doc" if "documentation.doc" in node["captures"] else
                        "ref" if "documentation.doc.ref" in node["captures"] else "comment")
            }
        }
    }
} 