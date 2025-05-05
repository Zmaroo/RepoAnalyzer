"""Shared patterns between JavaScript and TypeScript with enhanced type system and relationships.

This module provides patterns that are common between JavaScript and TypeScript,
integrating with the enhanced pattern processing system, including support for both
tree-sitter and regex parsers, proper typing, relationships, and context.
"""

from typing import Dict, Any, List, Optional, Union, Set, Callable
from dataclasses import dataclass, field
import re
import os
import time
import json
from collections import defaultdict

from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType, ExtractedBlock, BlockType
)
from parsers.models import PATTERN_CATEGORIES
from .common import (
    COMMON_PATTERNS, COMMON_CAPABILITIES,
    process_tree_sitter_pattern, validate_tree_sitter_pattern, create_tree_sitter_context
)
from .enhanced_patterns import (
    TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern, 
    TreeSitterCrossProjectPatternLearner, DATA_DIR
)
from .tree_sitter_utils import execute_tree_sitter_query, count_nodes, extract_captures
from .recovery_strategies import get_recovery_strategies
from .learning_strategies import get_learning_strategies
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
import asyncio
from parsers.pattern_processor import pattern_processor
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import BaseFeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor

# JS/TS shared capabilities (extends common capabilities)
JS_TS_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.DYNAMIC_ANALYSIS,
    AICapability.MODULE_RESOLUTION
}

# Pattern relationships for shared JS/TS patterns
JS_TS_PATTERN_RELATIONSHIPS = {
    "function_definition": [
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.9,
            metadata={"documentation": True}
        )
    ],
    "class_definition": [
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="method_definition",
            relationship_type=PatternRelationType.CONTAINS,
            confidence=0.95,
            metadata={"class_members": True}
        ),
        PatternRelationship(
            source_pattern="class_definition",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.9,
            metadata={"documentation": True}
        )
    ],
    "module_exports": [
        PatternRelationship(
            source_pattern="module_exports",
            target_pattern="function_definition",
            relationship_type=PatternRelationType.EXPORTS,
            confidence=0.95,
            metadata={"module_system": True}
        ),
        PatternRelationship(
            source_pattern="module_exports",
            target_pattern="class_definition",
            relationship_type=PatternRelationType.EXPORTS,
            confidence=0.95,
            metadata={"module_system": True}
        )
    ]
}

# Performance metrics tracking for shared JS/TS patterns
JS_TS_PATTERN_METRICS = {
    "function_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "class_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "module_exports": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced shared patterns with proper typing and relationships
JS_TS_SHARED_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            **COMMON_PATTERNS[PatternCategory.SYNTAX][PatternPurpose.UNDERSTANDING],  # Inherit common syntax patterns
            "function_definition": QueryPattern(
                name="function_definition",
                pattern="""
                [
                    (function_declaration
                        name: (identifier) @syntax.function.name
                        parameters: (formal_parameters) @syntax.function.params
                        body: (statement_block) @syntax.function.body) @syntax.function.def,
                    
                    (arrow_function
                        parameters: (formal_parameters) @syntax.arrow.params
                        body: [(statement_block) (expression)] @syntax.arrow.body) @syntax.arrow.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="javascript",
                confidence=0.95,
                extract=lambda m: {
                    "type": "function",
                    "name": m["captures"]["syntax.function.name"]["text"] 
                            if "syntax.function.name" in m.get("captures", {}) 
                            else "anonymous",
                    "params": m["captures"]["syntax.function.params"]["text"] 
                             if "syntax.function.params" in m.get("captures", {}) 
                             else m["captures"]["syntax.arrow.params"]["text"] 
                             if "syntax.arrow.params" in m.get("captures", {})
                             else "",
                    "is_arrow": "syntax.arrow.def" in m.get("captures", {}),
                    "body_type": "block" if "syntax.function.body" in m.get("captures", {})
                                else "expression" if "syntax.arrow.body" in m.get("captures", {})
                                else "unknown"
                },
                block_type="function",
                contains_blocks=["function", "conditional", "loop"],
                is_nestable=True,
                extraction_priority=10,
                metadata={
                    "relationships": JS_TS_PATTERN_RELATIONSHIPS["function_definition"],
                    "metrics": JS_TS_PATTERN_METRICS["function_definition"],
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches function declarations and arrow functions in JavaScript/TypeScript",
                    "examples": [
                        "function example() { return true; }",
                        "const arrow = () => true;"
                    ],
                    "version": "1.0",
                    "tags": ["function", "arrow", "declaration", "method"]
                },
                test_cases=[
                    {
                        "input": "function test() { return true; }",
                        "expected": {
                            "type": "function",
                            "name": "test",
                            "is_arrow": False
                        }
                    },
                    {
                        "input": "const arrow = () => true;",
                        "expected": {
                            "type": "function",
                            "is_arrow": True,
                            "body_type": "expression"
                        }
                    }
                ]
            ),
            
            "class_definition": QueryPattern(
                name="class_definition",
                pattern="""
                [
                    (class_declaration
                        name: (identifier) @syntax.class.name
                        extends: (class_heritage)? @syntax.class.extends
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                    
                    (method_definition
                        name: (property_identifier) @syntax.method.name
                        parameters: (formal_parameters) @syntax.method.params
                        body: (statement_block) @syntax.method.body) @syntax.method.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="javascript",
                confidence=0.95,
                extract=lambda m: {
                    "type": "class" if "syntax.class.def" in m.get("captures", {}) else "method",
                    "name": m["captures"]["syntax.class.name"]["text"] 
                            if "syntax.class.name" in m.get("captures", {}) 
                            else m["captures"]["syntax.method.name"]["text"] 
                            if "syntax.method.name" in m.get("captures", {})
                            else "",
                    "extends": m["captures"]["syntax.class.extends"]["text"] 
                               if "syntax.class.extends" in m.get("captures", {}) 
                               else None,
                    "has_methods": "syntax.class.body" in m.get("captures", {}) and 
                                   "method_definition" in m["captures"]["syntax.class.body"]["text"]
                },
                block_type="class",
                contains_blocks=["method", "property", "constructor"],
                is_nestable=True,
                extraction_priority=20,
                metadata={
                    "relationships": JS_TS_PATTERN_RELATIONSHIPS["class_definition"],
                    "metrics": JS_TS_PATTERN_METRICS["class_definition"],
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches class declarations and method definitions in JavaScript/TypeScript",
                    "examples": [
                        "class MyClass { method() {} }",
                        "class Child extends Parent {}"
                    ],
                    "version": "1.0",
                    "tags": ["class", "method", "oop", "inheritance"]
                },
                test_cases=[
                    {
                        "input": "class Example { constructor() {} }",
                        "expected": {
                            "type": "class",
                            "name": "Example",
                            "has_methods": True
                        }
                    },
                    {
                        "input": "class Child extends Parent {}",
                        "expected": {
                            "type": "class",
                            "name": "Child",
                            "extends": "Parent"
                        }
                    }
                ]
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "module_exports": QueryPattern(
                name="module_exports",
                pattern="""
                [
                    (assignment_expression
                        left: (member_expression
                            object: (identifier) @semantics.module.object
                            property: (property_identifier) @semantics.module.property)
                        right: (_) @semantics.module.value) @semantics.module.exports,
                    
                    (export_statement
                        declaration: (_) @semantics.export.value) @semantics.export.statement
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="javascript",
                confidence=0.9,
                extract=lambda m: {
                    "type": "export",
                    "method": "module.exports" if "semantics.module.exports" in m.get("captures", {})
                              else "export_statement",
                    "name": m["captures"]["semantics.module.property"]["text"] 
                            if "semantics.module.property" in m.get("captures", {})
                            else "",
                    "exported_value": m["captures"]["semantics.module.value"]["text"] 
                                      if "semantics.module.value" in m.get("captures", {})
                                      else m["captures"]["semantics.export.value"]["text"]
                                      if "semantics.export.value" in m.get("captures", {})
                                      else ""
                },
                block_type="export",
                is_nestable=False,
                extraction_priority=5,
                metadata={
                    "relationships": JS_TS_PATTERN_RELATIONSHIPS["module_exports"],
                    "metrics": JS_TS_PATTERN_METRICS["module_exports"],
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches module exports and export statements in JavaScript/TypeScript",
                    "examples": [
                        "module.exports = MyClass;",
                        "export const myFunction = () => {};"
                    ],
                    "version": "1.0",
                    "tags": ["export", "module", "commonjs", "es6-module"]
                },
                test_cases=[
                    {
                        "input": "module.exports = { func1, func2 };",
                        "expected": {
                            "type": "export",
                            "method": "module.exports"
                        }
                    },
                    {
                        "input": "export default class MyComponent {}",
                        "expected": {
                            "type": "export",
                            "method": "export_statement"
                        }
                    }
                ]
            ),
            
            "variable_declaration": QueryPattern(
                name="variable_declaration",
                pattern="""
                [
                    (variable_declaration
                        kind: [(const) (let) (var)] @semantics.var.kind
                        declarator: (variable_declarator
                            name: (identifier) @semantics.var.name
                            value: (_)? @semantics.var.value)) @semantics.var.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="javascript",
                confidence=0.9,
                extract=lambda m: {
                    "type": "variable",
                    "kind": m["captures"]["semantics.var.kind"]["text"] if "semantics.var.kind" in m.get("captures", {}) else "",
                    "name": m["captures"]["semantics.var.name"]["text"] if "semantics.var.name" in m.get("captures", {}) else "",
                    "has_value": "semantics.var.value" in m.get("captures", {}),
                    "is_const": "semantics.var.kind" in m.get("captures", {}) and 
                                m["captures"]["semantics.var.kind"]["text"] == "const"
                },
                block_type="variable",
                is_nestable=False,
                extraction_priority=3,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches variable declarations in JavaScript/TypeScript",
                    "examples": [
                        "const x = 5;",
                        "let user = { name: 'John' };",
                        "var oldStyle;"
                    ],
                    "version": "1.0",
                    "tags": ["variable", "const", "let", "var", "declaration"]
                },
                test_cases=[
                    {
                        "input": "const API_KEY = 'abc123';",
                        "expected": {
                            "type": "variable",
                            "kind": "const",
                            "name": "API_KEY",
                            "is_const": True
                        }
                    },
                    {
                        "input": "let counter = 0;",
                        "expected": {
                            "type": "variable",
                            "kind": "let",
                            "has_value": True,
                            "is_const": False
                        }
                    }
                ]
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comments": QueryPattern(
                name="comments",
                pattern="""
                [
                    (comment) @documentation.comment
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="javascript",
                confidence=0.9,
                extract=lambda m: {
                    "type": "comment",
                    "content": m["captures"]["documentation.comment"]["text"] if "documentation.comment" in m.get("captures", {}) else "",
                    "is_jsdoc": m["captures"]["documentation.comment"]["text"].startswith("/**") if "documentation.comment" in m.get("captures", {}) else False,
                    "is_block": m["captures"]["documentation.comment"]["text"].startswith("/*") if "documentation.comment" in m.get("captures", {}) else False,
                    "is_line": m["captures"]["documentation.comment"]["text"].startswith("//") if "documentation.comment" in m.get("captures", {}) else False,
                    "line": m.get("line", 0)
                },
                block_type="comment",
                is_nestable=False,
                extraction_priority=1,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches comments in JavaScript/TypeScript including JSDoc",
                    "examples": [
                        "// Line comment",
                        "/* Block comment */",
                        "/** JSDoc comment */"
                    ],
                    "version": "1.0",
                    "tags": ["comment", "documentation", "jsdoc"]
                },
                test_cases=[
                    {
                        "input": "// TODO: Fix this later",
                        "expected": {
                            "type": "comment",
                            "is_line": True,
                            "is_jsdoc": False
                        }
                    },
                    {
                        "input": "/** @param {string} name - The user's name */",
                        "expected": {
                            "type": "comment",
                            "is_jsdoc": True
                        }
                    },
                    {
                        "input": "/* Multi-line\n   comment */",
                        "expected": {
                            "type": "comment",
                            "is_block": True
                        }
                    }
                ]
            )
        }
    }
}

async def create_js_ts_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None,
    parser_type: ParserType = ParserType.TREE_SITTER
) -> PatternContext:
    """Create pattern context for JS/TS files with support for both parser types.
    
    Args:
        file_path: Path to the file being processed
        code_structure: AST or parsed structure information
        learned_patterns: Optional dictionary of learned patterns
        parser_type: The parser type being used (defaults to tree-sitter for JS/TS)
        
    Returns:
        PatternContext with appropriate settings for JS/TS processing
    """
    # Get filename to determine exact language (js vs ts)
    filename = os.path.basename(file_path)
    extension = os.path.splitext(filename)[1].lower()
    
    # Determine language
    language_id = "typescript" if extension in [".ts", ".tsx"] else "javascript"
    
    # Create context with proper metadata
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": language_id, "version": "es2022"},
        project_patterns=learned_patterns.keys() if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        extracted_blocks=[],  # Will be populated during processing
        parser_type=parser_type,
        
        # Enhanced context fields
        metadata={
            "file_extension": extension,
            "timestamp": time.time(),
            "filename": filename
        },
        validation_results={},
        pattern_stats={},
        block_types=[],
        relationships={},
        ai_capabilities=JS_TS_CAPABILITIES,
        language_id=language_id,
        file_type=FileType.CODE
    )
    
    return context

def get_js_ts_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return JS_TS_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_js_ts_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in JS_TS_PATTERN_METRICS:
        pattern_metrics = JS_TS_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_js_ts_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_js_ts_pattern_relationships(pattern_name),
        performance=JS_TS_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "javascript"}
    )

# Export public interfaces
__all__ = [
    'JS_TS_SHARED_PATTERNS',
    'JS_TS_PATTERN_RELATIONSHIPS',
    'JS_TS_PATTERN_METRICS',
    'JS_TS_CAPABILITIES',
    'create_js_ts_pattern_context',
    'get_js_ts_pattern_relationships',
    'update_js_ts_pattern_metrics',
    'get_js_ts_pattern_match_result',
    'process_js_ts_pattern',
    'validate_js_ts_pattern'
]

# Module identification
LANGUAGE = "javascript"

class JSTSPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced JS/TS pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        super().__init__()
        self._feature_extractor = None
        self._pattern_processor = pattern_processor
        self._ai_processor = None
        self._block_extractor = None
        self._unified_parser = None
        self._learning_strategies = get_learning_strategies()
        self._recovery_strategies = get_recovery_strategies()
        self._metrics = {
            "total_patterns": 0,
            "learned_patterns": 0,
            "failed_patterns": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "learning_times": [],
            "strategy_metrics": {
                "learning": {},
                "recovery": {}
            }
        }
        # Ensure insights directory exists
        self.insights_path = os.path.join(DATA_DIR, "javascript_pattern_insights.json")
        os.makedirs(DATA_DIR, exist_ok=True)
        register_shutdown_handler(self.cleanup)

    async def initialize(self):
        """Initialize with JS/TS-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Load previously saved insights
        await self._load_insights()
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("javascript", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register JS/TS patterns
        await self._pattern_processor.register_language_patterns(
            "javascript", 
            JS_TS_SHARED_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "javascript_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(JS_TS_SHARED_PATTERNS),
                "capabilities": list(JS_TS_CAPABILITIES),
                "insights_loaded": len(self.project_insights) if hasattr(self, "project_insights") else 0
            }
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for JS/TS."""
        # Try tree-sitter first
        tree_sitter_parser = await get_tree_sitter_parser("javascript")  # Use JS parser as base
        if tree_sitter_parser:
            return tree_sitter_parser
            
        # Fallback to unified parser
        return await self._unified_parser.get_parser("javascript", FileType.CODE)

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="javascript",
                file_type=FileType.CODE,
                interaction_type=InteractionType.LEARNING,
                repository_id=None,
                file_path=project_path
            )
            
            ai_result = await self._ai_processor.process_with_ai(
                source_code="",  # Will be filled by processor
                context=ai_context
            )
            
            learned_patterns = []
            if ai_result.success:
                learned_patterns.extend(ai_result.learned_patterns)
                self._metrics["learned_patterns"] += len(ai_result.learned_patterns)
            
            # Then do cross-project learning through base class
            project_patterns = await self._extract_project_patterns(project_path)
            await self._integrate_patterns(project_patterns, project_path)
            learned_patterns.extend(project_patterns)
            
            # Finally add JS/TS-specific patterns
            async with AsyncErrorBoundary("javascript_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "javascript",
                    "",  # Will be filled from files
                    None
                )
                
                # Extract features with metrics
                features = []
                for block in blocks:
                    block_features = await self._feature_extractor.extract_features(
                        block.content,
                        block.metadata
                    )
                    features.append(block_features)
                
                # Learn patterns from features
                js_ts_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(js_ts_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "javascript_pattern_learner",
                ComponentStatus.HEALTHY,
                details={
                    "learned_patterns": len(learned_patterns),
                    "learning_time": learning_time
                }
            )
            
            return learned_patterns
            
        except Exception as e:
            self._metrics["failed_patterns"] += 1
            await log(f"Error learning patterns: {e}", level="error")
            
            # Update health status
            await global_health_monitor.update_component_status(
                "javascript_pattern_learner",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": str(e)}
            )
            
            return []

    async def _learn_patterns_from_features(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Learn patterns from extracted features with strategy application."""
        patterns = await super()._learn_patterns_from_features(features)
        
        # Apply learning strategies to improve patterns
        improved_patterns = []
        for pattern_data in patterns:
            pattern_str = pattern_data.get("pattern", "")
            insights = pattern_data.get("insights", {})
            
            # Try each learning strategy in sequence
            for strategy_name, strategy in self._learning_strategies.items():
                try:
                    improved = await strategy.apply(pattern_str, insights, "javascript")
                    if improved:
                        pattern_data["pattern"] = improved["pattern"]
                        pattern_data["confidence"] = improved["confidence"]
                        
                        # Update learning strategy metrics
                        if strategy_name not in self._metrics["strategy_metrics"]["learning"]:
                            self._metrics["strategy_metrics"]["learning"][strategy_name] = {
                                "attempts": 0,
                                "improvements": 0,
                                "success_rate": 0.0
                            }
                        
                        metrics = self._metrics["strategy_metrics"]["learning"][strategy_name]
                        metrics["attempts"] += 1
                        metrics["improvements"] += 1
                        metrics["success_rate"] = metrics["improvements"] / metrics["attempts"]
                
                except Exception as e:
                    await log(
                        f"Error applying learning strategy {strategy_name}: {e}",
                        level="warning",
                        context={"language": "javascript"}
                    )
            
            # Apply recovery strategies if needed
            if pattern_data.get("confidence", 1.0) < 0.8:
                for strategy_name, strategy in self._recovery_strategies.items():
                    try:
                        recovered = await strategy.apply(
                            pattern_str,
                            pattern_data.get("name", "unnamed_pattern"),
                            tree_sitter_parser=self._unified_parser.get_parser("javascript"),
                            extract_fn=pattern_data.get("extract")
                        )
                        
                        if recovered and recovered.get("success"):
                            pattern_data["pattern"] = recovered["pattern"]
                            pattern_data["is_recovered"] = True
                            pattern_data["recovery_strategy"] = strategy_name
                            
                            # Update recovery strategy metrics
                            if strategy_name not in self._metrics["strategy_metrics"]["recovery"]:
                                self._metrics["strategy_metrics"]["recovery"][strategy_name] = {
                                    "attempts": 0,
                                    "successes": 0,
                                    "success_rate": 0.0
                                }
                            
                            metrics = self._metrics["strategy_metrics"]["recovery"][strategy_name]
                            metrics["attempts"] += 1
                            metrics["successes"] += 1
                            metrics["success_rate"] = metrics["successes"] / metrics["attempts"]
                            
                            break  # Stop after first successful recovery
                    
                    except Exception as e:
                        await log(
                            f"Error applying recovery strategy {strategy_name}: {e}",
                            level="warning",
                            context={"language": "javascript"}
                        )
            
            improved_patterns.append(pattern_data)
        
        return improved_patterns

    async def suggest_patterns(self, context: PatternContext) -> List[QueryPattern]:
        """Suggest patterns based on cross-project learning and common patterns."""
        # Get cross-project suggestions
        suggested_patterns = await super().suggest_patterns(context)
        
        # Add relevant common patterns
        for pattern in COMMON_PATTERNS.values():
            if pattern.language_id in ("*", "javascript", "typescript"):
                suggested_patterns.append(pattern)
        
        # Validate suggestions
        validated_patterns = []
        for pattern in suggested_patterns:
            validation_result = await self._pattern_processor.validate_pattern(
                pattern,
                language_id="javascript",
                context=context
            )
            if validation_result.is_valid:
                validated_patterns.append(pattern)
        
        return validated_patterns

    async def cleanup(self):
        """Clean up pattern learner resources."""
        try:
            # Save insights before cleanup
            await self._save_insights()
            
            # Clean up base class resources
            await super().cleanup()
            
            # Clean up specific components
            if self._feature_extractor:
                await self._feature_extractor.cleanup()
            if self._block_extractor:
                await self._block_extractor.cleanup()
            if self._unified_parser:
                await self._unified_parser.cleanup()
            if self._ai_processor:
                await self._ai_processor.cleanup()
            
            # Update final status
            await global_health_monitor.update_component_status(
                "javascript_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "javascript_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
            
    async def _load_insights(self) -> None:
        """Load previously saved JavaScript pattern insights."""
        try:
            if os.path.exists(self.insights_path):
                with open(self.insights_path, 'r') as f:
                    data = json.load(f)
                    
                    # Load data
                    self.project_insights = data.get("project_insights", {})
                    self.pattern_improvements = defaultdict(list, data.get("pattern_improvements", {}))
                    self.training_projects = set(data.get("training_projects", []))
                    self.pattern_variations = defaultdict(
                        lambda: {ParserType.TREE_SITTER.value: [], ParserType.CUSTOM.value: []},
                        data.get("pattern_variations", {})
                    )
                    self.metrics = data.get("metrics", self._metrics)
                    
                await log(
                    "Loaded JavaScript pattern learner insights", 
                    level="info",
                    context={
                        "projects": len(self.project_insights),
                        "improvements": sum(len(imps) for imps in self.pattern_improvements.values())
                    }
                )
        except Exception as e:
            await log(
                f"Error loading JavaScript pattern learner insights: {e}",
                level="warning"
            )
            
    async def _save_insights(self) -> None:
        """Save JavaScript pattern learner insights."""
        try:
            # Prepare data for serialization
            data = {
                "project_insights": self.project_insights,
                "pattern_improvements": {k: list(v) for k, v in self.pattern_improvements.items()},
                "training_projects": list(self.training_projects),
                "pattern_variations": self.pattern_variations,
                "metrics": self._metrics,
                "last_updated": time.time()
            }
            
            # Save to file
            with open(self.insights_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            await log(
                "Saved JavaScript pattern learner insights",
                level="info"
            )
        except Exception as e:
            await log(
                f"Error saving JavaScript pattern learner insights: {e}",
                level="error"
            )

# Initialize pattern learner
js_ts_pattern_learner = JSTSPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_js_ts_pattern(
    pattern: Union[QueryPattern, TreeSitterPattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a JS/TS pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_tree_sitter_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to JS/TS-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("javascript", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "javascript", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_js_ts_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks
        blocks = await block_extractor.get_child_blocks(
            "javascript",
            source_code,
            context.code_structure if context else None
        )
        
        # Process blocks and extract features
        matches = []
        start_time = time.time()
        
        for block in blocks:
            block_matches = await pattern.matches(block.content)
            if block_matches:
                # Extract features for each match
                for match in block_matches:
                    features = await feature_extractor.extract_features(
                        block.content,
                        match
                    )
                    match["features"] = features
                    match["block"] = block.__dict__
                matches.extend(block_matches)
        
        # Update pattern metrics
        await update_js_ts_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        return matches

# Update initialization
async def initialize_js_ts_patterns():
    """Initialize JS/TS patterns during app startup."""
    global js_ts_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register JS/TS patterns
    await pattern_processor.register_language_patterns(
        "javascript",
        JS_TS_SHARED_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": JS_TS_CAPABILITIES,
            "languages": ["javascript", "typescript"],
            "file_extensions": [".js", ".jsx", ".ts", ".tsx"]
        }
    )
    
    # Create and initialize learner
    js_ts_pattern_learner = JSTSPatternLearner()
    await js_ts_pattern_learner.initialize()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "javascript",
        js_ts_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "javascript_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(JS_TS_SHARED_PATTERNS),
            "capabilities": list(JS_TS_CAPABILITIES),
            "pattern_types": "QueryPattern",
            "parser_type": "tree-sitter"
        }
    )

async def extract_js_ts_features(
    pattern: Union[QueryPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from pattern matches."""
    feature_extractor = await BaseFeatureExtractor.create("javascript", FileType.CODE)
    
    features = ExtractedFeatures()
    
    for match in matches:
        # Extract features based on pattern category
        if pattern.category == PatternCategory.SYNTAX:
            syntax_features = await feature_extractor._extract_syntax_features(
                match,
                context
            )
            features.update(syntax_features)
            
        elif pattern.category == PatternCategory.SEMANTICS:
            semantic_features = await feature_extractor._extract_semantic_features(
                match,
                context
            )
            features.update(semantic_features)
    
    return features

async def validate_js_ts_pattern(
    pattern: Union[QueryPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a JS/TS pattern with system integration."""
    # First try common pattern validation
    common_result = await validate_tree_sitter_pattern(pattern, context)
    if common_result.is_valid:
        return common_result
    
    # Fall back to JS/TS-specific validation
    async with AsyncErrorBoundary("javascript_pattern_validation"):
        # Get pattern processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="javascript",
            context=context
        )
        
        # Update pattern metrics
        if not validation_result.is_valid:
            pattern_metrics = JS_TS_PATTERN_METRICS.get(pattern.name)
            if pattern_metrics:
                pattern_metrics.error_count += 1
        
        return validation_result
