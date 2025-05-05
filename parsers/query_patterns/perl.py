"""
Query patterns for Perl files.

This module provides Perl-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Set, Union
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from .common import (
    COMMON_PATTERNS, COMMON_CAPABILITIES, 
    process_tree_sitter_pattern, validate_tree_sitter_pattern, create_tree_sitter_context
)
from .enhanced_patterns import (
    TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern,
    TreeSitterCrossProjectPatternLearner
)
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
LANGUAGE_ID = "perl"

# Perl capabilities (extends common capabilities)
PERL_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.SCRIPTING,
    AICapability.REGEX,
    AICapability.OBJECT_ORIENTED
}

@dataclass
class PerlPatternContext(PatternContext):
    """Perl-specific pattern context."""
    subroutine_names: Set[str] = field(default_factory=set)
    package_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    has_moose: bool = False
    has_regex: bool = False
    has_dbi: bool = False
    has_object_oriented: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.subroutine_names)}:{self.has_moose}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "subroutine": PatternPerformanceMetrics(),
    "package": PatternPerformanceMetrics(),
    "regex": PatternPerformanceMetrics(),
    "object": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics()
}

PERL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "subroutine": TreeSitterResilientPattern(
                pattern="""
                [
                    (subroutine_declaration
                        attributes: (attribute_list)? @syntax.sub.attrs
                        name: [(bare_word) @syntax.sub.name
                              (package_qualified_word) @syntax.sub.qualified_name]
                        prototype: (prototype)? @syntax.sub.proto
                        signature: (signature)? @syntax.sub.sig
                        body: (block) @syntax.sub.body) @syntax.sub.def
                ]
                """,
                extract=lambda node: {
                    "type": "subroutine",
                    "name": (
                        node["captures"].get("syntax.sub.name", {}).get("text", "") or
                        node["captures"].get("syntax.sub.qualified_name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.sub.def", {}).get("start_point", [0])[0],
                    "has_signature": "syntax.sub.sig" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="subroutine",
                description="Matches Perl subroutine declarations",
                examples=["sub process_data { }", "sub MyPackage::handle_event { }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["subroutine"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:]*$'
                    }
                }
            ),
            "package": TreeSitterResilientPattern(
                pattern="""
                [
                    (package_statement
                        name: (package_qualified_word) @syntax.pkg.name
                        version: (version_number)? @syntax.pkg.version
                        block: (block)? @syntax.pkg.body) @syntax.pkg.def,
                    (use_statement
                        module: (package_qualified_word) @syntax.use.module
                        version: (version_number)? @syntax.use.version
                        imports: (import_list)? @syntax.use.imports) @syntax.use.def
                ]
                """,
                extract=lambda node: {
                    "type": "package",
                    "name": (
                        node["captures"].get("syntax.pkg.name", {}).get("text", "") or
                        node["captures"].get("syntax.use.module", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.pkg.def", {}).get("start_point", [0])[0],
                    "is_use": "syntax.use.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["subroutine"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="package",
                description="Matches Perl package declarations",
                examples=["package MyModule;", "use strict;"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["package"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9:]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.OBJECT_ORIENTED: {
            "moose": TreeSitterAdaptivePattern(
                pattern="""
                [
                    (use_statement
                        module: (package_qualified_word) @oop.module
                        (#match? @oop.module "^(Moose|Moo|Mouse|Class::Accessor)$")) @oop.use,
                        
                    (function_call
                        function: (bare_word) @oop.func.name
                        (#match? @oop.func.name "^(has|extends|with|method|before|after|around)$")
                        arguments: (argument_list) @oop.func.args) @oop.func
                ]
                """,
                extract=lambda node: {
                    "type": "object_oriented",
                    "line_number": node["captures"].get("oop.use", {}).get("start_point", [0])[0],
                    "framework": node["captures"].get("oop.module", {}).get("text", ""),
                    "method_type": node["captures"].get("oop.func.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["package"],
                        PatternRelationType.CONTAINS: ["subroutine"]
                    }
                },
                name="moose",
                description="Matches Perl OOP patterns",
                examples=["use Moose;", "has 'name' => (is => 'rw');"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.OBJECT_ORIENTED,
                language_id=LANGUAGE_ID,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["object"],
                    "validation": {
                        "required_fields": []
                    }
                }
            )
        },
        PatternPurpose.REGEX: {
            "regex": TreeSitterAdaptivePattern(
                pattern="""
                [
                    (regex
                        pattern: (_) @regex.pattern
                        modifiers: (_)? @regex.mods) @regex.def,
                        
                    (substitution
                        pattern: (_) @regex.sub.pattern
                        replacement: (_) @regex.sub.repl
                        modifiers: (_)? @regex.sub.mods) @regex.sub
                ]
                """,
                extract=lambda node: {
                    "type": "regex",
                    "line_number": node["captures"].get("regex.def", {}).get("start_point", [0])[0],
                    "is_substitution": "regex.sub" in node["captures"],
                    "pattern": (
                        node["captures"].get("regex.pattern", {}).get("text", "") or
                        node["captures"].get("regex.sub.pattern", {}).get("text", "")
                    ),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: [],
                        PatternRelationType.REFERENCES: []
                    }
                },
                name="regex",
                description="Matches Perl regex patterns",
                examples=["m/pattern/g", "s/pattern/replacement/"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REGEX,
                language_id=LANGUAGE_ID,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["regex"],
                    "validation": {
                        "required_fields": ["pattern"]
                    }
                }
            )
        }
    }
}

class PerlPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced Perl pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Perl-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("perl", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Perl patterns
        await self._pattern_processor.register_language_patterns(
            "perl", 
            PERL_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "perl_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(PERL_PATTERNS),
                "capabilities": list(PERL_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="perl",
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
            
            # Finally add Perl-specific patterns
            async with AsyncErrorBoundary("perl_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "perl",
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
                perl_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(perl_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "perl_pattern_learner",
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
                "perl_pattern_learner",
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
                "perl_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "perl_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_perl_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Perl pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_tree_sitter_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Perl-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("perl", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "perl", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_tree_sitter_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"perl_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "perl",
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
        await update_perl_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "perl_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_perl_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create Perl-specific pattern context with tree-sitter integration.
    
    This function creates a tree-sitter based context for Perl patterns
    with full system integration.
    """
    # Create a base tree-sitter context
    base_context = await create_tree_sitter_context(
        file_path,
        code_structure,
        language_id=LANGUAGE_ID,
        learned_patterns=learned_patterns
    )
    
    # Add Perl-specific information
    base_context.language_stats = {"language": LANGUAGE_ID}
    base_context.relevant_patterns = list(PERL_PATTERNS.keys())
    
    # Add system integration metadata
    base_context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return base_context

def update_perl_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_perl_pattern_match_result(
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
        metadata={"language": "perl"}
    )

# Initialize pattern learner
pattern_learner = PerlPatternLearner()

async def initialize_perl_patterns():
    """Initialize Perl patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Perl patterns
    await pattern_processor.register_language_patterns(
        "perl",
        PERL_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": PERL_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await PerlPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "perl",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "perl_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(PERL_PATTERNS),
            "capabilities": list(PERL_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "subroutine": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["package"]
    },
    "package": {
        PatternRelationType.CONTAINS: ["subroutine"],
        PatternRelationType.DEPENDS_ON: ["package"]
    },
    "object_oriented": {
        PatternRelationType.DEPENDS_ON: ["package"],
        PatternRelationType.CONTAINS: ["subroutine"]
    },
    "regex": {
        PatternRelationType.DEPENDS_ON: [],
        PatternRelationType.REFERENCES: []
    }
}

# Export public interfaces
__all__ = [
    'PERL_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_perl_pattern_context',
    'get_perl_pattern_match_result',
    'update_perl_pattern_metrics',
    'PerlPatternLearner',
    'process_perl_pattern',
    'LANGUAGE_ID'
] 