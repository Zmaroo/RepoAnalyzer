"""TSX-specific patterns with enhanced type system and relationships.

This module provides TSX-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

from typing import Dict, Any, List, Optional, Union, Set
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType
)
from parsers.models import PATTERN_CATEGORIES
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
from utils.request_cache import cached_in_request
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
import asyncio
from parsers.pattern_processor import pattern_processor
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import get_feature_extractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
from .typescript import (
    TS_PATTERNS,
    TS_CAPABILITIES,
    TypeScriptPatternLearner,
    TypeScriptPatternContext,
    process_typescript_pattern,
    extract_typescript_features,
    validate_typescript_pattern,
    TYPESCRIPT_PATTERNS,
    TYPESCRIPT_SPECIFIC_PATTERNS
)
from .js_ts_shared import (
    JS_TS_SHARED_PATTERNS,
    process_js_ts_pattern,
    JSTSPatternLearner,
    JS_TS_CAPABILITIES,
    create_js_ts_pattern_context
)
from .react import ReactAnalyzer, react_analyzer
import time
import os

# Module identification - must be before any usage
LANGUAGE = "tsx"

# TSX capabilities (extends TypeScript capabilities)
TSX_CAPABILITIES = TS_CAPABILITIES | {
    AICapability.JSX_SUPPORT,
    AICapability.REACT_INTEGRATION
}

@dataclass
class TSXPatternContext(TypeScriptPatternContext):
    """TSX-specific pattern context."""
    jsx_component_names: Set[str] = field(default_factory=set)
    jsx_prop_types: Dict[str, str] = field(default_factory=dict)
    has_jsx_fragments: bool = False
    has_react_hooks: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.jsx_component_names)}:{self.has_react_hooks}"

# TSX patterns extend TypeScript patterns
TSX_SPECIFIC_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "jsx_element": TreeSitterPattern(
                name="jsx_element",
                pattern="""
                [
                    (jsx_element
                        opening_element: (jsx_opening_element
                            name: (_) @syntax.jsx.name) @syntax.jsx.opening
                        children: (jsx_children)? @syntax.jsx.children
                        closing_element: (jsx_closing_element)? @syntax.jsx.closing) @syntax.jsx.element
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="tsx",
                confidence=0.95,
                extract=lambda m: {
                    "type": "jsx_element",
                    "element_name": m["captures"]["syntax.jsx.name"]["text"] if "syntax.jsx.name" in m.get("captures", {}) else "",
                    "has_children": "syntax.jsx.children" in m.get("captures", {}),
                    "is_component": m["captures"]["syntax.jsx.name"]["text"][0].isupper() if "syntax.jsx.name" in m.get("captures", {}) else False,
                    "is_self_closing": "syntax.jsx.closing" not in m.get("captures", {})
                },
                regex_pattern=r'<([A-Za-z][A-Za-z0-9]*)\s*(?:[^>]*?)(/>|>)',
                block_type="jsx_element",
                contains_blocks=["jsx_element", "jsx_expression"],
                is_nestable=True,
                extraction_priority=15,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches JSX elements in TSX files",
                    "examples": [
                        "<div>Content</div>",
                        "<Component prop={value} />"
                    ],
                    "version": "1.0",
                    "tags": ["jsx", "tsx", "react", "element", "component"]
                },
                test_cases=[
                    {
                        "input": "<div>Content</div>",
                        "expected": {
                            "type": "jsx_element",
                            "element_name": "div",
                            "is_component": False,
                            "has_children": True,
                            "is_self_closing": False
                        }
                    },
                    {
                        "input": "<Button onClick={handleClick} />",
                        "expected": {
                            "type": "jsx_element",
                            "element_name": "Button",
                            "is_component": True,
                            "is_self_closing": True
                        }
                    }
                ]
            ),
            
            "jsx_expression": TreeSitterPattern(
                name="jsx_expression",
                pattern="""
                [
                    (jsx_expression
                        expression: (_) @syntax.jsx_expr.content) @syntax.jsx_expr.container
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="tsx",
                confidence=0.95,
                extract=lambda m: {
                    "type": "jsx_expression",
                    "content": m["captures"]["syntax.jsx_expr.content"]["text"] if "syntax.jsx_expr.content" in m.get("captures", {}) else "",
                    "is_function_call": "(" in m["captures"]["syntax.jsx_expr.content"]["text"] if "syntax.jsx_expr.content" in m.get("captures", {}) else False,
                    "is_conditional": "?" in m["captures"]["syntax.jsx_expr.content"]["text"] if "syntax.jsx_expr.content" in m.get("captures", {}) else False
                },
                regex_pattern=r'\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
                block_type="jsx_expression",
                is_nestable=True,
                extraction_priority=10,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches JSX expressions in TSX files",
                    "examples": [
                        "{name}",
                        "{isActive ? 'active' : 'inactive'}"
                    ],
                    "version": "1.0",
                    "tags": ["jsx", "tsx", "react", "expression"]
                },
                test_cases=[
                    {
                        "input": "{user.name}",
                        "expected": {
                            "type": "jsx_expression",
                            "is_function_call": False,
                            "is_conditional": False
                        }
                    },
                    {
                        "input": "{isLoggedIn ? <UserProfile /> : <LoginButton />}",
                        "expected": {
                            "type": "jsx_expression",
                            "is_conditional": True
                        }
                    }
                ]
            ),
            
            "jsx_attribute": TreeSitterPattern(
                name="jsx_attribute",
                pattern="""
                [
                    (jsx_attribute
                        name: (property_identifier) @syntax.jsx_attr.name
                        value: (_)? @syntax.jsx_attr.value) @syntax.jsx_attr.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="tsx",
                confidence=0.95,
                extract=lambda m: {
                    "type": "jsx_attribute",
                    "name": m["captures"]["syntax.jsx_attr.name"]["text"] if "syntax.jsx_attr.name" in m.get("captures", {}) else "",
                    "has_value": "syntax.jsx_attr.value" in m.get("captures", {}),
                    "is_event_handler": m["captures"]["syntax.jsx_attr.name"]["text"].startswith("on") if "syntax.jsx_attr.name" in m.get("captures", {}) else False
                },
                regex_pattern=r'([a-zA-Z][a-zA-Z0-9]*?)(?:=(?:"[^"]*"|\'[^\']*\'|\{[^}]*\}))?',
                block_type="jsx_attribute",
                is_nestable=False,
                extraction_priority=5,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches JSX attributes in TSX files",
                    "examples": [
                        "className=\"container\"",
                        "onClick={handleClick}"
                    ],
                    "version": "1.0",
                    "tags": ["jsx", "tsx", "react", "attribute", "prop"]
                },
                test_cases=[
                    {
                        "input": "className=\"container\"",
                        "expected": {
                            "type": "jsx_attribute",
                            "name": "className",
                            "has_value": True,
                            "is_event_handler": False
                        }
                    },
                    {
                        "input": "onClick={handleClick}",
                        "expected": {
                            "type": "jsx_attribute",
                            "name": "onClick",
                            "has_value": True,
                            "is_event_handler": True
                        }
                    }
                ]
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "react_hook_call": TreeSitterPattern(
                name="react_hook_call",
                pattern=r'(?:const|let)\s+(?:\[[^=[\]]+\]|[a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*use[A-Z][a-zA-Z]*\(',
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="tsx",
                confidence=0.9,
                extract=lambda m: {
                    "type": "react_hook",
                    "hook_call": m.group(0),
                    "hook_name": m.group(0).split("use")[1].split("(")[0],
                    "is_state_hook": "useState" in m.group(0),
                    "is_effect_hook": "useEffect" in m.group(0),
                    "line_number": m.string.count('\n', 0, m.start()) + 1
                },
                regex_pattern=r'(?:const|let)\s+(?:\[[^=[\]]+\]|[a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*use[A-Z][a-zA-Z]*\(',
                block_type="hook_call",
                is_nestable=False,
                extraction_priority=12,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": {
                        "is_valid": True,
                        "validation_time": 0.0
                    },
                    "description": "Matches React hook calls in TSX files",
                    "examples": [
                        "const [count, setCount] = useState(0)",
                        "const data = useQuery('key')"
                    ],
                    "version": "1.0",
                    "tags": ["react", "hook", "tsx", "functional"]
                },
                test_cases=[
                    {
                        "input": "const [count, setCount] = useState(0)",
                        "expected": {
                            "type": "react_hook",
                            "hook_name": "State",
                            "is_state_hook": True
                        }
                    },
                    {
                        "input": "const user = useContext(UserContext)",
                        "expected": {
                            "type": "react_hook",
                            "hook_name": "Context",
                            "is_state_hook": False
                        }
                    }
                ]
            )
        }
    }
}

# Combine TypeScript patterns with TSX-specific patterns
TSX_PATTERNS = {
    **TYPESCRIPT_PATTERNS,
    **TSX_SPECIFIC_PATTERNS
}

class TSXPatternLearner(JSTSPatternLearner):
    """Pattern learner specialized for TSX code."""
    
    def __init__(self):
        super().__init__(language_id="tsx")
        self.insights_path = os.path.join(DATA_DIR, "tsx_pattern_insights.json")
        
    async def initialize(self):
        """Initialize with TSX-specific components."""
        await super().initialize()
        
        # Register TSX-specific patterns
        from parsers.pattern_processor import register_pattern
        for category, purpose_dict in TSX_SPECIFIC_PATTERNS.items():
            for purpose, patterns in purpose_dict.items():
                for name, pattern in patterns.items():
                    pattern_key = f"{category}:{purpose}:{name}"
                    await register_pattern(pattern_key, pattern)
        
        # Update health monitoring
        await global_health_monitor.update_component_status(
            "tsx_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(TSX_PATTERNS),
                "tsx_specific_patterns": len(TSX_SPECIFIC_PATTERNS),
                "capabilities": list(JS_TS_CAPABILITIES)
            }
        )
    
    async def create_context(self, **kwargs):
        """Create TSX-specific pattern context."""
        return create_js_ts_pattern_context(language_id=LANGUAGE, **kwargs)

# Initialize pattern learner
tsx_pattern_learner = TSXPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_tsx_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[TSXPatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a TSX pattern with full system integration."""
    # Use TypeScript pattern processing with TSX-specific context
    return await process_typescript_pattern(pattern, source_code, context)

# Update initialization
async def initialize_tsx_patterns():
    """Initialize TSX patterns during app startup."""
    global tsx_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register TSX patterns
    await pattern_processor.register_language_patterns(
        "tsx",
        TSX_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": TSX_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    tsx_pattern_learner = await TSXPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "tsx",
        tsx_pattern_learner
    )
    
    # Initialize React analyzer and patterns
    from .react import initialize_react_patterns
    await initialize_react_patterns()
    
    await global_health_monitor.update_component_status(
        "tsx_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(TSX_PATTERNS),
            "capabilities": list(TSX_CAPABILITIES)
        }
    )

async def extract_tsx_features(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    matches: List[Dict[str, Any]],
    context: TSXPatternContext
) -> ExtractedFeatures:
    """Extract features from TSX pattern matches."""
    # Use TypeScript feature extraction with TSX-specific context
    features = await extract_typescript_features(pattern, matches, context)
    
    # Add TSX-specific features
    if pattern.category == PatternCategory.COMPONENTS:
        component_features = await extract_component_features(matches, context)
        features.update(component_features)
    
    return features

async def validate_tsx_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    context: Optional[TSXPatternContext] = None
) -> PatternValidationResult:
    """Validate a TSX pattern with system integration."""
    # Use TypeScript pattern validation with TSX-specific context
    return await validate_typescript_pattern(pattern, context)

async def extract_component_features(
    matches: List[Dict[str, Any]],
    context: TSXPatternContext
) -> ExtractedFeatures:
    """Extract TSX-specific React component features."""
    features = ExtractedFeatures()
    
    for match in matches:
        if "component" in match:
            features.add_component_info(
                name=match["name"],
                type=match.get("component_type"),
                has_hooks=match.get("has_hooks", False),
                prop_types=match.get("prop_types", {})
            )
            
            # Update context
            context.jsx_component_names.add(match["name"])
            if match.get("has_hooks"):
                context.has_react_hooks = True
            context.jsx_prop_types.update(match.get("prop_types", {}))
    
    return features

async def get_react_analyzer():
    """Get or create a React analyzer instance."""
    return react_analyzer

# Export public interfaces
__all__ = [
    'TSX_PATTERNS',
    'TSX_PATTERN_RELATIONSHIPS',
    'TSX_PATTERN_METRICS',
    'get_tsx_pattern_relationships',
    'update_tsx_pattern_metrics',
    'get_tsx_pattern_match_result'
]