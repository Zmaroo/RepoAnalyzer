"""JavaScript-specific patterns with enhanced type system and relationships.

This module provides JavaScript-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

import os
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from parsers.pattern_processor import pattern_processor
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
    JS_TS_SHARED_PATTERNS,
    JS_TS_CAPABILITIES,
    JSTSPatternLearner,
    process_js_ts_pattern,
    extract_js_ts_features,
    validate_js_ts_pattern,
    create_js_ts_pattern_context
)
from .react import ReactAnalyzer, react_analyzer
import re

# Module identification - must be before any usage
LANGUAGE = "javascript"

# JavaScript capabilities (extends JS/TS capabilities)
JS_CAPABILITIES = JS_TS_CAPABILITIES | {
    AICapability.NODE_INTEGRATION,
    AICapability.NPM_ECOSYSTEM
}

# JavaScript patterns extend shared patterns
JS_PATTERNS = {
    **JS_TS_SHARED_PATTERNS,  # Inherit shared patterns
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "node_module": TreeSitterAdaptivePattern(
                name="node_module",
                pattern="""
                [
                    (call_expression
                        function: (identifier) @semantics.require.function
                        arguments: (arguments
                            (string) @semantics.require.module)) @semantics.require,
                        
                    (member_expression
                        object: (identifier) @semantics.module.object
                        property: (property_identifier) @semantics.module.property) @semantics.module.exports
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="javascript",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "undefined_variable": QueryPattern(
            name="undefined_variable",
            pattern=r'\b(?:let|const|var)?\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*([^=;\n]+)',
            extract=lambda m: {
                "type": "undefined_variable",
                "variable": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potential undefined variable usage", "examples": ["x = y + 1  // y might be undefined"]}
        ),
        "type_error": QueryPattern(
            name="type_error",
            pattern=r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\.\s*([a-zA-Z_$][a-zA-Z0-9_$]*)',
            extract=lambda m: {
                "type": "type_error",
                "object": m.group(1),
                "property": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potential type errors", "examples": ["obj.nonexistentMethod()"]}
        ),
        "memory_leak": QueryPattern(
            name="memory_leak",
            pattern=r'setInterval\s*\(\s*function\s*\([^)]*\)\s*{\s*([^}]+)\s*}\s*,',
            extract=lambda m: {
                "type": "memory_leak",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.8
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potential memory leaks in intervals", "examples": ["setInterval(function() { /* no clearInterval */ }, 1000)"]}
        ),
        "promise_error": QueryPattern(
            name="promise_error",
            pattern=r'new\s+Promise\s*\(\s*(?:function\s*\([^)]*\)|[^)]+)\s*\)\s*(?!\.catch)',
            extract=lambda m: {
                "type": "promise_error",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.85
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects uncaught promise errors", "examples": ["new Promise((resolve, reject) => { /* no catch */ })"]}
        ),
        "null_reference": QueryPattern(
            name="null_reference",
            pattern=r'(?:null|undefined)\s*\.\s*[a-zA-Z_$][a-zA-Z0-9_$]*',
            extract=lambda m: {
                "type": "null_reference",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects null/undefined references", "examples": ["null.toString()", "undefined.method()"]}
        )
    }
}

# JavaScript-specific patterns (using QueryPattern)
JAVASCRIPT_SPECIFIC_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "js_function_expression": QueryPattern(
                name="js_function_expression",
                pattern="""
                [
                    (function_expression
                        name: (identifier)? @syntax.jsfunc.name
                        parameters: (formal_parameters) @syntax.jsfunc.params
                        body: (statement_block) @syntax.jsfunc.body) @syntax.jsfunc.expr
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                extract=lambda m: {
                    "type": "function_expression",
                    "function_name": m["captures"]["syntax.jsfunc.name"]["text"] if "syntax.jsfunc.name" in m.get("captures", {}) else None,
                    "is_anonymous": "syntax.jsfunc.name" not in m.get("captures", {}),
                    "parameters": m["captures"]["syntax.jsfunc.params"]["text"] if "syntax.jsfunc.params" in m.get("captures", {}) else "()",
                    "body_length": len(m["captures"]["syntax.jsfunc.body"]["text"]) if "syntax.jsfunc.body" in m.get("captures", {}) else 0
                },
                regex_pattern=r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)?\s*\(([^)]*)\)\s*\{',
                block_type="function_expression",
                contains_blocks=["statement", "expression"],
                is_nestable=True,
                extraction_priority=12,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches JavaScript function expressions",
                    "examples": [
                        "const add = function(a, b) { return a + b; }",
                        "function multiply(a, b) { return a * b; }"
                    ],
                    "version": "1.0",
                    "tags": ["function", "expression", "javascript"]
                },
                test_cases=[
                    {
                        "input": "const add = function(a, b) { return a + b; }",
                        "expected": {
                            "type": "function_expression",
                            "is_anonymous": True
                        }
                    },
                    {
                        "input": "function multiply(a, b) { return a * b; }",
                        "expected": {
                            "type": "function_expression",
                            "function_name": "multiply"
                        }
                    }
                ]
            ),
            
            "jsx_in_js": QueryPattern(
                name="jsx_in_js",
                pattern=r'React\.createElement\(|<[A-Z][a-zA-Z]*(?:\s+[a-z][a-zA-Z]*=(?:{[^}]*}|"[^"]*"|\'[^\']*\'))*\s*(?:/>|>)',
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                extract=lambda m: {
                    "type": "jsx_in_js",
                    "component_call": m.group(0),
                    "is_explicit_create": m.group(0).startswith("React.createElement"),
                    "is_component": bool(re.match(r'<[A-Z]', m.group(0))),
                    "is_self_closing": bool(re.search(r'/>$', m.group(0))),
                    "has_props": bool(re.search(r'\s+[a-z][a-zA-Z]*=', m.group(0))),
                    "line_number": m.string.count('\n', 0, m.start()) + 1
                },
                regex_pattern=r'React\.createElement\(|<[A-Z][a-zA-Z]*(?:\s+[a-z][a-zA-Z]*=(?:{[^}]*}|"[^"]*"|\'[^\']*\'))*\s*(?:/>|>)',
                block_type="jsx",
                is_nestable=True,
                extraction_priority=10,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Detects JSX usage in JavaScript files",
                    "examples": [
                        "<Button onClick={handleClick}>Click me</Button>",
                        "<Component prop={value} />",
                        "React.createElement('div', null, 'Hello')",
                        "<App/>",
                        "<User name=\"John\" age={30} isActive={true} />"
                    ],
                    "version": "1.0",
                    "tags": ["jsx", "react", "component"]
                },
                test_cases=[
                    {
                        "input": "<Button onClick={handleClick}>Click me</Button>",
                        "expected": {
                            "type": "jsx_in_js",
                            "is_explicit_create": False,
                            "is_component": True,
                            "is_self_closing": False,
                            "has_props": True
                        }
                    },
                    {
                        "input": "React.createElement('div', null, 'Hello')",
                        "expected": {
                            "type": "jsx_in_js",
                            "is_explicit_create": True
                        }
                    },
                    {
                        "input": "<Component prop={value} />",
                        "expected": {
                            "type": "jsx_in_js",
                            "is_explicit_create": False,
                            "is_component": True,
                            "is_self_closing": True,
                            "has_props": True
                        }
                    },
                    {
                        "input": "<App/>",
                        "expected": {
                            "type": "jsx_in_js",
                            "is_explicit_create": False,
                            "is_component": True,
                            "is_self_closing": True,
                            "has_props": False
                        }
                    }
                ]
            )
        }
    },
    
    PatternCategory.BEST_PRACTICES: {
        PatternPurpose.UNDERSTANDING: {
            "strict_mode": QueryPattern(
                name="strict_mode",
                pattern=r'^\s*[\'"]use strict[\'"]\s*;',
                category=PatternCategory.BEST_PRACTICES,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                extract=lambda m: {
                    "type": "strict_mode",
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "is_file_level": m.start() < 100
                },
                regex_pattern=r'^\s*[\'"]use strict[\'"]\s*;',
                block_type="directive",
                is_nestable=False,
                extraction_priority=2,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Identifies JavaScript strict mode usage",
                    "examples": [
                        "'use strict';",
                        "\"use strict\";"
                    ],
                    "version": "1.0",
                    "tags": ["strict-mode", "best-practice", "javascript"]
                },
                test_cases=[
                    {
                        "input": "'use strict';",
                        "expected": {
                            "type": "strict_mode",
                            "is_file_level": True
                        }
                    },
                    {
                        "input": "function test() {\n  \"use strict\";\n}",
                        "expected": {
                            "type": "strict_mode",
                            "is_file_level": False
                        }
                    }
                ]
            )
        }
    }
}

# Combine JS_PATTERNS and JAVASCRIPT_SPECIFIC_PATTERNS
JAVASCRIPT_PATTERNS = {
    **JS_PATTERNS,
    **JAVASCRIPT_SPECIFIC_PATTERNS
}

class JavaScriptPatternLearner(JSTSPatternLearner):
    """Pattern learner specialized for JavaScript code."""
    
    def __init__(self):
        super().__init__(language_id=LANGUAGE)
        self.insights_path = os.path.join(DATA_DIR, "javascript_pattern_insights.json")
        
    async def initialize(self):
        """Initialize with JavaScript-specific components."""
        await super().initialize()
        
        # Register JavaScript-specific patterns
        from parsers.pattern_processor import register_pattern
        for category, purpose_dict in JAVASCRIPT_SPECIFIC_PATTERNS.items():
            for purpose, patterns in purpose_dict.items():
                for name, pattern in patterns.items():
                    pattern_key = f"{category}:{purpose}:{name}"
                    await register_pattern(pattern_key, pattern)
        
        # Update health monitoring for JavaScript specifically
        from utils.health_monitor import global_health_monitor, ComponentStatus
        await global_health_monitor.update_component_status(
            "javascript_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(JAVASCRIPT_PATTERNS),
                "js_specific_patterns": len(JAVASCRIPT_SPECIFIC_PATTERNS),
                "capabilities": list(JS_TS_CAPABILITIES)
            }
        )
    
    async def create_context(self, **kwargs):
        """Create JavaScript-specific pattern context."""
        return create_js_ts_pattern_context(language_id=LANGUAGE, **kwargs)

# Initialize pattern learner
javascript_pattern_learner = JavaScriptPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_javascript_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a JavaScript pattern with full system integration."""
    # Use shared JS/TS pattern processing with JavaScript-specific context
    return await process_js_ts_pattern(pattern, source_code, context)

# Update initialization
async def initialize_javascript_patterns():
    """Initialize JavaScript patterns during app startup."""
    global javascript_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register JavaScript patterns
    await pattern_processor.register_language_patterns(
        "javascript",
        JAVASCRIPT_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": JS_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    javascript_pattern_learner = JavaScriptPatternLearner()
    await javascript_pattern_learner.initialize()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "javascript",
        javascript_pattern_learner
    )
    
    # Initialize React analyzer and patterns
    from .react import initialize_react_patterns
    await initialize_react_patterns()
    
    await global_health_monitor.update_component_status(
        "javascript_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(JAVASCRIPT_PATTERNS),
            "capabilities": list(JS_CAPABILITIES)
        }
    )

async def extract_javascript_features(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from JavaScript pattern matches."""
    # Use shared JS/TS feature extraction
    return await extract_js_ts_features(pattern, matches, context)

async def validate_javascript_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a JavaScript pattern with system integration."""
    # Use shared JS/TS pattern validation
    return await validate_js_ts_pattern(pattern, context)

async def get_react_analyzer():
    """Get or create a React analyzer instance."""
    return react_analyzer

# Export public interfaces
__all__ = [
    'JAVASCRIPT_PATTERNS',
    'JAVASCRIPT_PATTERN_RELATIONSHIPS',
    'JAVASCRIPT_PATTERN_METRICS',
    'get_javascript_pattern_relationships',
    'update_javascript_pattern_metrics',
    'get_javascript_pattern_match_result',
    'get_react_analyzer'
] 