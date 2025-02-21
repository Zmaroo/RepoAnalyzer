"""Query patterns for CUDA files."""

from .common import COMMON_PATTERNS

CUDA_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    declarator: (function_declarator
                        declarator: (_) @syntax.kernel.name)
                    (attribute_declaration
                        (attribute
                            name: (identifier) @syntax.kernel.attr.name
                            (#match? @syntax.kernel.attr.name "^(__global__|__device__|__host__)$")))
                    body: (_) @syntax.kernel.body) @syntax.kernel.def,
                
                (function_definition
                    declarator: (function_declarator
                        declarator: (_) @syntax.function.name)
                    body: (_) @syntax.function.body) @syntax.function.def
            ]
            """,
            "extract": lambda node: {
                "name": (node["captures"].get("syntax.kernel.name", {}).get("text", "") or
                        node["captures"].get("syntax.function.name", {}).get("text", "")),
                "type": "kernel" if "syntax.kernel.def" in node["captures"] else "function"
            }
        }
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
        "variable": {
            "pattern": """
            [
                (declaration
                    (attribute_declaration
                        (attribute
                            name: (identifier) @semantics.var.attr.name
                            (#match? @semantics.var.attr.name "^(__device__|__constant__|__shared__|__managed__|__restrict__|__global__)$")))
                    declarator: (_) @semantics.var.name) @semantics.var.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.var.name", {}).get("text", ""),
                "attribute": node["captures"].get("semantics.var.attr.name", {}).get("text", "")
            }
        },
        
        "synchronization": {
            "pattern": """
            [
                (call_expression
                    function: (identifier) @semantics.sync.func
                    (#match? @semantics.sync.func "^(__syncthreads|__syncwarp|__syncthreads_count|__syncthreads_and|__syncthreads_or)$")
                    arguments: (_)? @semantics.sync.args) @semantics.sync.def
            ]
            """,
            "extract": lambda node: {
                "function": node["captures"].get("semantics.sync.func", {}).get("text", "")
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment.single,
                (comment_multiline) @documentation.comment.multi
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment.single", {}).get("text", "") or
                       node["captures"].get("documentation.comment.multi", {}).get("text", ""),
                "type": "single" if "documentation.comment.single" in node["captures"] else "multi"
            }
        }
    }
} 