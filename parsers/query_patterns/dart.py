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

# Repository learning patterns for Dart
DART_PATTERNS_FOR_LEARNING = {
    "flutter_widgets": {
        "pattern": """
        [
            (class_declaration
                metadata: (metadata)? @widget.metadata
                name: (identifier) @widget.name
                superclass: (superclass
                    type: [(type_identifier) (qualified_identifier)]+ @widget.superclass.type) @widget.superclass) @widget.class,
                
            (method_declaration
                name: (identifier) @widget.build.name
                (#match? @widget.build.name "^build$")
                parameters: (formal_parameter_list) @widget.build.params
                body: (block) @widget.build.body) @widget.build.method
        ]
        """,
        "extract": lambda node: {
            "type": "flutter_widget_pattern",
            "widget_name": node["captures"].get("widget.name", {}).get("text", ""),
            "is_stateless": "StatelessWidget" in (node["captures"].get("widget.superclass.type", {}).get("text", "") or ""),
            "is_stateful": "StatefulWidget" in (node["captures"].get("widget.superclass.type", {}).get("text", "") or ""),
            "has_build_method": "widget.build.method" in node["captures"],
            "widget_type": ("stateless" if "StatelessWidget" in (node["captures"].get("widget.superclass.type", {}).get("text", "") or "") else
                          "stateful" if "StatefulWidget" in (node["captures"].get("widget.superclass.type", {}).get("text", "") or "") else
                          "other")
        }
    },
    
    "async_patterns": {
        "pattern": """
        [
            (method_declaration
                body: (block
                    (async_marker) @async.marker.method
                    (#match? @async.marker.method "^(async|async\\*|sync\\*)$")) @async.method.body) @async.method,
                
            (function_declaration
                body: (block
                    (async_marker) @async.marker.function
                    (#match? @async.marker.function "^(async|async\\*|sync\\*)$")) @async.function.body) @async.function,
                
            (await_expression
                expression: (_) @async.await.expr) @async.await,
                
            (return_statement
                (await_expression) @async.return.await) @async.return,
                
            (method_declaration
                return_type: (type_identifier) @async.return.type
                (#match? @async.return.type "^(Future|Stream)$")
                name: (identifier) @async.return.method) @async.future.method
        ]
        """,
        "extract": lambda node: {
            "type": "async_pattern",
            "is_async_method": "async.marker.method" in node["captures"],
            "is_async_function": "async.marker.function" in node["captures"],
            "uses_await": "async.await" in node["captures"],
            "returns_future": "async.return.type" in node["captures"] and "Future" in node["captures"].get("async.return.type", {}).get("text", ""),
            "returns_stream": "async.return.type" in node["captures"] and "Stream" in node["captures"].get("async.return.type", {}).get("text", ""),
            "async_style": (node["captures"].get("async.marker.method", {}).get("text", "") or
                           node["captures"].get("async.marker.function", {}).get("text", "") or "").strip()
        }
    },
    
    "null_safety": {
        "pattern": """
        [
            (nullable_type
                type: (_) @nullable.type) @nullable,
                
            (formal_parameter
                type: (_) @param.type
                name: (identifier) @param.name
                default_value: (_)? @param.default) @param.def,
                
            (null_check
                expression: (_) @null.check.expr) @null.check,
                
            (null_aware
                expression: (_) @null.aware.expr) @null.aware,
                
            (binary_expression
                left: (_) @null.assert.left
                operator: (binary_operator) @null.assert.op
                (#match? @null.assert.op "\\!\\=")
                right: (null_literal) @null.assert.right) @null.assert
        ]
        """,
        "extract": lambda node: {
            "type": "null_safety_pattern",
            "uses_nullable_type": "nullable" in node["captures"],
            "uses_null_check": "null.check" in node["captures"],
            "uses_null_aware": "null.aware" in node["captures"],
            "checks_for_null": "null.assert" in node["captures"],
            "nullable_type": node["captures"].get("nullable.type", {}).get("text", ""),
            "parameter_has_default": "param.def" in node["captures"] and "param.default" in node["captures"]
        }
    },
    
    "naming_conventions": {
        "pattern": """
        [
            (class_declaration
                name: (identifier) @naming.class.name) @naming.class,
                
            (method_declaration
                name: (identifier) @naming.method.name) @naming.method,
                
            (variable_declaration
                (initialized_variable_declaration
                    name: (identifier) @naming.variable.name)) @naming.variable,
                    
            (constant_declaration
                (initialized_identifier_list
                    (identifier) @naming.constant.name)) @naming.constant
        ]
        """,
        "extract": lambda node: {
            "type": "naming_convention_pattern",
            "entity_type": ("class" if "naming.class.name" in node["captures"] else
                          "method" if "naming.method.name" in node["captures"] else
                          "constant" if "naming.constant.name" in node["captures"] else
                          "variable"),
            "name": (node["captures"].get("naming.class.name", {}).get("text", "") or
                   node["captures"].get("naming.method.name", {}).get("text", "") or
                   node["captures"].get("naming.constant.name", {}).get("text", "") or
                   node["captures"].get("naming.variable.name", {}).get("text", "")),
            "is_pascal_case": (node["captures"].get("naming.class.name", {}).get("text", "") or "").strip() and
                             (node["captures"].get("naming.class.name", {}).get("text", "") or "")[0:1].isupper() and
                             not "_" in (node["captures"].get("naming.class.name", {}).get("text", "") or ""),
            "is_camel_case": (node["captures"].get("naming.method.name", {}).get("text", "") or 
                            node["captures"].get("naming.variable.name", {}).get("text", "") or "").strip() and
                           (node["captures"].get("naming.method.name", {}).get("text", "") or 
                            node["captures"].get("naming.variable.name", {}).get("text", "") or "")[0:1].islower() and
                           not "_" in (node["captures"].get("naming.method.name", {}).get("text", "") or 
                                     node["captures"].get("naming.variable.name", {}).get("text", "") or ""),
            "is_screaming_snake_case": all(c.isupper() or not c.isalpha() for c in 
                                         (node["captures"].get("naming.constant.name", {}).get("text", "") or "")) and
                                      "_" in (node["captures"].get("naming.constant.name", {}).get("text", "") or "")
        }
    }
}

# Add the repository learning patterns to the main patterns
DART_PATTERNS['REPOSITORY_LEARNING'] = DART_PATTERNS_FOR_LEARNING 