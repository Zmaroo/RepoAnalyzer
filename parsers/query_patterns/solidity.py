"""Solidity-specific Tree-sitter patterns.

This module defines basic queries for extracting key Solidity constructs such as contracts,
functions, modifiers, events, and state variable declarations.
"""

SOLIDITY_PATTERNS = {
    "default": r"""
        (contract_definition
            name: (identifier) @contract.name)
        (function_definition
            name: (identifier) @function.name
            parameters: (parameter_list) @function.parameters)
        (modifier_definition
            name: (identifier) @modifier.name)
        (event_definition
            name: (identifier) @event.name)
        (state_variable_declaration
            name: (identifier) @variable.name)
    """
} 