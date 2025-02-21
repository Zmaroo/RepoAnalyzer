"""Query patterns for Svelte files."""

SVELTE_PATTERNS = {
    "syntax": {
        "script": {
            "pattern": """
            (script_element
                (start_tag)
                (raw_text)? @syntax.script.content
                (end_tag)) @syntax.script.def
            """
        },
        "style": {
            "pattern": """
            (style_element
                (start_tag)
                (raw_text)? @syntax.style.content
                (end_tag)) @syntax.style.def
            """
        },
        "control_flow": {
            "pattern": """
            [
                (if_statement
                    (expression) @syntax.if.condition
                    (_)* @syntax.if.consequence
                    (else_statement)? @syntax.if.alternative) @syntax.if.def,
                
                (each_statement
                    (each_start_expr) @syntax.each.start
                    (_)* @syntax.each.body
                    (each_end_expr)? @syntax.each.end) @syntax.each.def,
                
                (await_statement
                    (expression) @syntax.await.expression
                    (then_expr)? @syntax.await.then
                    (catch_statement)? @syntax.await.catch) @syntax.await.def
            ]
            """
        }
    },
    "structure": {
        "element": {
            "pattern": """
            (element
                (start_tag
                    (tag_name) @structure.element.name
                    (attribute)* @structure.element.attributes)
                (_)* @structure.element.content
                (end_tag)?) @structure.element.def
            """
        }
    },
    "semantics": {
        "expression": {
            "pattern": """
            [
                (expression
                    (_) @semantics.expression.content) @semantics.expression.def,
                
                (const_expr
                    (_) @semantics.constant.value) @semantics.constant.def,
                
                (debug_expr
                    (_) @semantics.debug.value) @semantics.debug.def
            ]
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    }
} 