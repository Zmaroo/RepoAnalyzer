"""CUDA-specific Tree-sitter patterns."""

CUDA_PATTERNS = {
    # CUDA kernel patterns
    "kernel": """
        [
          (function_definition
            declarator: (function_declarator
              declarator: (_) @kernel.name)
            (attribute_declaration
              (attribute
                name: (identifier) @kernel.attr.name
                (#match? @kernel.attr.name "^(__global__|__device__|__host__)$")))
            body: (_) @kernel.body) @kernel.def
        ]
    """,

    # CUDA memory space patterns
    "memory_space": """
        [
          (declaration
            (attribute_declaration
              (attribute
                name: (identifier) @memory.attr.name
                (#match? @memory.attr.name "^(__device__|__constant__|__shared__|__managed__|__restrict__|__global__)$")))
            declarator: (_) @memory.var) @memory.decl
        ]
    """,

    # Launch bounds patterns
    "launch_bounds": """
        [
          (launch_bounds
            (_) @launch.max_threads
            (_)? @launch.min_blocks) @launch.bounds
        ]
    """,

    # Grid/Block dimension patterns
    "grid_dim": """
        [
          (call_expression
            function: (_) @grid.func
            arguments: (_) @grid.args
            kernel_call_syntax: (_) @grid.dims) @grid.launch
        ]
    """,

    # Device function patterns
    "device_function": """
        [
          (function_definition
            declarator: (function_declarator
              declarator: (_) @device.func.name)
            (attribute_declaration
              (attribute
                name: (identifier) @device.attr.name
                (#match? @device.attr.name "^(__device__|__host__|__noinline__|__forceinline__)$")))
            body: (_) @device.func.body) @device.func.def
        ]
    """,

    # Atomic operation patterns
    "atomic": """
        [
          (call_expression
            function: (identifier) @atomic.func
            (#match? @atomic.func "^(atomicAdd|atomicSub|atomicMin|atomicMax|atomicInc|atomicDec|atomicExch|atomicCAS)$")
            arguments: (_) @atomic.args) @atomic.call
        ]
    """,

    # Synchronization patterns
    "sync": """
        [
          (call_expression
            function: (identifier) @sync.func
            (#match? @sync.func "^(__syncthreads|__syncwarp|__syncthreads_count|__syncthreads_and|__syncthreads_or)$")
            arguments: (_)? @sync.args) @sync.call
        ]
    """,

    # Memory fence patterns
    "memory_fence": """
        [
          (call_expression
            function: (identifier) @fence.func
            (#match? @fence.func "^(__threadfence|__threadfence_block|__threadfence_system)$")
            arguments: (_)? @fence.args) @fence.call
        ]
    """,

    # Warp intrinsics patterns
    "warp": """
        [
          (call_expression
            function: (identifier) @warp.func
            (#match? @warp.func "^(__ballot|__all|__any|__shfl|__shfl_up|__shfl_down|__shfl_xor)$")
            arguments: (_) @warp.args) @warp.call
        ]
    """,

    # Texture memory patterns
    "texture": """
        [
          (declaration
            type: (type_identifier) @texture.type
            (#match? @texture.type "^(texture|cudaTextureObject_t)$")
            declarator: (_) @texture.name) @texture.decl
        ]
    """,

    # Error handling patterns
    "error_handling": """
        [
          (call_expression
            function: (identifier) @error.func
            (#match? @error.func "^(cudaGetLastError|cudaGetErrorString|cudaError_t)$")
            arguments: (_)? @error.args) @error.call
        ]
    """
} 