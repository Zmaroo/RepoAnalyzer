"""
Query patterns for requirements.txt files.

This module provides requirements.txt-specific patterns with enhanced type system and relationships.
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
from utils.cache import UnifiedCache
from utils.cache import cache_coordinator

# Language identifier
LANGUAGE_ID = "requirements"

# Requirements capabilities (extends common capabilities)
REQUIREMENTS_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.DEPENDENCY_MANAGEMENT,
    AICapability.VERSION_CONTROL,
    AICapability.PACKAGE_MANAGEMENT
}

@dataclass
class RequirementsPatternContext(PatternContext):
    """Requirements.txt-specific pattern context."""
    package_names: Set[str] = field(default_factory=set)
    version_specs: Set[str] = field(default_factory=set)
    constraint_names: Set[str] = field(default_factory=set)
    has_versions: bool = False
    has_constraints: bool = False
    has_direct_urls: bool = False
    has_local_paths: bool = False
    has_editable: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.package_names)}:{self.has_versions}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "package": PatternPerformanceMetrics(),
    "version": PatternPerformanceMetrics(),
    "constraint": PatternPerformanceMetrics(),
    "url": PatternPerformanceMetrics(),
    "option": PatternPerformanceMetrics()
}

REQUIREMENTS_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "package": TreeSitterResilientPattern(
                pattern="""
                [
                    (requirement
                        package: (package) @syntax.pkg.name
                        version_spec: (version_spec
                            version_cmp: (version_cmp) @syntax.pkg.cmp
                            version: (version) @syntax.pkg.version)? @syntax.pkg.version_spec
                        extras: (extras
                            package: (package)* @syntax.pkg.extras.package)? @syntax.pkg.extras) @syntax.pkg,
                    (requirement
                        package: (package) @syntax.direct.pkg
                        url_spec: (url_spec) @syntax.direct.url) @syntax.direct,
                    (requirement
                        package: (package) @syntax.local.pkg
                        path_spec: (path_spec) @syntax.local.path) @syntax.local
                ]
                """,
                extract=lambda node: {
                    "type": "package",
                    "name": (
                        node["captures"].get("syntax.pkg.name", {}).get("text", "") or
                        node["captures"].get("syntax.direct.pkg", {}).get("text", "") or
                        node["captures"].get("syntax.local.pkg", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.pkg", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.direct", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.local", {}).get("start_point", [0])[0]
                    ),
                    "has_version": "syntax.pkg.version_spec" in node["captures"],
                    "is_direct_url": "syntax.direct" in node["captures"],
                    "is_local_path": "syntax.local" in node["captures"],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["version", "constraint"],
                        PatternRelationType.REFERENCED_BY: ["option"]
                    }
                },
                name="package",
                description="Matches requirements.txt package declarations",
                examples=["package==1.0.0", "package @ http://example.com", "./local/package"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["package"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_.-]+$'
                    }
                }
            ),
            "constraint": TreeSitterResilientPattern(
                pattern="""
                [
                    (requirement
                        marker_spec: (marker_spec
                            marker_var: (marker_var) @syntax.marker.var
                            marker_op: (marker_op) @syntax.marker.op
                            marker_value: [(quoted_string) (marker_var)] @syntax.marker.value) @syntax.marker.spec) @syntax.marker,
                    (requirement
                        version_spec: (version_spec
                            version_cmp: [(version_cmp) (version_cmp_multi)] @syntax.version.op
                            version: (version) @syntax.version.value) @syntax.version) @syntax.version.req
                ]
                """,
                extract=lambda node: {
                    "type": "constraint",
                    "line_number": (
                        node["captures"].get("syntax.marker", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.version.req", {}).get("start_point", [0])[0]
                    ),
                    "operator": (
                        node["captures"].get("syntax.marker.op", {}).get("text", "") or
                        node["captures"].get("syntax.version.op", {}).get("text", "")
                    ),
                    "is_marker": "syntax.marker" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["package"],
                        PatternRelationType.DEPENDS_ON: ["version"]
                    }
                },
                name="constraint",
                description="Matches requirements.txt constraints",
                examples=["package>=1.0.0", "package; python_version>='3.7'"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["constraint"],
                    "validation": {
                        "required_fields": ["operator"],
                        "name_format": None
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.OPTIONS: {
            "option": TreeSitterAdaptivePattern(
                pattern="""
                [
                    (global_opt
                        option: (option) @option.global.name
                        value: [(argument) (quoted_string) (path) (url)]* @option.global.value) @option.global,
                    (requirement_opt
                        option: (option) @option.req.name
                        value: [(argument) (quoted_string)] @option.req.value) @option.req
                ]
                """,
                extract=lambda node: {
                    "type": "option",
                    "line_number": (
                        node["captures"].get("option.global", {}).get("start_point", [0])[0] or
                        node["captures"].get("option.req", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("option.global.name", {}).get("text", "") or
                        node["captures"].get("option.req.name", {}).get("text", "")
                    ),
                    "is_global": "option.global" in node["captures"],
                    "relationships": {
                        PatternRelationType.APPLIES_TO: ["package"],
                        PatternRelationType.DEPENDS_ON: ["option"]
                    }
                },
                name="option",
                description="Matches requirements.txt options",
                examples=["-i https://pypi.org/simple", "--no-binary :all:"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.OPTIONS,
                language_id=LANGUAGE_ID,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["option"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^-{1,2}[a-z][a-z0-9-]*$'
                    }
                }
            )
        }
    },

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "version_conflict": QueryPattern(
            name="version_conflict",
            pattern=r'^([a-zA-Z0-9_-]+)==([0-9.]+).*\n(?:.*\n)*?\1==(?!\2)',
            extract=lambda m: {
                "type": "version_conflict",
                "package": m.group(1),
                "version": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects version conflicts", "examples": ["package==1.0\npackage==2.0"]}
        ),
        "invalid_version": QueryPattern(
            name="invalid_version",
            pattern=r'^([a-zA-Z0-9_-]+)[^=><~]*$',
            extract=lambda m: {
                "type": "invalid_version",
                "package": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects missing version specifiers", "examples": ["requests"]}
        ),
        "insecure_version": QueryPattern(
            name="insecure_version",
            pattern=r'^([a-zA-Z0-9_-]+)==([0-9.]+)',
            extract=lambda m: {
                "type": "insecure_version",
                "package": m.group(1),
                "version": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects potentially insecure versions", "examples": ["django==1.8.0"]}
        ),
        "invalid_constraint": QueryPattern(
            name="invalid_constraint",
            pattern=r'^([a-zA-Z0-9_-]+)\s*([<>]=?|==|~=|!=)\s*([^,\s]+)',
            extract=lambda m: {
                "type": "invalid_constraint",
                "package": m.group(1),
                "operator": m.group(2),
                "version": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects invalid version constraints", "examples": ["package => 1.0"]}
        ),
        "duplicate_requirement": QueryPattern(
            name="duplicate_requirement",
            pattern=r'^([a-zA-Z0-9_-]+)(?:[<>=!~]|$).*\n(?:.*\n)*?\1(?:[<>=!~]|$)',
            extract=lambda m: {
                "type": "duplicate_requirement",
                "package": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects duplicate package requirements", "examples": ["package>=1.0\npackage<=2.0"]}
        )
    }
}

class RequirementsPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced requirements.txt pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with requirements.txt-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("requirements", FileType.DEPENDENCY)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Requirements patterns
        await self._pattern_processor.register_language_patterns(
            "requirements", 
            REQUIREMENTS_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "requirements_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(REQUIREMENTS_PATTERNS),
                "capabilities": list(REQUIREMENTS_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="requirements",
                file_type=FileType.DEPENDENCY,
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
            
            # Finally add Requirements-specific patterns
            async with AsyncErrorBoundary("requirements_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "requirements",
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
                requirements_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(requirements_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "requirements_pattern_learner",
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
                "requirements_pattern_learner",
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
                "requirements_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "requirements_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

# Initialize caches
pattern_cache = UnifiedCache("requirements_patterns", eviction_policy="lru")
context_cache = UnifiedCache("requirements_contexts", eviction_policy="lru")

@cached_in_request
async def get_requirements_pattern_cache():
    """Get the requirements pattern cache from the coordinator."""
    return await cache_coordinator.get_cache("requirements_patterns")

@cached_in_request
async def get_requirements_context_cache():
    """Get the requirements context cache from the coordinator."""
    return await cache_coordinator.get_cache("requirements_contexts")

async def initialize_requirements_patterns():
    """Initialize requirements.txt patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Initialize caches through coordinator
    await cache_coordinator.register_cache("requirements_patterns", pattern_cache)
    await cache_coordinator.register_cache("requirements_contexts", context_cache)
    
    # Register cache warmup functions
    analytics = await get_cache_analytics()
    analytics.register_warmup_function(
        "requirements_patterns",
        _warmup_pattern_cache
    )
    analytics.register_warmup_function(
        "requirements_contexts",
        _warmup_context_cache
    )
    
    # Register patterns and initialize learner
    await pattern_processor.register_language_patterns(
        "requirements",
        REQUIREMENTS_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": REQUIREMENTS_CAPABILITIES
        }
    )
    
    pattern_learner = await RequirementsPatternLearner.create()
    await pattern_processor.register_pattern_learner("requirements", pattern_learner)
    
    await global_health_monitor.update_component_status(
        "requirements_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(REQUIREMENTS_PATTERNS),
            "capabilities": list(REQUIREMENTS_CAPABILITIES)
        }
    )

async def _warmup_pattern_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for pattern cache."""
    results = {}
    for key in keys:
        try:
            patterns = REQUIREMENTS_PATTERNS.get(PatternCategory.SYNTAX, {})
            if patterns:
                results[key] = patterns
        except Exception as e:
            await log(f"Error warming up pattern cache for {key}: {e}", level="warning")
    return results

async def _warmup_context_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for context cache."""
    results = {}
    for key in keys:
        try:
            context = await create_requirements_pattern_context("", {})
            results[key] = context.__dict__
        except Exception as e:
            await log(f"Error warming up context cache for {key}: {e}", level="warning")
    return results

@handle_async_errors(error_types=ProcessingError)
async def process_requirements_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a requirements.txt pattern with full system integration."""
    # Try pattern cache first
    cache_key = f"requirements_pattern_{pattern.name}_{hash(source_code)}"
    pattern_cache = await get_requirements_pattern_cache()
    cached_result = await pattern_cache.get_async(cache_key)
    if cached_result:
        return cached_result
        
    # Then check request cache
    request_cache = get_current_request_cache()
    if request_cache:
        request_cached = await request_cache.get(cache_key)
        if request_cached:
            return request_cached
    
    # Process pattern if not cached
    common_result = await process_tree_sitter_pattern(pattern, source_code, context)
    if common_result:
        # Cache results
        await pattern_cache.set_async(cache_key, common_result)
        if request_cache:
            await request_cache.set(cache_key, common_result)
        return common_result
    
    # Rest of the existing processing logic...
    # ... rest of the function remains the same ...

async def create_requirements_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create requirements.txt-specific pattern context with tree-sitter integration.
    
    This function creates a tree-sitter context for requirements.txt patterns
    with full system integration.
    """
    context = PatternContext(
        language_id=LANGUAGE_ID,
        pattern_name="requirements",
        category=PatternCategory.SYNTAX,
        purpose=PatternPurpose.UNDERSTANDING
    )
    
    # Add requirements-specific information
    context.language_stats = {"language": LANGUAGE_ID}
    context.relevant_patterns = list(REQUIREMENTS_PATTERNS.keys())
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_requirements_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_requirements_pattern_match_result(
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
        metadata={"language": "requirements"}
    )

# Initialize pattern learner
pattern_learner = RequirementsPatternLearner()

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "package": {
        PatternRelationType.DEPENDS_ON: ["version", "constraint"],
        PatternRelationType.REFERENCED_BY: ["option"]
    },
    "constraint": {
        PatternRelationType.CONTAINED_BY: ["package"],
        PatternRelationType.DEPENDS_ON: ["version"]
    },
    "option": {
        PatternRelationType.APPLIES_TO: ["package"],
        PatternRelationType.DEPENDS_ON: ["option"]
    }
}

# Export public interfaces
__all__ = [
    'REQUIREMENTS_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_requirements_pattern_context',
    'get_requirements_pattern_match_result',
    'update_requirements_pattern_metrics',
    'RequirementsPatternContext',
    'LANGUAGE_ID'
]