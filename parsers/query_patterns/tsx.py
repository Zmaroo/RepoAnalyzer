"""TSX-specific patterns with enhanced type system and relationships.

This module provides TSX-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

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
from .common import COMMON_PATTERNS
from .enhanced_patterns import AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
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
from .typescript import (
    TS_PATTERNS,
    TS_CAPABILITIES,
    TypeScriptPatternLearner,
    TypeScriptPatternContext,
    process_typescript_pattern,
    extract_typescript_features,
    validate_typescript_pattern
)
from .js_ts_shared import (
    JS_TS_SHARED_PATTERNS,
    process_js_ts_pattern
)
import time

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
TSX_PATTERNS = {
    **TS_PATTERNS,  # Inherit TypeScript patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "jsx_element": ResilientPattern(
                name="jsx_element",
                pattern="""
                [
                    (jsx_element
                        open_tag: (jsx_opening_element
                            name: (_) @syntax.jsx.element.name
                            attributes: (jsx_attributes
                                (jsx_attribute
                                    name: (jsx_attribute_name) @syntax.jsx.attribute.name
                                    value: (_)? @syntax.jsx.attribute.value)*)?
                            ) @syntax.jsx.open_tag
                        children: (_)* @syntax.jsx.children
                        close_tag: (jsx_closing_element)? @syntax.jsx.close_tag) @syntax.jsx.element,
                    
                    (jsx_self_closing_element
                        name: (_) @syntax.jsx.self_closing.name
                        attributes: (jsx_attributes
                            (jsx_attribute
                                name: (jsx_attribute_name) @syntax.jsx.self_closing.attribute.name
                                value: (_)? @syntax.jsx.self_closing.attribute.value)*)?
                        ) @syntax.jsx.self_closing
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="tsx",
                confidence=0.95,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "jsx_component": ResilientPattern(
                name="jsx_component",
                pattern="""
                [
                    (function_declaration
                        modifiers: [(export) (default)]* @syntax.component.modifier
                        name: (identifier) @syntax.component.name
                        parameters: (formal_parameters
                            (required_parameter
                                name: (identifier) @syntax.component.props.name
                                type: (type_annotation)? @syntax.component.props.type)) @syntax.component.props
                        return_type: (type_annotation)? @syntax.component.return_type
                        body: (statement_block
                            (return_statement
                                (jsx_element) @syntax.component.jsx))) @syntax.component.function,
                    
                    (arrow_function
                        parameters: (formal_parameters
                            (required_parameter
                                name: (identifier) @syntax.component.arrow.props.name
                                type: (type_annotation)? @syntax.component.arrow.props.type)) @syntax.component.arrow.props
                        return_type: (type_annotation)? @syntax.component.arrow.return_type
                        body: (jsx_element) @syntax.component.arrow.jsx) @syntax.component.arrow
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="tsx",
                confidence=0.95,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "react_hook": ResilientPattern(
                name="react_hook",
                pattern="""
                [
                    (call_expression
                        function: (identifier) @syntax.hook.name
                        arguments: (arguments) @syntax.hook.args) @syntax.hook.call
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="tsx",
                confidence=0.95,
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
    }
}

class TSXPatternLearner(TypeScriptPatternLearner):
    """TSX-specific pattern learner extending TypeScript learner."""
    
    async def initialize(self):
        """Initialize with TSX-specific components."""
        await super().initialize()
        
        # Register TSX-specific patterns
        await self._pattern_processor.register_language_patterns(
            "tsx",
            TSX_PATTERNS,
            self
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for TSX."""
        # Try tree-sitter first
        tree_sitter_parser = await get_tree_sitter_parser("tsx")
        if tree_sitter_parser:
            return tree_sitter_parser
            
        # Fallback to base parser
        return await BaseParser.create(
            language_id="tsx",
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with AI assistance and React component information."""
        patterns = await super().learn_from_project(project_path)
        
        # Add TSX-specific pattern learning
        async with AsyncErrorBoundary("tsx_pattern_learning"):
            # Extract React component information
            component_patterns = await self._extract_component_patterns(project_path)
            patterns.extend(component_patterns)
            
            return patterns

    async def _extract_component_patterns(self, project_path: str) -> List[Dict[str, Any]]:
        """Extract TSX-specific React component patterns."""
        component_patterns = []
        
        # Get React analyzer
        react_analyzer = await get_react_analyzer()
        
        # Extract component information
        component_info = await react_analyzer.analyze_project(project_path)
        
        # Convert component information to patterns
        for component in component_info:
            pattern = {
                "name": component.name,
                "category": PatternCategory.COMPONENTS,
                "content": component.content,
                "confidence": 0.95,
                "metadata": {
                    "component_type": component.type,
                    "has_hooks": component.uses_hooks,
                    "prop_types": component.prop_types
                }
            }
            component_patterns.append(pattern)
        
        return component_patterns

# Initialize pattern learner
tsx_pattern_learner = TSXPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_tsx_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
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
    
    await global_health_monitor.update_component_status(
        "tsx_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(TSX_PATTERNS),
            "capabilities": list(TSX_CAPABILITIES)
        }
    )

async def extract_tsx_features(
    pattern: Union[AdaptivePattern, ResilientPattern],
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
    pattern: Union[AdaptivePattern, ResilientPattern],
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

# Export public interfaces
__all__ = [
    'TSX_PATTERNS',
    'TSX_PATTERN_RELATIONSHIPS',
    'TSX_PATTERN_METRICS',
    'get_tsx_pattern_relationships',
    'update_tsx_pattern_metrics',
    'get_tsx_pattern_match_result'
]