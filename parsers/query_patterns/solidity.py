"""Query patterns for Solidity files."""

SOLIDITY_PATTERNS = {
    "syntax": {
        "contract": {
            "pattern": """
            [
                (contract_definition
                    name: (identifier) @syntax.contract.name
                    body: (contract_body) @syntax.contract.body) @syntax.contract.def
            ]
            """
        },
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (parameter_list) @syntax.function.params
                    return_parameters: (parameter_list)? @syntax.function.returns
                    body: (block) @syntax.function.body) @syntax.function.def,
                
                (fallback_receive_definition
                    parameters: (parameter_list)? @syntax.function.params
                    body: (block) @syntax.function.body) @syntax.function.fallback
            ]
            """
        },
        "modifier": {
            "pattern": """
            (modifier_definition
                name: (identifier) @syntax.modifier.name
                parameters: (parameter_list)? @syntax.modifier.params
                body: (block) @syntax.modifier.body) @syntax.modifier.def
            """
        }
    },
    "structure": {
        "enum": {
            "pattern": """
            (enum_declaration
                name: (identifier) @structure.enum.name
                members: (enum_value_list)? @structure.enum.values) @structure.enum.def
            """
        },
        "event": {
            "pattern": """
            (event_definition
                name: (identifier) @structure.event.name
                parameters: (event_parameter_list) @structure.event.params) @structure.event.def
            """
        },
        "struct": {
            "pattern": """
            (struct_declaration
                name: (identifier) @structure.struct.name
                members: (struct_member_list) @structure.struct.members) @structure.struct.def
            """
        }
    },
    "semantics": {
        "variable": {
            "pattern": """
            [
                (state_variable_declaration
                    type: (type_name) @semantics.variable.type
                    name: (identifier) @semantics.variable.name
                    value: (_)? @semantics.variable.value) @semantics.variable.def,
                
                (variable_declaration_statement
                    declaration: (variable_declaration) @semantics.variable.decl) @semantics.variable.stmt
            ]
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (natspec) @documentation.natspec
            ]
            """
        }
    }
} 