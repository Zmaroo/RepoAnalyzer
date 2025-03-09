"""JavaScript-specific patterns with enhanced type system and relationships.

This module provides JavaScript-specific patterns that integrate with the enhanced
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
from .js_ts_shared import (
    JS_TS_SHARED_PATTERNS,
    JS_TS_CAPABILITIES,
    JSTSPatternLearner,
    process_js_ts_pattern,
    extract_js_ts_features,
    validate_js_ts_pattern
)
import time

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
            "node_module": AdaptivePattern(
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
    }
}

class JavaScriptPatternLearner(JSTSPatternLearner):
    """JavaScript-specific pattern learner extending JS/TS learner."""
    
    async def initialize(self):
        """Initialize with JavaScript-specific components."""
        await super().initialize()
        
        # Register JavaScript-specific patterns
        await self._pattern_processor.register_language_patterns(
            "javascript",
            JS_PATTERNS,
            self
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for JavaScript."""
        # Try tree-sitter first
        tree_sitter_parser = await get_tree_sitter_parser("javascript")
        if tree_sitter_parser:
            return tree_sitter_parser
            
        # Fallback to base parser
        return await BaseParser.create(
            language_id="javascript",
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )

# Initialize pattern learner
js_pattern_learner = JavaScriptPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_javascript_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a JavaScript pattern with full system integration."""
    # Use shared JS/TS pattern processing with JavaScript-specific context
    return await process_js_ts_pattern(pattern, source_code, context)

# Update initialization
async def initialize_javascript_patterns():
    """Initialize JavaScript patterns during app startup."""
    global js_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register JavaScript patterns
    await pattern_processor.register_language_patterns(
        "javascript",
        JS_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": JS_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    js_pattern_learner = await JavaScriptPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "javascript",
        js_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "javascript_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(JS_PATTERNS),
            "capabilities": list(JS_CAPABILITIES)
        }
    )

async def extract_javascript_features(
    pattern: Union[AdaptivePattern, ResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from JavaScript pattern matches."""
    # Use shared JS/TS feature extraction
    return await extract_js_ts_features(pattern, matches, context)

async def validate_javascript_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a JavaScript pattern with system integration."""
    # Use shared JS/TS pattern validation
    return await validate_js_ts_pattern(pattern, context)

# Export public interfaces
__all__ = [
    'JS_PATTERNS',
    'JS_PATTERN_RELATIONSHIPS',
    'JS_PATTERN_METRICS',
    'create_pattern_context',
    'get_js_pattern_relationships',
    'update_js_pattern_metrics',
    'get_js_pattern_match_result'
]

# Module identification
LANGUAGE = "javascript" 