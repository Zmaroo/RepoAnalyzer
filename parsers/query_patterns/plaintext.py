"""
Query patterns for plaintext files with enhanced pattern support.

This module provides plaintext-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Match, Optional, Set, Union
from dataclasses import dataclass, field
from parsers.types import (
    FileType, QueryPattern, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
from utils.error_handling import (
    handle_async_errors, AsyncErrorBoundary, ProcessingError, ErrorSeverity
)
from utils.logger import log
from utils.cache import UnifiedCache, cache_coordinator
from utils.cache_analytics import get_cache_analytics
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation
from utils.request_cache import cached_in_request, request_cache_context

# Language identifier
LANGUAGE = "plaintext"

@dataclass
class PlaintextPatternContext(PatternContext):
    """Plaintext-specific pattern context."""
    section_names: Set[str] = field(default_factory=set)
    list_types: Set[str] = field(default_factory=set)
    metadata_keys: Set[str] = field(default_factory=set)
    heading_levels: Set[int] = field(default_factory=set)
    code_languages: Set[str] = field(default_factory=set)
    has_sections: bool = False
    has_lists: bool = False
    has_metadata: bool = False
    has_code_blocks: bool = False
    has_references: bool = False
    has_headings: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.section_names)}:{len(self.heading_levels)}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "section": PatternPerformanceMetrics(),
    "list": PatternPerformanceMetrics(),
    "code_block": PatternPerformanceMetrics(),
    "metadata": PatternPerformanceMetrics(),
    "heading": PatternPerformanceMetrics(),
    "reference": PatternPerformanceMetrics()
}

# Initialize caches
_pattern_cache = UnifiedCache("plaintext_patterns")
_context_cache = UnifiedCache("plaintext_contexts")

async def initialize_caches():
    """Initialize pattern caches."""
    await cache_coordinator.register_cache("plaintext_patterns", _pattern_cache)
    await cache_coordinator.register_cache("plaintext_contexts", _context_cache)
    
    # Register warmup functions
    analytics = await get_cache_analytics()
    analytics.register_warmup_function(
        "plaintext_patterns",
        _warmup_pattern_cache
    )
    analytics.register_warmup_function(
        "plaintext_contexts",
        _warmup_context_cache
    )

async def _warmup_pattern_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for pattern cache."""
    results = {}
    for key in keys:
        try:
            patterns = ENHANCED_PATTERNS.get(PatternCategory.SYNTAX, {})
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
            context = PlaintextPatternContext()
            results[key] = context.__dict__
        except Exception as e:
            await log(f"Error warming up context cache for {key}: {e}", level="warning")
    return results

def extract_list_item(match: Match) -> Dict[str, Any]:
    """Extract list item information."""
    return {
        "type": "list_item",
        "content": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "confidence": 0.9
    }

def extract_header(match: Match) -> Dict[str, Any]:
    """Extract header information."""
    return {
        "type": "header",
        "level": len(match.group(1)) if match.group(1) else (1 if match.group(4) and match.group(4)[0] == '=' else 2),
        "content": match.group(2) if match.group(2) else match.group(3),
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "confidence": 0.95
    }

# Convert existing patterns to enhanced types
def create_enhanced_pattern(pattern_def: Dict[str, Any]) -> Union[AdaptivePattern, ResilientPattern]:
    """Create enhanced pattern from definition."""
    base_pattern = pattern_def.copy()
    
    # Determine if pattern should be resilient based on importance
    is_resilient = base_pattern.get("type") in {
        "header", "section", "list_item", "code_block", "metadata"
    }
    
    pattern_class = ResilientPattern if is_resilient else AdaptivePattern
    return pattern_class(**base_pattern)

# Convert PLAINTEXT_PATTERNS to ENHANCED_PATTERNS
ENHANCED_PATTERNS = {
    category: {
        name: create_enhanced_pattern({
            "name": name,
            "pattern": pattern.pattern,
            "extract": pattern.extract,
            "category": category,
            "purpose": pattern.purpose if hasattr(pattern, 'purpose') else PatternPurpose.UNDERSTANDING,
            "language_id": LANGUAGE,
            "confidence": getattr(pattern, 'confidence', 0.85)
        })
        for name, pattern in patterns.items()
    }
    for category, patterns in PLAINTEXT_PATTERNS.items()
}

# Initialize pattern learner with error handling
pattern_learner = CrossProjectPatternLearner()

@handle_async_errors(error_types=ProcessingError)
@cached_in_request
async def extract_plaintext_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from plaintext content for repository learning."""
    patterns = []
    context = PlaintextPatternContext()
    
    try:
        async with AsyncErrorBoundary(
            "plaintext_pattern_extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            # Update health status
            await global_health_monitor.update_component_status(
                "plaintext_pattern_processor",
                ComponentStatus.PROCESSING,
                details={"operation": "pattern_extraction"}
            )
            
            # Process patterns with monitoring
            with monitor_operation("extract_patterns", "plaintext_processor"):
                # Process each pattern category
                for category in PatternCategory:
                    if category in ENHANCED_PATTERNS:
                        category_patterns = ENHANCED_PATTERNS[category]
                        for pattern_name, pattern in category_patterns.items():
                            try:
                                matches = await pattern.matches(content, context)
                                for match in matches:
                                    patterns.append({
                                        "name": pattern_name,
                                        "category": category.value,
                                        "content": match.get("text", ""),
                                        "metadata": match,
                                        "confidence": pattern.confidence,
                                        "relationships": match.get("relationships", {})
                                    })
                                    
                                    # Update context
                                    if match["type"] == "header":
                                        context.heading_levels.add(match.get("level", 1))
                                        context.has_headings = True
                                    elif match["type"] == "section":
                                        context.section_names.add(match.get("title", ""))
                                        context.has_sections = True
                                    elif match["type"] == "list_item":
                                        context.list_types.add(match.get("list_type", "bullet"))
                                        context.has_lists = True
                                    elif match["type"] == "metadata":
                                        context.metadata_keys.add(match.get("key", ""))
                                        context.has_metadata = True
                                    elif match["type"] == "code_block":
                                        context.has_code_blocks = True
                                        if lang := match.get("language"):
                                            context.code_languages.add(lang)
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
            
            # Update final status
            await global_health_monitor.update_component_status(
                "plaintext_pattern_processor",
                ComponentStatus.HEALTHY,
                details={
                    "operation": "pattern_extraction_complete",
                    "patterns_found": len(patterns),
                    "context": {
                        "heading_levels": len(context.heading_levels),
                        "section_names": len(context.section_names),
                        "list_types": len(context.list_types),
                        "metadata_keys": len(context.metadata_keys),
                        "code_languages": len(context.code_languages)
                    }
                }
            )
    
    except Exception as e:
        await log(f"Error extracting plaintext patterns: {e}", level="error")
        await global_health_monitor.update_component_status(
            "plaintext_pattern_processor",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"error": str(e)}
        )
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        PatternRelationType.CONTAINS: ["header", "section", "paragraph", "list_item", "code_block"],
        PatternRelationType.DEPENDS_ON: []
    },
    "section": {
        PatternRelationType.CONTAINS: ["paragraph", "list_item", "code_block"],
        PatternRelationType.DEPENDS_ON: ["document"]
    },
    "header": {
        PatternRelationType.CONTAINS: [],
        PatternRelationType.DEPENDS_ON: ["document", "section"]
    },
    "paragraph": {
        PatternRelationType.CONTAINS: ["url", "email", "path", "inline_code"],
        PatternRelationType.DEPENDS_ON: ["document", "section"]
    },
    "list_item": {
        PatternRelationType.CONTAINS: ["url", "email", "path", "inline_code"],
        PatternRelationType.DEPENDS_ON: ["document", "section"]
    },
    "code_block": {
        PatternRelationType.CONTAINS: ["inline_code"],
        PatternRelationType.DEPENDS_ON: ["document", "section"]
    },
    "metadata": {
        PatternRelationType.CONTAINS: [],
        PatternRelationType.DEPENDS_ON: ["document"]
    }
}

# Export public interfaces
__all__ = [
    'ENHANCED_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_plaintext_patterns_for_learning',
    'PlaintextPatternContext',
    'pattern_learner',
    'initialize_caches',
    'PATTERN_METRICS'
] 