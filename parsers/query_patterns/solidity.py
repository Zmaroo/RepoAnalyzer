"""Query patterns for Solidity files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

SOLIDITY_PATTERNS_FOR_LEARNING = {
    "contract_patterns": {
        "pattern": """
        [
            (contract_definition
                name: (identifier) @contract.name
                base: (inheritance_specifier 
                    name: (identifier) @contract.base.name)* @contract.base
                body: (contract_body) @contract.body) @contract.def,
                
            (interface_definition
                name: (identifier) @interface.name
                body: (contract_body) @interface.body) @interface.def,
                
            (library_definition
                name: (identifier) @library.name
                body: (contract_body) @library.body) @library.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "contract_patterns",
            "is_contract": "contract.def" in node["captures"],
            "is_interface": "interface.def" in node["captures"],
            "is_library": "library.def" in node["captures"],
            "name": (
                node["captures"].get("contract.name", {}).get("text", "") or
                node["captures"].get("interface.name", {}).get("text", "") or
                node["captures"].get("library.name", {}).get("text", "")
            ),
            "has_inheritance": "contract.base" in node["captures"] and node["captures"].get("contract.base", {}).get("text", "") != "",
            "base_contracts": [base.get("text", "") for base in node["captures"].get("contract.base.name", [])],
            "contract_type": (
                "contract" if "contract.def" in node["captures"] else
                "interface" if "interface.def" in node["captures"] else
                "library" if "library.def" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "function_patterns": {
        "pattern": """
        [
            (function_definition
                name: (identifier) @function.name
                visibility: [(public) (private) (internal) (external)] @function.visibility
                state_mutability: [(pure) (view) (payable)] @function.mutability
                parameters: (parameter_list) @function.params
                return_parameters: (parameter_list)? @function.returns
                body: (block) @function.body) @function.def,
                
            (modifier_definition
                name: (identifier) @modifier.name
                parameters: (parameter_list)? @modifier.params
                body: (block) @modifier.body) @modifier.def,
                
            (constructor_definition
                parameters: (parameter_list) @constructor.params
                body: (block) @constructor.body) @constructor.def,
                
            (fallback_receive_definition
                kind: [(fallback) (receive)] @fallback.kind
                parameters: (parameter_list)? @fallback.params
                body: (block) @fallback.body) @fallback.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "function_patterns",
            "is_function": "function.def" in node["captures"],
            "is_modifier": "modifier.def" in node["captures"],
            "is_constructor": "constructor.def" in node["captures"],
            "is_fallback_receive": "fallback.def" in node["captures"],
            "name": (
                node["captures"].get("function.name", {}).get("text", "") or
                node["captures"].get("modifier.name", {}).get("text", "")
            ),
            "visibility": node["captures"].get("function.visibility", {}).get("text", ""),
            "mutability": node["captures"].get("function.mutability", {}).get("text", ""),
            "fallback_type": node["captures"].get("fallback.kind", {}).get("text", ""),
            "function_type": (
                "regular_function" if "function.def" in node["captures"] else
                "modifier" if "modifier.def" in node["captures"] else
                "constructor" if "constructor.def" in node["captures"] else
                "fallback_receive" if "fallback.def" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "data_storage": {
        "pattern": """
        [
            (state_variable_declaration
                type: (type_name) @storage.var.type
                visibility: [(public) (private) (internal)] @storage.var.visibility
                name: (identifier) @storage.var.name
                value: (_)? @storage.var.value) @storage.var.def,
                
            (struct_declaration
                name: (identifier) @storage.struct.name
                members: (struct_member
                    type: (type_name) @storage.struct.member.type
                    name: (identifier) @storage.struct.member.name)* @storage.struct.members) @storage.struct.def,
                
            (enum_declaration
                name: (identifier) @storage.enum.name
                members: (enum_value
                    name: (identifier) @storage.enum.value.name
                    value: (_)? @storage.enum.value.value)* @storage.enum.values) @storage.enum.def,
                
            (mapping
                key: (mapping_key) @storage.mapping.key
                value: (type_name) @storage.mapping.value) @storage.mapping.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "data_storage",
            "is_state_variable": "storage.var.def" in node["captures"],
            "is_struct": "storage.struct.def" in node["captures"],
            "is_enum": "storage.enum.def" in node["captures"],
            "is_mapping": "storage.mapping.def" in node["captures"],
            "name": (
                node["captures"].get("storage.var.name", {}).get("text", "") or
                node["captures"].get("storage.struct.name", {}).get("text", "") or
                node["captures"].get("storage.enum.name", {}).get("text", "")
            ),
            "variable_type": node["captures"].get("storage.var.type", {}).get("text", ""),
            "visibility": node["captures"].get("storage.var.visibility", {}).get("text", ""),
            "mapping_key": node["captures"].get("storage.mapping.key", {}).get("text", ""),
            "mapping_value": node["captures"].get("storage.mapping.value", {}).get("text", ""),
            "storage_type": (
                "state_variable" if "storage.var.def" in node["captures"] else
                "struct" if "storage.struct.def" in node["captures"] else
                "enum" if "storage.enum.def" in node["captures"] else
                "mapping" if "storage.mapping.def" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "security_patterns": {
        "pattern": """
        [
            (require_statement
                condition: (_) @security.require.cond
                message: (_)? @security.require.msg) @security.require.def,
                
            (assert_statement
                condition: (_) @security.assert.cond) @security.assert.def,
                
            (call_expression
                function: (member_expression
                    object: (_) @security.transfer.obj
                    property: (identifier) @security.transfer.func {
                        match: "^(transfer|send)$"
                    }) @security.transfer.member
                arguments: (call_arguments) @security.transfer.args) @security.transfer.call,
                
            (function_call
                function: (identifier) @security.call.name {
                    match: "^(delegatecall|callcode|call)$"
                }
                arguments: (call_arguments) @security.call.args) @security.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "security_patterns",
            "is_require": "security.require.def" in node["captures"],
            "is_assert": "security.assert.def" in node["captures"],
            "is_transfer": "security.transfer.call" in node["captures"],
            "is_low_level_call": "security.call" in node["captures"],
            "transfer_function": node["captures"].get("security.transfer.func", {}).get("text", ""),
            "call_function": node["captures"].get("security.call.name", {}).get("text", ""),
            "has_error_message": "security.require.msg" in node["captures"] and node["captures"].get("security.require.msg", {}).get("text", "") != "",
            "security_pattern": (
                "require_check" if "security.require.def" in node["captures"] else
                "assert_check" if "security.assert.def" in node["captures"] else
                "value_transfer" if "security.transfer.call" in node["captures"] else
                "delegate_call" if "security.call" in node["captures"] and "delegatecall" in node["captures"].get("security.call.name", {}).get("text", "") else
                "low_level_call" if "security.call" in node["captures"] else
                "unknown"
            )
        }
    }
}

SOLIDITY_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "contract": QueryPattern(
                pattern="""
                [
                    (contract_definition
                        name: (identifier) @syntax.contract.name
                        base: (inheritance_specifier 
                            name: (identifier) @syntax.contract.base.name)* @syntax.contract.base
                        body: (contract_body) @syntax.contract.body) @syntax.contract.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.contract.name", {}).get("text", ""),
                    "has_inheritance": "syntax.contract.base" in node["captures"],
                    "base_contracts": [base.get("text", "") for base in node["captures"].get("syntax.contract.base.name", [])]
                }
            ),
            "function": QueryPattern(
                pattern="""
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
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "has_params": "syntax.function.params" in node["captures"],
                    "has_returns": "syntax.function.returns" in node["captures"],
                    "is_fallback": "syntax.function.fallback" in node["captures"]
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "enum": QueryPattern(
                pattern="""
                (enum_declaration
                    name: (identifier) @structure.enum.name
                    members: (enum_value_list)? @structure.enum.values) @structure.enum.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.enum.name", {}).get("text", ""),
                    "has_values": "structure.enum.values" in node["captures"]
                }
            ),
            "event": QueryPattern(
                pattern="""
                (event_definition
                    name: (identifier) @structure.event.name
                    parameters: (event_parameter_list) @structure.event.params) @structure.event.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.event.name", {}).get("text", ""),
                    "has_params": "structure.event.params" in node["captures"]
                }
            ),
            "struct": QueryPattern(
                pattern="""
                (struct_declaration
                    name: (identifier) @structure.struct.name
                    members: (struct_member_list) @structure.struct.members) @structure.struct.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.struct.name", {}).get("text", ""),
                    "has_members": "structure.struct.members" in node["captures"]
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment,
                    (natspec) @documentation.natspec
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment", {}).get("text", "") or
                        node["captures"].get("documentation.natspec", {}).get("text", "")
                    ),
                    "type": "natspec" if "documentation.natspec" in node["captures"] else "comment"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.SECURITY: {
            "security_patterns": QueryPattern(
                pattern="""
                [
                    (require_statement
                        condition: (_) @security.require.cond
                        message: (_)? @security.require.msg) @security.require.def,
                    
                    (assert_statement
                        condition: (_) @security.assert.cond) @security.assert.def,
                    
                    (call_expression
                        function: (member_expression
                            object: (_) @security.transfer.obj
                            property: (identifier) @security.transfer.func {
                                match: "^(transfer|send)$"
                            }) @security.transfer.member
                        arguments: (call_arguments) @security.transfer.args) @security.transfer.call,
                    
                    (function_call
                        function: (identifier) @security.call.name {
                            match: "^(delegatecall|callcode|call)$"
                        }
                        arguments: (call_arguments) @security.call.args) @security.call
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "security",
                    "is_require": "security.require.def" in node["captures"],
                    "is_assert": "security.assert.def" in node["captures"],
                    "is_transfer": "security.transfer.call" in node["captures"],
                    "is_low_level_call": "security.call" in node["captures"],
                    "transfer_function": node["captures"].get("security.transfer.func", {}).get("text", ""),
                    "call_function": node["captures"].get("security.call.name", {}).get("text", ""),
                    "has_error_message": "security.require.msg" in node["captures"],
                    "security_pattern": (
                        "require_check" if "security.require.def" in node["captures"] else
                        "assert_check" if "security.assert.def" in node["captures"] else
                        "value_transfer" if "security.transfer.call" in node["captures"] else
                        "delegate_call" if "security.call" in node["captures"] and "delegatecall" in node["captures"].get("security.call.name", {}).get("text", "") else
                        "low_level_call" if "security.call" in node["captures"] else
                        "unknown"
                    )
                }
            )
        }
    },

    "REPOSITORY_LEARNING": SOLIDITY_PATTERNS_FOR_LEARNING
} 