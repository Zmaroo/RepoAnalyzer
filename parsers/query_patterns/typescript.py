"""TypeScript-specific patterns with enhanced type system and relationships.

This module provides TypeScript-specific patterns that integrate with the enhanced
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

# TypeScript capabilities (extends JS/TS capabilities)
TS_CAPABILITIES = JS_TS_CAPABILITIES | {
    AICapability.TYPE_CHECKING,
    AICapability.INTERFACE_GENERATION,
    AICapability.TYPE_INFERENCE
}

@dataclass
class TypeScriptPatternContext(PatternContext):
    """TypeScript-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    interface_names: Set[str] = field(default_factory=set)
    type_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    has_generics: bool = False
    has_decorators: bool = False
    has_async: bool = False
    has_jsx: bool = False
    has_modules: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_generics}"

# TypeScript patterns extend shared patterns
TS_PATTERNS = {
    **JS_TS_SHARED_PATTERNS,  # Inherit shared patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "type_definition": ResilientPattern(
                name="type_definition",
                pattern="""
                [
                    (type_alias_declaration
                        name: (type_identifier) @syntax.type.name
                        type_parameters: (type_parameters)? @syntax.type.generics
                        value: (_) @syntax.type.value) @syntax.type.def,
                    (interface_declaration
                        name: (type_identifier) @syntax.interface.name
                        type_parameters: (type_parameters)? @syntax.interface.generics
                        extends: (interface_heritage)? @syntax.interface.extends
                        body: (object_type) @syntax.interface.body) @syntax.interface.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="typescript",
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
            
            "decorator": ResilientPattern(
                name="decorator",
                pattern="""
                [
                    (decorator
                        expression: (call_expression
                            function: (identifier) @syntax.decorator.name
                            arguments: (arguments)? @syntax.decorator.args)) @syntax.decorator.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="typescript",
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
    },

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "type_mismatch": QueryPattern(
            name="type_mismatch",
            pattern=r'(?:let|const|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*([a-zA-Z_$][a-zA-Z0-9_$<>]*)\s*=\s*([^;\n]+)',
            extract=lambda m: {
                "type": "type_mismatch",
                "variable": m.group(1),
                "declared_type": m.group(2),
                "value": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potential type mismatches", "examples": ["let x: string = 42"]}
        ),
        "implicit_any": QueryPattern(
            name="implicit_any",
            pattern=r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(([^:)]+)\)',
            extract=lambda m: {
                "type": "implicit_any",
                "function": m.group(1),
                "params": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects implicit any types", "examples": ["function process(data) { }"]}
        ),
        "unsafe_type_assertion": QueryPattern(
            name="unsafe_type_assertion",
            pattern=r'(?:as\s+any|\<any\>)',
            extract=lambda m: {
                "type": "unsafe_type_assertion",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects unsafe type assertions", "examples": ["value as any", "<any>value"]}
        ),
        "null_undefined_union": QueryPattern(
            name="null_undefined_union",
            pattern=r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*[a-zA-Z_$][a-zA-Z0-9_$]*(?:\s*\|\s*(?:null|undefined))+',
            extract=lambda m: {
                "type": "null_undefined_union",
                "variable": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.85
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects null/undefined union types", "examples": ["value: string | null | undefined"]}
        ),
        "non_null_assertion": QueryPattern(
            name="non_null_assertion",
            pattern=r'([a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)!',
            extract=lambda m: {
                "type": "non_null_assertion",
                "expression": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects non-null assertions", "examples": ["obj.value!", "getData()!"]}
        )
    }
}

class TypeScriptPatternLearner(JSTSPatternLearner):
    """TypeScript-specific pattern learner extending JS/TS learner."""
    
    async def initialize(self):
        """Initialize with TypeScript-specific components."""
        await super().initialize()
        
        # Register TypeScript-specific patterns
        await self._pattern_processor.register_language_patterns(
            "typescript",
            TS_PATTERNS,
            self
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for TypeScript."""
        # Try tree-sitter first
        tree_sitter_parser = await get_tree_sitter_parser("typescript")
        if tree_sitter_parser:
            return tree_sitter_parser
            
        # Fallback to base parser
        return await BaseParser.create(
            language_id="typescript",
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with AI assistance and type information."""
        patterns = await super().learn_from_project(project_path)
        
        # Add TypeScript-specific pattern learning
        async with AsyncErrorBoundary("typescript_pattern_learning"):
            # Extract type information
            type_patterns = await self._extract_type_patterns(project_path)
            patterns.extend(type_patterns)
            
            return patterns

    async def _extract_type_patterns(self, project_path: str) -> List[Dict[str, Any]]:
        """Extract TypeScript-specific type patterns."""
        type_patterns = []
        
        # Get type checker
        type_checker = await get_type_checker()
        
        # Extract type information
        type_info = await type_checker.analyze_project(project_path)
        
        # Convert type information to patterns
        for type_def in type_info:
            pattern = {
                "name": type_def.name,
                "category": PatternCategory.TYPES,
                "content": type_def.content,
                "confidence": 0.95,
                "metadata": {
                    "type_kind": type_def.kind,
                    "is_generic": type_def.has_generics
                }
            }
            type_patterns.append(pattern)
        
        return type_patterns

# Initialize pattern learner
ts_pattern_learner = TypeScriptPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def process_typescript_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[TypeScriptPatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a TypeScript pattern with full system integration."""
    # Use shared JS/TS pattern processing with TypeScript-specific context
    return await process_js_ts_pattern(pattern, source_code, context)

# Update initialization
async def initialize_typescript_patterns():
    """Initialize TypeScript patterns during app startup."""
    global ts_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register TypeScript patterns
    await pattern_processor.register_language_patterns(
        "typescript",
        TS_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": TS_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    ts_pattern_learner = await TypeScriptPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "typescript",
        ts_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "typescript_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(TS_PATTERNS),
            "capabilities": list(TS_CAPABILITIES)
        }
    )

async def extract_typescript_features(
    pattern: Union[AdaptivePattern, ResilientPattern],
    matches: List[Dict[str, Any]],
    context: TypeScriptPatternContext
) -> ExtractedFeatures:
    """Extract features from TypeScript pattern matches."""
    # Use shared JS/TS feature extraction with TypeScript-specific context
    features = await extract_js_ts_features(pattern, matches, context)
    
    # Add TypeScript-specific features
    if pattern.category == PatternCategory.TYPES:
        type_features = await extract_type_features(matches, context)
        features.update(type_features)
    
    return features

async def validate_typescript_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    context: Optional[TypeScriptPatternContext] = None
) -> PatternValidationResult:
    """Validate a TypeScript pattern with system integration."""
    # Use shared JS/TS pattern validation with TypeScript-specific context
    return await validate_js_ts_pattern(pattern, context)

async def extract_type_features(
    matches: List[Dict[str, Any]],
    context: TypeScriptPatternContext
) -> ExtractedFeatures:
    """Extract TypeScript-specific type features."""
    features = ExtractedFeatures()
    
    for match in matches:
        if "type" in match:
            features.add_type_info(
                name=match["name"],
                kind=match.get("type_kind"),
                is_generic=match.get("is_generic", False)
            )
    
    return features

async def get_type_checker():
    """Get or create a TypeScript type checker instance."""
    from parsers.typescript_analyzer import TypeScriptTypeChecker
    return await TypeScriptTypeChecker.create()