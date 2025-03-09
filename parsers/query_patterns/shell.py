"""Query patterns for Shell files.

This module provides Shell-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "shell"

# Shell capabilities (extends common capabilities)
SHELL_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.SCRIPTING,
    AICapability.AUTOMATION,
    AICapability.SYSTEM_INTEGRATION
}

@dataclass
class ShellPatternContext(PatternContext):
    """Shell-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    variable_names: Set[str] = field(default_factory=set)
    alias_names: Set[str] = field(default_factory=set)
    has_functions: bool = False
    has_arrays: bool = False
    has_pipes: bool = False
    has_redirects: bool = False
    has_subshells: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{self.has_functions}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "variable": PatternPerformanceMetrics(),
    "command": PatternPerformanceMetrics(),
    "pipeline": PatternPerformanceMetrics(),
    "redirect": PatternPerformanceMetrics()
}

SHELL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (word) @syntax.func.name
                        body: (compound_statement) @syntax.func.body) @syntax.func.def,
                    (function_definition
                        name: (word) @syntax.func.name
                        body: (group) @syntax.func.group) @syntax.func.group.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": node["captures"].get("syntax.func.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_grouped": "syntax.func.group.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["command", "variable", "pipeline"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="function",
                description="Matches Shell function declarations",
                examples=["function process() { echo 'done'; }", "backup() ( tar -czf backup.tar.gz . )"],
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
            "variable": ResilientPattern(
                pattern="""
                [
                    (variable_assignment
                        name: (variable_name) @syntax.var.name
                        value: (_) @syntax.var.value) @syntax.var.def,
                    (array_assignment
                        name: (variable_name) @syntax.array.name
                        elements: (array) @syntax.array.elements) @syntax.array.def
                ]
                """,
                extract=lambda node: {
                    "type": "variable",
                    "name": (
                        node["captures"].get("syntax.var.name", {}).get("text", "") or
                        node["captures"].get("syntax.array.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.var.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.array.def", {}).get("start_point", [0])[0]
                    ),
                    "is_array": "syntax.array.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["command", "pipeline"],
                        PatternRelationType.DEPENDS_ON: ["variable"]
                    }
                },
                name="variable",
                description="Matches Shell variable assignments",
                examples=["NAME='value'", "ARRAY=(one two three)"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["variable"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z_][A-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.COMMANDS: {
            "command": AdaptivePattern(
                pattern="""
                [
                    (command
                        name: (command_name) @cmd.name
                        argument: (_)* @cmd.args) @cmd.def,
                    (pipeline
                        command: (command)+ @cmd.pipe.command) @cmd.pipe.def,
                    (subshell
                        command: (_) @cmd.sub.command) @cmd.sub.def
                ]
                """,
                extract=lambda node: {
                    "type": "command",
                    "name": node["captures"].get("cmd.name", {}).get("text", ""),
                    "line_number": node["captures"].get("cmd.def", {}).get("start_point", [0])[0],
                    "is_pipeline": "cmd.pipe.def" in node["captures"],
                    "is_subshell": "cmd.sub.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.USES: ["variable", "function"],
                        PatternRelationType.DEPENDS_ON: ["command"]
                    }
                },
                name="command",
                description="Matches Shell command executions",
                examples=["ls -la", "echo $PATH | grep bin", "( cd /tmp && ls )"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.COMMANDS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["command"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_.-]+$'
                    }
                }
            )
        },
        PatternPurpose.REDIRECTS: {
            "redirect": AdaptivePattern(
                pattern="""
                [
                    (redirected_statement
                        command: (_) @redir.command
                        redirect: (file_redirect
                            descriptor: (_)? @redir.fd
                            operator: (_) @redir.op
                            file: (_) @redir.file)) @redir.def,
                    (heredoc_redirect
                        start: (_) @redir.heredoc.start
                        content: (_) @redir.heredoc.content
                        end: (_) @redir.heredoc.end) @redir.heredoc.def
                ]
                """,
                extract=lambda node: {
                    "type": "redirect",
                    "line_number": (
                        node["captures"].get("redir.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("redir.heredoc.def", {}).get("start_point", [0])[0]
                    ),
                    "operator": node["captures"].get("redir.op", {}).get("text", ""),
                    "is_heredoc": "redir.heredoc.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.MODIFIES: ["command", "pipeline"],
                        PatternRelationType.DEPENDS_ON: ["file"]
                    }
                },
                name="redirect",
                description="Matches Shell redirections",
                examples=["command > output.txt", "cat << EOF", "2>&1"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REDIRECTS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["redirect"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    }
}

class ShellPatternLearner(CrossProjectPatternLearner):
    """Enhanced Shell pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Shell-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("shell", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Shell patterns
        await self._pattern_processor.register_language_patterns(
            "shell", 
            SHELL_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "shell_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(SHELL_PATTERNS),
                "capabilities": list(SHELL_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="shell",
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
            
            # Finally add Shell-specific patterns
            async with AsyncErrorBoundary("shell_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "shell",
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
                shell_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(shell_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "shell_pattern_learner",
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
                "shell_pattern_learner",
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
                "shell_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "shell_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_shell_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Shell pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Shell-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("shell", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "shell", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_shell_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"shell_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "shell",
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
        await update_shell_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "shell_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_shell_pattern_context(
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
            language_id="shell",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "shell"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(SHELL_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_shell_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_shell_pattern_match_result(
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
        metadata={"language": "shell"}
    )

# Initialize pattern learner
pattern_learner = ShellPatternLearner()

async def initialize_shell_patterns():
    """Initialize Shell patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Shell patterns
    await pattern_processor.register_language_patterns(
        "shell",
        SHELL_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": SHELL_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await ShellPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "shell",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "shell_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(SHELL_PATTERNS),
            "capabilities": list(SHELL_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.CONTAINS: ["command", "variable", "pipeline"],
        PatternRelationType.DEPENDS_ON: ["function"]
    },
    "variable": {
        PatternRelationType.REFERENCED_BY: ["command", "pipeline"],
        PatternRelationType.DEPENDS_ON: ["variable"]
    },
    "command": {
        PatternRelationType.USES: ["variable", "function"],
        PatternRelationType.DEPENDS_ON: ["command"]
    },
    "redirect": {
        PatternRelationType.MODIFIES: ["command", "pipeline"],
        PatternRelationType.DEPENDS_ON: ["file"]
    }
}

# Export public interfaces
__all__ = [
    'SHELL_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_shell_pattern_match_result',
    'update_shell_pattern_metrics',
    'ShellPatternContext',
    'pattern_learner'
] 