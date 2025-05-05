"""
TypeScript pattern definitions for RepoAnalyzer.
This module defines patterns specific to TypeScript syntax and semantics.
"""

import os
from typing import Dict, List, Optional, Union, Any

from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternPerformanceMetrics, PatternValidationResult,
    PatternMatchResult, QueryPattern, FileType, ParserType
)
from utils.health_monitor import global_health_monitor, ComponentStatus
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from .common import (
    COMMON_PATTERNS,
    process_tree_sitter_pattern,
    validate_tree_sitter_pattern,
    create_tree_sitter_context
)
from .enhanced_patterns import (
    TreeSitterPattern, 
    TreeSitterAdaptivePattern, 
    TreeSitterResilientPattern, 
    TreeSitterCrossProjectPatternLearner, 
    DATA_DIR
)
from .tree_sitter_utils import execute_tree_sitter_query, count_nodes, extract_captures
from .recovery_strategies import get_recovery_strategies
from .learning_strategies import get_learning_strategies
from .js_ts_shared import (
    JS_TS_SHARED_PATTERNS, JSTSPatternLearner,
    JS_TS_CAPABILITIES, create_js_ts_pattern_context
)

# Constants
LANGUAGE = "typescript"

# TypeScript-specific patterns
TYPESCRIPT_SPECIFIC_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "interface_definition": TreeSitterPattern(
                name="interface_definition",
                pattern="""
                [
                    (interface_declaration
                        name: (type_identifier) @syntax.interface.name
                        body: (object_type) @syntax.interface.body) @syntax.interface.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                extract=lambda m: {
                    "type": "interface",
                    "name": m["captures"]["syntax.interface.name"]["text"] if "syntax.interface.name" in m.get("captures", {}) else "",
                    "body_length": len(m["captures"]["syntax.interface.body"]["text"]) if "syntax.interface.body" in m.get("captures", {}) else 0,
                    "properties_count": m["captures"]["syntax.interface.body"]["text"].count(":") if "syntax.interface.body" in m.get("captures", {}) else 0
                },
                regex_pattern=r'interface\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:extends\s+[^{]+)?\s*\{',
                block_type="interface",
                contains_blocks=["property_signature", "method_signature"],
                is_nestable=True,
                extraction_priority=18,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches TypeScript interface declarations",
                    "examples": [
                        "interface User { id: number; name: string; }",
                        "interface Config extends BaseConfig { }"
                    ],
                    "version": "1.0",
                    "tags": ["interface", "typescript", "declaration", "type"]
                },
                test_cases=[
                    {
                        "input": "interface User { id: number; name: string; }",
                        "expected": {
                            "type": "interface",
                            "name": "User",
                            "properties_count": 2
                        }
                    },
                    {
                        "input": "interface Empty { }",
                        "expected": {
                            "type": "interface",
                            "name": "Empty",
                            "properties_count": 0
                        }
                    }
                ]
            ),
            
            "type_definition": TreeSitterPattern(
                name="type_definition",
                pattern="""
                [
                    (type_alias_declaration
                        name: (type_identifier) @syntax.type.name
                        value: (_) @syntax.type.value) @syntax.type.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                extract=lambda m: {
                    "type": "type_alias",
                    "name": m["captures"]["syntax.type.name"]["text"] if "syntax.type.name" in m.get("captures", {}) else "",
                    "definition": m["captures"]["syntax.type.value"]["text"] if "syntax.type.value" in m.get("captures", {}) else "",
                    "is_union": "|" in m["captures"]["syntax.type.value"]["text"] if "syntax.type.value" in m.get("captures", {}) else False,
                    "is_intersection": "&" in m["captures"]["syntax.type.value"]["text"] if "syntax.type.value" in m.get("captures", {}) else False
                },
                regex_pattern=r'type\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*',
                block_type="type_alias",
                is_nestable=False,
                extraction_priority=16,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches TypeScript type alias declarations",
                    "examples": [
                        "type ID = string | number;",
                        "type User = { id: ID; name: string; }"
                    ],
                    "version": "1.0",
                    "tags": ["type", "alias", "typescript", "declaration"]
                },
                test_cases=[
                    {
                        "input": "type ID = string | number;",
                        "expected": {
                            "type": "type_alias",
                            "name": "ID",
                            "is_union": True,
                            "is_intersection": False
                        }
                    },
                    {
                        "input": "type UserMetadata = User & Timestamps;",
                        "expected": {
                            "type": "type_alias",
                            "name": "UserMetadata",
                            "is_union": False,
                            "is_intersection": True
                        }
                    }
                ]
            ),
            
            "generic_function": TreeSitterPattern(
                name="generic_function",
                pattern="""
                [
                    (function_declaration
                        type_parameters: (type_parameters) @syntax.generic.params
                        name: (identifier) @syntax.generic.name
                        parameters: (formal_parameters) @syntax.generic.args) @syntax.generic.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                extract=lambda m: {
                    "type": "generic_function",
                    "name": m["captures"]["syntax.generic.name"]["text"] if "syntax.generic.name" in m.get("captures", {}) else "",
                    "type_params": m["captures"]["syntax.generic.params"]["text"] if "syntax.generic.params" in m.get("captures", {}) else "",
                    "param_count": m["captures"]["syntax.generic.args"]["text"].count(",") + 1 if "syntax.generic.args" in m.get("captures", {}) and m["captures"]["syntax.generic.args"]["text"].strip() != "()" else 0
                },
                regex_pattern=r'function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*<\s*([^>]+)\s*>\s*\([^)]*\)',
                block_type="function",
                contains_blocks=["statement", "expression"],
                is_nestable=True,
                extraction_priority=14,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches TypeScript generic function declarations",
                    "examples": [
                        "function identity<T>(value: T): T { return value; }",
                        "function merge<T, U>(obj1: T, obj2: U): T & U { }"
                    ],
                    "version": "1.0",
                    "tags": ["generic", "function", "typescript"]
                },
                test_cases=[
                    {
                        "input": "function identity<T>(value: T): T { return value; }",
                        "expected": {
                            "type": "generic_function",
                            "name": "identity",
                            "param_count": 1
                        }
                    },
                    {
                        "input": "function merge<T, U>(obj1: T, obj2: U): T & U { }",
                        "expected": {
                            "type": "generic_function",
                            "name": "merge",
                            "param_count": 2
                        }
                    }
                ]
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "property_type_annotation": TreeSitterPattern(
                name="property_type_annotation",
                pattern="""
                [
                    (property_signature
                        name: (_) @semantics.prop.name
                        type: (type_annotation
                            type: (_) @semantics.prop.type)) @semantics.prop.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                extract=lambda m: {
                    "type": "property_type",
                    "property_name": m["captures"]["semantics.prop.name"]["text"] if "semantics.prop.name" in m.get("captures", {}) else "",
                    "type_annotation": m["captures"]["semantics.prop.type"]["text"] if "semantics.prop.type" in m.get("captures", {}) else "",
                    "is_optional": m["captures"]["semantics.prop.def"]["text"].find("?:") > 0 if "semantics.prop.def" in m.get("captures", {}) else False
                },
                regex_pattern=r'([a-zA-Z_$][a-zA-Z0-9_$]*)\??:\s*([^;,\{\}]+)',
                block_type="property",
                is_nestable=False,
                extraction_priority=10,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches TypeScript property type annotations",
                    "examples": [
                        "id: number;",
                        "name?: string;"
                    ],
                    "version": "1.0",
                    "tags": ["property", "type", "annotation", "typescript"]
                },
                test_cases=[
                    {
                        "input": "id: number;",
                        "expected": {
                            "type": "property_type",
                            "property_name": "id",
                            "type_annotation": "number",
                            "is_optional": False
                        }
                    },
                    {
                        "input": "name?: string;",
                        "expected": {
                            "type": "property_type",
                            "property_name": "name",
                            "type_annotation": "string",
                            "is_optional": True
                        }
                    }
                ]
            )
        }
    }
}

# Combine shared patterns with TypeScript-specific patterns
TYPESCRIPT_PATTERNS = {
    **JS_TS_SHARED_PATTERNS,
    **TYPESCRIPT_SPECIFIC_PATTERNS
}

class TypeScriptPatternLearner(JSTSPatternLearner):
    """Pattern learner specialized for TypeScript code."""
    
    def __init__(self):
        super().__init__(language_id=LANGUAGE)
        self.insights_path = os.path.join(DATA_DIR, "typescript_pattern_insights.json")
        
    async def initialize(self):
        """Initialize with TypeScript-specific components."""
        await super().initialize()
        
        # Register TypeScript-specific patterns
        from parsers.pattern_processor import register_pattern
        for category, purpose_dict in TYPESCRIPT_SPECIFIC_PATTERNS.items():
            for purpose, patterns in purpose_dict.items():
                for name, pattern in patterns.items():
                    pattern_key = f"{category}:{purpose}:{name}"
                    await register_pattern(pattern_key, pattern)
        
        # Update health monitoring
        await global_health_monitor.update_component_status(
            "typescript_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(TYPESCRIPT_PATTERNS),
                "ts_specific_patterns": len(TYPESCRIPT_SPECIFIC_PATTERNS),
                "capabilities": list(JS_TS_CAPABILITIES)
            }
        )
    
    async def create_context(self, **kwargs):
        """Create TypeScript-specific pattern context."""
        return create_js_ts_pattern_context(language_id=LANGUAGE, **kwargs)

# Initialize pattern learner
typescript_pattern_learner = TypeScriptPatternLearner()