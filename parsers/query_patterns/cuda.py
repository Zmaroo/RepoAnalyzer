"""Query patterns for CUDA files."""

CUDA_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                declarator: (function_declarator
                    declarator: (_) @kernel.name)
                (attribute_declaration
                    (attribute
                        name: (identifier) @kernel.attr.name
                        (#match? @kernel.attr.name "^(__global__|__device__|__host__)$")))
                body: (_) @kernel.body) @function
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (translation_unit
                (_)* @content) @namespace
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (declaration
                (attribute_declaration
                    (attribute
                        name: (identifier) @memory.attr.name
                        (#match? @memory.attr.name "^(__device__|__constant__|__shared__|__managed__|__restrict__|__global__)$")))
                declarator: (_) @memory.var) @variable
            """
        ],
        "expression": [
            """
            (call_expression
                function: (identifier) @sync.func
                (#match? @sync.func "^(__syncthreads|__syncwarp|__syncthreads_count|__syncthreads_and|__syncthreads_or)$")
                arguments: (_)? @sync.args) @expression
            """
        ]
    },
    "documentation": {
        "comment": [
            """
            [(comment) (comment_multiline)] @comment
            """
        ]
    }
} 