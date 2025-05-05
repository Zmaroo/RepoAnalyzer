"""Query patterns for PHP files.

This module provides PHP-specific patterns with enhanced type system and relationships.
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
LANGUAGE_ID = "php"

# PHP capabilities (extends common capabilities)
PHP_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.OBJECT_ORIENTED,
    AICapability.ATTRIBUTES,
    AICapability.NAMESPACES
}

@dataclass
class PHPPatternContext(PatternContext):
    """PHP-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    namespace_names: Set[str] = field(default_factory=set)
    trait_names: Set[str] = field(default_factory=set)
    has_attributes: bool = False
    has_traits: bool = False
    has_enums: bool = False
    has_namespaces: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_attributes}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "namespace": PatternPerformanceMetrics(),
    "attribute": PatternPerformanceMetrics(),
    "trait": PatternPerformanceMetrics()
}

PHP_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": TreeSitterResilientPattern(
                pattern="""
                [
                    (class_declaration
                        modifiers: [(abstract) (final)]* @syntax.class.modifier
                        name: (name) @syntax.class.name
                        base_clause: (base_clause)? @syntax.class.extends
                        interfaces: (class_interface_clause)? @syntax.class.implements
                        body: (declaration_list) @syntax.class.body) @syntax.class.def,
                    (interface_declaration
                        name: (name) @syntax.interface.name
                        interfaces: (interface_base_clause)? @syntax.interface.extends
                        body: (declaration_list) @syntax.interface.body) @syntax.interface.def,
                    (trait_declaration
                        name: (name) @syntax.trait.name
                        body: (declaration_list) @syntax.trait.body) @syntax.trait.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.interface.name", {}).get("text", "") or
                        node["captures"].get("syntax.trait.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0],
                    "is_interface": "syntax.interface.def" in node["captures"],
                    "is_trait": "syntax.trait.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "property", "attribute"],
                        PatternRelationType.DEPENDS_ON: ["interface", "class"]
                    }
                },
                name="class",
                description="Matches PHP class declarations",
                examples=["class MyClass extends BaseClass", "interface MyInterface"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["class"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": TreeSitterResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (name) @syntax.func.name
                        parameters: (formal_parameters) @syntax.func.params
                        body: (compound_statement) @syntax.func.body) @syntax.func.def,
                    (method_declaration
                        modifiers: [(public) (private) (protected) (static) (final) (abstract)]* @syntax.method.modifier
                        name: (name) @syntax.method.name
                        parameters: (formal_parameters) @syntax.method.params
                        body: (compound_statement)? @syntax.method.body) @syntax.method.def,
                    (arrow_function 
                        parameters: (formal_parameters) @syntax.arrow.params
                        body: (_) @syntax.arrow.body) @syntax.arrow.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.method.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_method": "syntax.method.def" in node["captures"],
                    "is_arrow": "syntax.arrow.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["class"]
                    }
                },
                name="function",
                description="Matches PHP function declarations",
                examples=["function process($data)", "public function handle(): void"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.ATTRIBUTES: {
            "attribute": TreeSitterAdaptivePattern(
                pattern="""
                [
                    (attribute
                        name: (qualified_name) @attr.name
                        arguments: (arguments)? @attr.args) @attr.def,
                    (attribute_group
                        attributes: (attribute)* @attr.group.items) @attr.group
                ]
                """,
                extract=lambda node: {
                    "type": "attribute",
                    "line_number": node["captures"].get("attr.def", {}).get("start_point", [0])[0],
                    "name": node["captures"].get("attr.name", {}).get("text", ""),
                    "has_arguments": "attr.args" in node["captures"],
                    "is_group": "attr.group" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["class", "method", "property"],
                        PatternRelationType.DEPENDS_ON: ["class"]
                    }
                },
                name="attribute",
                description="Matches PHP 8 attributes",
                examples=["#[Route('/api')]", "#[Attribute]"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.ATTRIBUTES,
                language_id=LANGUAGE_ID,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["attribute"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_\\]*$'
                    }
                }
            )
        },
        PatternPurpose.NAMESPACES: {
            "namespace": TreeSitterAdaptivePattern(
                pattern="""
                [
                    (namespace_definition
                        name: (namespace_name)? @ns.name
                        body: (compound_statement) @ns.body) @ns.def,
                    (namespace_use_declaration
                        clauses: (namespace_use_clause
                            name: (qualified_name) @ns.use.name
                            alias: (namespace_aliasing_clause)? @ns.use.alias)*) @ns.use
                ]
                """,
                extract=lambda node: {
                    "type": "namespace",
                    "line_number": node["captures"].get("ns.def", {}).get("start_point", [0])[0],
                    "name": node["captures"].get("ns.name", {}).get("text", ""),
                    "is_use": "ns.use" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["class", "function", "trait"],
                        PatternRelationType.DEPENDS_ON: ["namespace"]
                    }
                },
                name="namespace",
                description="Matches PHP namespace declarations",
                examples=["namespace App\\Controllers;", "use App\\Models\\User;"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.NAMESPACES,
                language_id=LANGUAGE_ID,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["namespace"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[A-Z][a-zA-Z0-9_\\]*$'
                    }
                }
            )
        }
    }
}

class PHPPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced PHP pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with PHP-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("php", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register PHP patterns
        await self._pattern_processor.register_language_patterns(
            "php", 
            PHP_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "php_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(PHP_PATTERNS),
                "capabilities": list(PHP_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="php",
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
            
            # Finally add PHP-specific patterns
            async with AsyncErrorBoundary("php_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "php",
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
                php_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(php_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "php_pattern_learner",
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
                "php_pattern_learner",
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
                "php_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "php_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_php_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a PHP pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_tree_sitter_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to PHP-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("php", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "php", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_tree_sitter_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"php_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "php",
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
        await update_php_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "php_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_php_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create PHP-specific pattern context with tree-sitter integration.
    
    This function creates a tree-sitter based context for PHP patterns
    with full system integration.
    """
    # Create a base tree-sitter context
    base_context = await create_tree_sitter_context(
        file_path,
        code_structure,
        language_id=LANGUAGE_ID,
        learned_patterns=learned_patterns
    )
    
    # Add PHP-specific information
    base_context.language_stats = {"language": LANGUAGE_ID}
    base_context.relevant_patterns = list(PHP_PATTERNS.keys())
    
    # Add system integration metadata
    base_context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return base_context

def update_php_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_php_pattern_match_result(
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
        metadata={"language": "php"}
    )

# Initialize pattern learner
pattern_learner = PHPPatternLearner()

async def initialize_php_patterns():
    """Initialize PHP patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register PHP patterns
    await pattern_processor.register_language_patterns(
        "php",
        PHP_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": PHP_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await PHPPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "php",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "php_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(PHP_PATTERNS),
            "capabilities": list(PHP_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "property", "attribute"],
        PatternRelationType.DEPENDS_ON: ["interface", "class"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["class"]
    },
    "attribute": {
        PatternRelationType.CONTAINED_BY: ["class", "method", "property"],
        PatternRelationType.DEPENDS_ON: ["class"]
    },
    "namespace": {
        PatternRelationType.CONTAINS: ["class", "function", "trait"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    }
}

# Export public interfaces
__all__ = [
    'PHP_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_php_pattern_context',
    'get_php_pattern_match_result',
    'update_php_pattern_metrics',
    'PHPPatternLearner',
    'process_php_pattern',
    'LANGUAGE_ID'
] 