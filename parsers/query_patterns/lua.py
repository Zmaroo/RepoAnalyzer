"""Query patterns for Lua files.

This module provides Lua-specific patterns with enhanced type system and relationships.
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

# Lua capabilities (extends common capabilities)
LUA_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.SCRIPTING,
    AICapability.METATABLES,
    AICapability.MODULES
}

# Language identifier
LANGUAGE = "lua"

@dataclass
class LuaPatternContext(PatternContext):
    """Lua-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    table_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    has_metatables: bool = False
    has_coroutines: bool = False
    has_modules: bool = False
    has_oop: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{self.has_metatables}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "table": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics(),
    "metatable": PatternPerformanceMetrics()
}

LUA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                pattern="""
                [
                    (function_declaration
                        name: (identifier) @syntax.func.name
                        parameters: (parameters) @syntax.func.params
                        body: (block) @syntax.func.body) @syntax.func.def,
                    (local_function
                        name: (identifier) @syntax.local.name
                        parameters: (parameters) @syntax.local.params
                        body: (block) @syntax.local.body) @syntax.local.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.local.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_local": "syntax.local.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["table"]
                    }
                },
                name="function",
                description="Matches function declarations",
                examples=["function foo(x) end", "local function bar() end"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "table": ResilientPattern(
                pattern="""
                [
                    (table_constructor
                        (field
                            name: (identifier) @syntax.table.field.name
                            value: (_) @syntax.table.field.value)*) @syntax.table.def,
                    (assignment_statement
                        variables: (variable_list
                            (identifier) @syntax.table.name)
                        values: (expression_list
                            (table_constructor) @syntax.table.value)) @syntax.table.assign
                ]
                """,
                extract=lambda node: {
                    "type": "table",
                    "name": node["captures"].get("syntax.table.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.table.def", {}).get("start_point", [0])[0],
                    "field_count": len(node["captures"].get("syntax.table.field.name", [])),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["field"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="table",
                description="Matches table declarations",
                examples=["t = {x = 1, y = 2}", "local t = {}"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["table"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.METATABLES: {
            "metatable": AdaptivePattern(
                pattern="""
                [
                    (function_call
                        name: (identifier) @meta.set.name
                        arguments: (arguments
                            (table_constructor) @meta.set.table) @meta.set.args
                        (#eq? @meta.set.name "setmetatable")) @meta.set,
                        
                    (function_call
                        name: (identifier) @meta.get.name
                        arguments: (arguments) @meta.get.args
                        (#eq? @meta.get.name "getmetatable")) @meta.get,
                        
                    (index_expression
                        table: (identifier) @meta.index.table
                        index: (string) @meta.index.metamethod
                        (#match? @meta.index.metamethod "^__[a-z]+$")) @meta.index
                ]
                """,
                extract=lambda node: {
                    "type": "metatable",
                    "line_number": node["captures"].get("meta.set", {}).get("start_point", [0])[0],
                    "is_setting_metatable": "meta.set" in node["captures"],
                    "is_getting_metatable": "meta.get" in node["captures"],
                    "uses_metamethod": "meta.index" in node["captures"],
                    "metamethod": node["captures"].get("meta.index.metamethod", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["table"],
                        PatternRelationType.REFERENCES: ["function"]
                    }
                },
                name="metatable",
                description="Matches metatable operations",
                examples=["setmetatable(t, mt)", "getmetatable(t)", "mt.__index = function() end"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.METATABLES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["metatable"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^__[a-z]+$'
                    }
                }
            )
        },
        PatternPurpose.MODULES: {
            "module": AdaptivePattern(
                pattern="""
                [
                    (assignment_statement
                        variables: (variable_list
                            (identifier) @module.name)
                        values: (expression_list
                            (table_constructor) @module.table)) @module.def,
                        
                    (function_call
                        name: (identifier) @module.require.name
                        arguments: (arguments
                            (string) @module.require.path) @module.require.args
                        (#eq? @module.require.name "require")) @module.require
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "name": node["captures"].get("module.name", {}).get("text", ""),
                    "line_number": node["captures"].get("module.def", {}).get("start_point", [0])[0],
                    "is_module_definition": "module.def" in node["captures"],
                    "is_module_import": "module.require" in node["captures"],
                    "module_path": node["captures"].get("module.require.path", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["function", "table"],
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="module",
                description="Matches module patterns",
                examples=["local M = {}", "require('module')"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.MODULES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["module"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

class LuaPatternLearner(CrossProjectPatternLearner):
    """Enhanced Lua pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Lua-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("lua", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Lua patterns
        await self._pattern_processor.register_language_patterns(
            "lua", 
            LUA_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "lua_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(LUA_PATTERNS),
                "capabilities": list(LUA_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="lua",
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
            
            # Finally add Lua-specific patterns
            async with AsyncErrorBoundary("lua_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "lua",
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
                lua_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(lua_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "lua_pattern_learner",
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
                "lua_pattern_learner",
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
                "lua_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "lua_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_lua_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Lua pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Lua-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("lua", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "lua", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_lua_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"lua_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "lua",
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
        await update_lua_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "lua_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_lua_pattern_context(
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
            language_id="lua",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "lua"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(LUA_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_lua_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_lua_pattern_match_result(
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
        metadata={"language": "lua"}
    )

# Initialize pattern learner
pattern_learner = LuaPatternLearner()

async def initialize_lua_patterns():
    """Initialize Lua patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Lua patterns
    await pattern_processor.register_language_patterns(
        "lua",
        LUA_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": LUA_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await LuaPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "lua",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "lua_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(LUA_PATTERNS),
            "capabilities": list(LUA_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["table"]
    },
    "table": {
        PatternRelationType.CONTAINS: ["field"],
        PatternRelationType.DEPENDS_ON: ["function"]
    },
    "module": {
        PatternRelationType.CONTAINS: ["function", "table"],
        PatternRelationType.DEPENDS_ON: ["module"]
    },
    "metatable": {
        PatternRelationType.DEPENDS_ON: ["table"],
        PatternRelationType.REFERENCES: ["function"]
    }
}

# Export public interfaces
__all__ = [
    'LUA_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_lua_pattern_match_result',
    'update_lua_pattern_metrics',
    'LuaPatternContext',
    'pattern_learner'
] 