"""CUDA-specific patterns with enhanced type system and relationships.

This module provides CUDA-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern
)
from parsers.models import PATTERN_CATEGORIES
from .common import COMMON_PATTERNS
from .enhanced_patterns import AdaptivePattern, ResilientPattern

# Pattern relationships for CUDA
CUDA_PATTERN_RELATIONSHIPS = {
    "kernel_definition": [
        PatternRelationship(
            source_pattern="kernel_definition",
            target_pattern="memory_management",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"gpu_memory": True}
        ),
        PatternRelationship(
            source_pattern="kernel_definition",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"best_practice": True}
        )
    ],
    "memory_management": [
        PatternRelationship(
            source_pattern="memory_management",
            target_pattern="synchronization",
            relationship_type=PatternRelationType.REQUIRES,
            confidence=0.9,
            metadata={"memory_sync": True}
        )
    ],
    "synchronization": [
        PatternRelationship(
            source_pattern="synchronization",
            target_pattern="kernel_definition",
            relationship_type=PatternRelationType.SUPPORTS,
            confidence=0.95,
            metadata={"kernel_sync": True}
        )
    ]
}

# Performance metrics tracking for CUDA patterns
CUDA_PATTERN_METRICS = {
    "kernel_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "memory_management": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "synchronization": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced CUDA patterns with proper typing and relationships
CUDA_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "kernel_definition": ResilientPattern(
                name="kernel_definition",
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
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cuda",
                confidence=0.95,
                metadata={
                    "relationships": CUDA_PATTERN_RELATIONSHIPS["kernel_definition"],
                    "metrics": CUDA_PATTERN_METRICS["kernel_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
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
            "memory_management": ResilientPattern(
                name="memory_management",
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
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cuda",
                confidence=0.95,
                metadata={
                    "relationships": CUDA_PATTERN_RELATIONSHIPS["memory_management"],
                    "metrics": CUDA_PATTERN_METRICS["memory_management"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "synchronization": ResilientPattern(
                name="synchronization",
                pattern="""
                [
                    (call_expression
                        function: (identifier) @semantics.sync.func
                        (#match? @semantics.sync.func "^(__syncthreads|__syncwarp|__syncthreads_count|__syncthreads_and|__syncthreads_or)$")
                        arguments: (_)? @semantics.sync.args) @semantics.sync.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cuda",
                confidence=0.95,
                metadata={
                    "relationships": CUDA_PATTERN_RELATIONSHIPS["synchronization"],
                    "metrics": CUDA_PATTERN_METRICS["synchronization"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comments": AdaptivePattern(
                name="comments",
                pattern="""
                [
                    (comment) @documentation.comment.single,
                    (comment_multiline) @documentation.comment.multi
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cuda",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="kernel_definition",
                            relationship_type=PatternRelationType.COMPLEMENTS,
                            confidence=0.8
                        )
                    ],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
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

def create_pattern_context(file_path: str, code_structure: Dict[str, Any]) -> PatternContext:
    """Create pattern context for CUDA files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "cuda", "version": "11.0"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CUDA_PATTERNS.keys())
    )

def get_cuda_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return CUDA_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_cuda_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in CUDA_PATTERN_METRICS:
        pattern_metrics = CUDA_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_cuda_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_cuda_pattern_relationships(pattern_name),
        performance=CUDA_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "cuda"}
    )

# Export public interfaces
__all__ = [
    'CUDA_PATTERNS',
    'CUDA_PATTERN_RELATIONSHIPS',
    'CUDA_PATTERN_METRICS',
    'create_pattern_context',
    'get_cuda_pattern_relationships',
    'update_cuda_pattern_metrics',
    'get_cuda_pattern_match_result'
] 