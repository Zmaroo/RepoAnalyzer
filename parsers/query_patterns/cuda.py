"""Query patterns for CUDA files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

CUDA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
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
                extract=lambda node: {
                    "name": (node["captures"].get("syntax.kernel.name", {}).get("text", "") or
                            node["captures"].get("syntax.function.name", {}).get("text", "")),
                    "type": "kernel" if "syntax.kernel.def" in node["captures"] else "function"
                }
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "namespace": QueryPattern(
                pattern="""
                [
                    (translation_unit
                        (_)* @content) @namespace
                ]
                """,
                extract=lambda node: {
                    "type": "namespace",
                    "content": node["node"].text.decode('utf8')
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (declaration
                        (attribute_declaration
                            (attribute
                                name: (identifier) @semantics.var.attr.name
                                (#match? @semantics.var.attr.name "^(__device__|__constant__|__shared__|__managed__|__restrict__|__global__)$")))
                        declarator: (_) @semantics.var.name) @semantics.var.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.var.name", {}).get("text", ""),
                    "attribute": node["captures"].get("semantics.var.attr.name", {}).get("text", "")
                }
            ),
            
            "synchronization": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (identifier) @semantics.sync.func
                        (#match? @semantics.sync.func "^(__syncthreads|__syncwarp|__syncthreads_count|__syncthreads_and|__syncthreads_or)$")
                        arguments: (_)? @semantics.sync.args) @semantics.sync.def
                ]
                """,
                extract=lambda node: {
                    "function": node["captures"].get("semantics.sync.func", {}).get("text", "")
                }
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comments": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment.single,
                    (comment_multiline) @documentation.comment.multi
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment.single", {}).get("text", "") or
                           node["captures"].get("documentation.comment.multi", {}).get("text", ""),
                    "type": "single" if "documentation.comment.single" in node["captures"] else "multi"
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "kernel_launch_patterns": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (identifier) @launch.kernel.name
                        arguments: (argument_list) @launch.kernel.args) @launch.kernel,
                        
                    (subscript_expression
                        argument: (argument_list) @launch.config.args) @launch.config,
                        
                    (call_expression
                        function: (identifier) @launch.api.func
                        (#match? @launch.api.func "^(cudaLaunch|cudaLaunchKernel)$")
                        arguments: (argument_list) @launch.api.args) @launch.api
                ]
                """,
                extract=lambda node: {
                    "type": "kernel_launch_pattern",
                    "is_triple_chevron": "<<<" in node["node"].text.decode('utf8') and ">>>" in node["node"].text.decode('utf8'),
                    "is_cuda_launch_api": "launch.api.func" in node["captures"],
                    "grid_dimensions": (3 if "<<<" in node["node"].text.decode('utf8') and 
                                      node["node"].text.decode('utf8').count(",") >= 5 else
                                      2 if "<<<" in node["node"].text.decode('utf8') else 0),
                    "kernel_name": node["captures"].get("launch.kernel.name", {}).get("text", "")
                }
            )
        },
        PatternPurpose.MEMORY_MANAGEMENT: {
            "memory_management": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (identifier) @memory.alloc.func
                        (#match? @memory.alloc.func "^(cudaMalloc|cudaMallocHost|cudaMallocManaged|cudaMallocPitch|cudaHostAlloc)$")
                        arguments: (argument_list) @memory.alloc.args) @memory.allocation,
                        
                    (call_expression
                        function: (identifier) @memory.free.func
                        (#match? @memory.free.func "^(cudaFree|cudaFreeHost)$")
                        arguments: (argument_list) @memory.free.args) @memory.free,
                        
                    (call_expression
                        function: (identifier) @memory.copy.func
                        (#match? @memory.copy.func "^(cudaMemcpy|cudaMemcpyAsync|cudaMemcpyToSymbol|cudaMemcpyFromSymbol|cudaMemcpy2D|cudaMemcpy3D)$")
                        arguments: (argument_list) @memory.copy.args) @memory.copy
                ]
                """,
                extract=lambda node: {
                    "type": "memory_management_pattern",
                    "operation": ("allocation" if "memory.allocation" in node["captures"] else
                                "free" if "memory.free" in node["captures"] else
                                "copy" if "memory.copy" in node["captures"] else "unknown"),
                    "api_function": (node["captures"].get("memory.alloc.func", {}).get("text", "") or
                                   node["captures"].get("memory.free.func", {}).get("text", "") or
                                   node["captures"].get("memory.copy.func", {}).get("text", "")),
                    "is_unified_memory": "cudaMallocManaged" in (node["captures"].get("memory.alloc.func", {}).get("text", "") or ""),
                    "is_pinned_memory": "cudaMallocHost" in (node["captures"].get("memory.alloc.func", {}).get("text", "") or "") or "cudaHostAlloc" in (node["captures"].get("memory.alloc.func", {}).get("text", "") or "")
                }
            )
        },
        PatternPurpose.PERFORMANCE: {
            "thread_organization": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (identifier) @thread.idx.func
                        (#match? @thread.idx.func "^(threadIdx|blockIdx|blockDim|gridDim)$")
                        field: (field_expression
                            field: (field_identifier) @thread.idx.field)) @thread.idx,
                            
                    (call_expression
                        function: (identifier) @thread.sync.func
                        (#match? @thread.sync.func "^(__syncthreads|__syncwarp|__syncthreads_count|__syncthreads_and|__syncthreads_or)$")
                        arguments: (argument_list)? @thread.sync.args) @thread.sync
                ]
                """,
                extract=lambda node: {
                    "type": "thread_organization_pattern",
                    "is_thread_index": "thread.idx" in node["captures"],
                    "is_sync": "thread.sync" in node["captures"],
                    "index_type": node["captures"].get("thread.idx.func", {}).get("text", ""),
                    "dimension": node["captures"].get("thread.idx.field", {}).get("text", ""),
                    "sync_function": node["captures"].get("thread.sync.func", {}).get("text", "")
                }
            )
        },
        PatternPurpose.API_USAGE: {
            "cuda_api_usage": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (identifier) @api.func
                        (#match? @api.func "^(cuda[A-Z][a-zA-Z0-9]*)$")
                        arguments: (argument_list) @api.args) @api.call,
                        
                    (call_expression
                        function: (identifier) @api.error.func
                        (#match? @api.error.func "^(cudaGetLastError|cudaGetErrorString|cudaGetErrorName)$")
                        arguments: (argument_list)? @api.error.args) @api.error.check
                ]
                """,
                extract=lambda node: {
                    "type": "cuda_api_usage_pattern",
                    "api_function": node["captures"].get("api.func", {}).get("text", "") or node["captures"].get("api.error.func", {}).get("text", ""),
                    "is_error_check": "api.error.check" in node["captures"],
                    "api_category": (
                        "memory" if any(prefix in (node["captures"].get("api.func", {}).get("text", "") or "") 
                                      for prefix in ["cudaMalloc", "cudaFree", "cudaMemcpy"]) else
                        "execution" if any(prefix in (node["captures"].get("api.func", {}).get("text", "") or "") 
                                        for prefix in ["cudaLaunch", "cudaStream", "cudaEvent", "cudaGraph"]) else
                        "error" if "api.error.check" in node["captures"] else
                        "device" if any(prefix in (node["captures"].get("api.func", {}).get("text", "") or "") 
                                      for prefix in ["cudaGetDevice", "cudaSetDevice", "cudaDeviceReset"]) else
                        "other"
                    )
                }
            )
        }
    }
} 