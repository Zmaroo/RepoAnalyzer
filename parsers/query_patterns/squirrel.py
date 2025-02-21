"""Query patterns for Squirrel files."""

SQUIRREL_PATTERNS = {
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_declaration
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list)? @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.def,
                
                (anonymous_function
                    parameters: (parameter_list)? @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.lambda
            ]
            """
        },
        "class": {
            "pattern": """
            (class_declaration
                name: (identifier) @syntax.class.name
                members: [
                    (attribute_declaration)* @syntax.class.attributes
                    (member_declaration)* @syntax.class.members
                ]) @syntax.class.def
            """
        },
        "control_flow": {
            "pattern": """
            [
                (if_statement
                    condition: (expression) @syntax.if.condition
                    consequence: (_) @syntax.if.consequence
                    alternative: (else_statement)? @syntax.if.alternative) @syntax.if.def,
                
                (switch_statement
                    value: (expression) @syntax.switch.value
                    cases: [
                        (case_statement)* @syntax.switch.case
                        (default_statement)? @syntax.switch.default
                    ]) @syntax.switch.def,
                
                (try_statement
                    body: (block) @syntax.try.body
                    catch: (catch_clause)* @syntax.try.catch) @syntax.try.def
            ]
            """
        }
    },
    "semantics": {
        "variable": {
            "pattern": """
            [
                (var_statement
                    name: (identifier) @semantics.variable.name
                    value: (expression)? @semantics.variable.value) @semantics.variable.def,
                
                (const_declaration
                    name: (identifier) @semantics.constant.name
                    value: (expression) @semantics.constant.value) @semantics.constant.def
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