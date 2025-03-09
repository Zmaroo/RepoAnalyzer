"""Query patterns for Ruby files.

This module provides Ruby-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Union, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from .common import COMMON_PATTERNS, COMMON_CAPABILITIES, process_common_pattern
from .enhanced_patterns import AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
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
import time

# Language identifier
LANGUAGE = "ruby"

# Ruby capabilities (extends common capabilities)
RUBY_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.OBJECT_ORIENTED,
    AICapability.METAPROGRAMMING,
    AICapability.BLOCKS
}

@dataclass
class RubyPatternContext(PatternContext):
    """Ruby-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    method_names: Set[str] = field(default_factory=set)
    gem_names: Set[str] = field(default_factory=set)
    has_rails: bool = False
    has_rspec: bool = False
    has_modules: bool = False
    has_mixins: bool = False
    has_blocks: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_rails}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics(),
    "method": PatternPerformanceMetrics(),
    "gem": PatternPerformanceMetrics(),
    "block": PatternPerformanceMetrics()
}

RUBY_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class
                        name: (constant) @syntax.class.name
                        superclass: (constant)? @syntax.class.super
                        body: (_)? @syntax.class.body) @syntax.class.def,
                    (singleton_class
                        value: (_) @syntax.singleton.value
                        body: (_)? @syntax.singleton.body) @syntax.singleton.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0],
                    "superclass": node["captures"].get("syntax.class.super", {}).get("text", ""),
                    "is_singleton": "syntax.singleton.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "constant", "include"],
                        PatternRelationType.DEPENDS_ON: ["class", "module"]
                    }
                },
                name="class",
                description="Matches Ruby class declarations",
                examples=["class MyClass < BaseClass", "class << self"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["class"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "module": ResilientPattern(
                pattern="""
                [
                    (module
                        name: (constant) @syntax.module.name
                        body: (_)? @syntax.module.body) @syntax.module.def,
                    (include
                        name: (constant) @syntax.include.name) @syntax.include.def,
                    (extend
                        name: (constant) @syntax.extend.name) @syntax.extend.def
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "name": (
                        node["captures"].get("syntax.module.name", {}).get("text", "") or
                        node["captures"].get("syntax.include.name", {}).get("text", "") or
                        node["captures"].get("syntax.extend.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.module.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.include.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.extend.def", {}).get("start_point", [0])[0]
                    ),
                    "is_include": "syntax.include.def" in node["captures"],
                    "is_extend": "syntax.extend.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "constant"],
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="module",
                description="Matches Ruby module declarations and inclusions",
                examples=["module MyModule", "include Enumerable", "extend ActiveSupport::Concern"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["module"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_:]*$'
                    }
                }
            ),
            "method": ResilientPattern(
                pattern="""
                [
                    (method
                        name: (identifier) @syntax.method.name
                        parameters: (method_parameters)? @syntax.method.params
                        body: (_)? @syntax.method.body) @syntax.method.def,
                    (singleton_method
                        object: (_) @syntax.singleton.method.obj
                        name: (identifier) @syntax.singleton.method.name
                        parameters: (method_parameters)? @syntax.singleton.method.params
                        body: (_)? @syntax.singleton.method.body) @syntax.singleton.method.def
                ]
                """,
                extract=lambda node: {
                    "type": "method",
                    "name": (
                        node["captures"].get("syntax.method.name", {}).get("text", "") or
                        node["captures"].get("syntax.singleton.method.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.method.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.singleton.method.def", {}).get("start_point", [0])[0]
                    ),
                    "is_singleton": "syntax.singleton.method.def" in node["captures"],
                    "has_params": (
                        "syntax.method.params" in node["captures"] or
                        "syntax.singleton.method.params" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["block", "call"],
                        PatternRelationType.DEPENDS_ON: ["class", "module"]
                    }
                },
                name="method",
                description="Matches Ruby method declarations",
                examples=["def process(data)", "def self.create", "def my_method; end"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["method"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z_][a-zA-Z0-9_]*[?!=]?$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.DEPENDENCIES: {
            "gem": AdaptivePattern(
                pattern="""
                [
                    (call
                        method: (identifier) @gem.name
                        arguments: (argument_list
                            (string) @gem.version)? @gem.args) @gem.def
                        (#match? @gem.name "^gem$"),
                    (call
                        method: (identifier) @gem.require.name
                        arguments: (argument_list
                            (string) @gem.require.path) @gem.require.args) @gem.require.def
                        (#match? @gem.require.name "^require$")
                ]
                """,
                extract=lambda node: {
                    "type": "gem",
                    "line_number": (
                        node["captures"].get("gem.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("gem.require.def", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("gem.args", {}).get("text", "") or
                        node["captures"].get("gem.require.path", {}).get("text", "")
                    ),
                    "version": node["captures"].get("gem.version", {}).get("text", ""),
                    "is_require": "gem.require.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.PROVIDES: ["class", "module", "method"],
                        PatternRelationType.DEPENDS_ON: ["gem"]
                    }
                },
                name="gem",
                description="Matches Ruby gem declarations and requires",
                examples=["gem 'rails', '~> 6.1.0'", "require 'json'"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.DEPENDENCIES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["gem"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-z0-9_-]*$'
                    }
                }
            )
        },
        PatternPurpose.BLOCKS: {
            "block": AdaptivePattern(
                pattern="""
                [
                    (block
                        call: (call) @block.call
                        parameters: (block_parameters)? @block.params
                        body: (_)? @block.body) @block.def,
                    (do_block
                        call: (call) @block.do.call
                        parameters: (block_parameters)? @block.do.params
                        body: (_)? @block.do.body) @block.do.def
                ]
                """,
                extract=lambda node: {
                    "type": "block",
                    "line_number": (
                        node["captures"].get("block.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("block.do.def", {}).get("start_point", [0])[0]
                    ),
                    "has_params": (
                        "block.params" in node["captures"] or
                        "block.do.params" in node["captures"]
                    ),
                    "is_do": "block.do.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["method", "class"],
                        PatternRelationType.DEPENDS_ON: ["method"]
                    }
                },
                name="block",
                description="Matches Ruby block expressions",
                examples=["[1,2,3].each { |n| puts n }", "5.times do |i| end"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.BLOCKS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["block"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    }
}

class RubyPatternLearner(CrossProjectPatternLearner):
    """Enhanced Ruby pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        super().__init__()
        self._feature_extractor = None
        self._pattern_processor = pattern_processor
        self._ai_processor = None
        self._block_extractor = None
        self._unified_parser = None
        self._metrics = {
            "total_patterns": 0,
            "learned_patterns": 0,
            "failed_patterns": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "learning_times": []
        }
        register_shutdown_handler(self.cleanup)

    async def initialize(self):
        """Initialize with Ruby-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("ruby", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Ruby patterns
        await self._pattern_processor.register_language_patterns(
            "ruby", 
            RUBY_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "ruby_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(RUBY_PATTERNS),
                "capabilities": list(RUBY_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="ruby",
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
            
            # Finally add Ruby-specific patterns
            async with AsyncErrorBoundary("ruby_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "ruby",
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
                ruby_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(ruby_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "ruby_pattern_learner",
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
                "ruby_pattern_learner",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": str(e)}
            )
            
            return []

    async def cleanup(self):
        """Clean up pattern learner resources."""
        try:
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
                "ruby_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "ruby_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_ruby_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Ruby pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Ruby-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("ruby", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "ruby", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_ruby_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"ruby_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "ruby",
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
        
        # Cache the result
        await get_current_request_cache().set(cache_key, matches)
        
        # Update pattern metrics
        await update_ruby_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "ruby_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_ruby_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create pattern context with full system integration."""
    # Get unified parser
    unified_parser = await get_unified_parser()
    
    # Parse the code structure if needed
    if not code_structure:
        parse_result = await unified_parser.parse(
            file_path,
            language_id="ruby",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "ruby"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(RUBY_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_ruby_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in PATTERN_METRICS:
        pattern_metrics = PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_ruby_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=PATTERN_RELATIONSHIPS.get(pattern_name, []),
        performance=PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "ruby"}
    )

# Initialize pattern learner
pattern_learner = RubyPatternLearner()

async def initialize_ruby_patterns():
    """Initialize Ruby patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Ruby patterns
    await pattern_processor.register_language_patterns(
        "ruby",
        RUBY_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": RUBY_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await RubyPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "ruby",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "ruby_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(RUBY_PATTERNS),
            "capabilities": list(RUBY_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "constant", "include"],
        PatternRelationType.DEPENDS_ON: ["class", "module"]
    },
    "module": {
        PatternRelationType.CONTAINS: ["method", "constant"],
        PatternRelationType.DEPENDS_ON: ["module"]
    },
    "method": {
        PatternRelationType.CONTAINS: ["block", "call"],
        PatternRelationType.DEPENDS_ON: ["class", "module"]
    },
    "gem": {
        PatternRelationType.PROVIDES: ["class", "module", "method"],
        PatternRelationType.DEPENDS_ON: ["gem"]
    },
    "block": {
        PatternRelationType.CONTAINED_BY: ["method", "class"],
        PatternRelationType.DEPENDS_ON: ["method"]
    }
}

# Export public interfaces
__all__ = [
    'RUBY_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_ruby_pattern_match_result',
    'update_ruby_pattern_metrics',
    'RubyPatternContext',
    'pattern_learner'
] 