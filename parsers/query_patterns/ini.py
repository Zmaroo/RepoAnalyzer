"""Query patterns for INI/Properties files with enhanced pattern support.

This module provides INI/Properties file patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Match, Optional, Set, Union
from dataclasses import dataclass, field
import time
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
LANGUAGE = "ini"

@dataclass
class INIPatternContext(PatternContext):
    """INI-specific pattern context."""
    section_names: Set[str] = field(default_factory=set)
    property_names: Set[str] = field(default_factory=set)
    has_sections: bool = False
    has_includes: bool = False
    has_properties: bool = False
    has_comments: bool = False
    has_references: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.section_names)}:{len(self.property_names)}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "section": PatternPerformanceMetrics(),
    "property": PatternPerformanceMetrics(),
    "include": PatternPerformanceMetrics(),
    "reference": PatternPerformanceMetrics(),
    "comment": PatternPerformanceMetrics()
}

# Initialize caches
_pattern_cache = UnifiedCache("ini_patterns")
_context_cache = UnifiedCache("ini_contexts")

async def initialize_caches():
    """Initialize pattern caches."""
    await cache_coordinator.register_cache("ini_patterns", _pattern_cache)
    await cache_coordinator.register_cache("ini_contexts", _context_cache)
    
    # Register warmup functions
    analytics = await get_cache_analytics()
    analytics.register_warmup_function(
        "ini_patterns",
        _warmup_pattern_cache
    )
    analytics.register_warmup_function(
        "ini_contexts",
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
            context = INIPatternContext()
            results[key] = context.__dict__
        except Exception as e:
            await log(f"Error warming up context cache for {key}: {e}", level="warning")
    return results

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "name": match.group(1).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "confidence": 0.95,
        "relationships": {
            PatternRelationType.CONTAINS: ["property", "comment"],
            PatternRelationType.DEPENDS_ON: []
        }
    }

def extract_property(match: Match) -> Dict[str, Any]:
    """Extract property information."""
    return {
        "type": "property",
        "key": match.group(1).strip(),
        "value": match.group(2).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "confidence": 0.95,
        "relationships": {
            PatternRelationType.CONTAINED_BY: ["section", "root"],
            PatternRelationType.REFERENCES: []
        }
    }

# Define base patterns
INI_PATTERNS = {
    PatternCategory.SYNTAX: {
        "section": QueryPattern(
            name="section",
            pattern=r'^\[([^\]]+)\]$',
            extract=lambda m: {
                "type": "section",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches INI section headers", "examples": ["[section]"]}
        ),
        "property": QueryPattern(
            name="property",
            pattern=r'^([^=]+)=(.*)$',
            extract=lambda m: {
                "type": "property",
                "key": m.group(1).strip(),
                "value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches INI property assignments", "examples": ["key = value"]}
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": QueryPattern(
            name="comment",
            pattern=r'^[#;](.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches INI comments", "examples": ["# Comment", "; Another comment"]}
        ),
        "section_comment": QueryPattern(
            name="section_comment",
            pattern=r'^[#;]\s*Section:\s*(.*)$',
            extract=lambda m: {
                "type": "section_comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches section documentation", "examples": ["# Section: Configuration"]}
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "include": QueryPattern(
            name="include",
            pattern=r'^include\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "include",
                "path": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.DEPENDENCIES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches include directives", "examples": ["include = other.ini"]}
        ),
        "reference": QueryPattern(
            name="reference",
            pattern=r'\$\{([^}]+)\}',
            extract=lambda m: {
                "type": "reference",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.DEPENDENCIES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches variable references", "examples": ["${variable}"]}
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "duplicate_property": QueryPattern(
            name="duplicate_property",
            pattern=r'^([^=]+)=(.*)$\n(?:.*\n)*?^\1=',
            extract=lambda m: {
                "type": "duplicate_property",
                "key": m.group(1).strip(),
                "first_value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.BEST_PRACTICES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects duplicate property definitions", "examples": ["key = value1\nkey = value2"]}
        ),
        "malformed_section": QueryPattern(
            name="malformed_section",
            pattern=r'^\[[^\]]*$',
            extract=lambda m: {
                "type": "malformed_section",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.BEST_PRACTICES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects malformed section headers", "examples": ["[unclosed_section"]}
        )
    },

    PatternCategory.COMMON_ISSUES: {
        "duplicate_property": QueryPattern(
            name="duplicate_property",
            pattern=r'^([^=]+)=(.*)$\n(?:.*\n)*?^\1=',
            extract=lambda m: {
                "type": "duplicate_property",
                "key": m.group(1).strip(),
                "first_value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects duplicate property definitions", "examples": ["key = value1\nkey = value2"]}
        ),
        "malformed_section": QueryPattern(
            name="malformed_section",
            pattern=r'^\[[^\]]*$',
            extract=lambda m: {
                "type": "malformed_section",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects malformed section headers", "examples": ["[unclosed_section"]}
        )
    }
}

# Convert existing patterns to enhanced types
def create_enhanced_pattern(pattern_def: Dict[str, Any]) -> Union[AdaptivePattern, ResilientPattern]:
    """Create enhanced pattern from definition."""
    base_pattern = pattern_def.copy()
    
    # Determine if pattern should be resilient based on importance
    is_resilient = base_pattern.get("type") in {
        "section", "property", "include", "reference"
    }
    
    pattern_class = ResilientPattern if is_resilient else AdaptivePattern
    return pattern_class(**base_pattern)

# Convert INI_PATTERNS to ENHANCED_PATTERNS
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
    for category, patterns in INI_PATTERNS.items()
}

# Initialize pattern learner with error handling
pattern_learner = CrossProjectPatternLearner()

@handle_async_errors(error_types=ProcessingError)
@cached_in_request
async def extract_ini_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from INI content for repository learning."""
    patterns = []
    context = INIPatternContext()
    
    try:
        async with AsyncErrorBoundary(
            "ini_pattern_extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            # Update health status
            await global_health_monitor.update_component_status(
                "ini_pattern_processor",
                ComponentStatus.PROCESSING,
                details={"operation": "pattern_extraction"}
            )
            
            # Process patterns with monitoring
            with monitor_operation("extract_patterns", "ini_processor"):
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
                                    
                                    # Update metrics
                                    if pattern_name in PATTERN_METRICS:
                                        PATTERN_METRICS[pattern_name].update(
                                            True,
                                            time.time(),
                                            context.get_context_key(),
                                            "ini"
                                        )
                                    
                                    # Update context
                                    if match["type"] == "section":
                                        context.section_names.add(match.get("name", ""))
                                        context.has_sections = True
                                    elif match["type"] == "property":
                                        context.property_names.add(match.get("key", ""))
                                        context.has_properties = True
                                    elif match["type"] == "include":
                                        context.has_includes = True
                                    elif match["type"] == "reference":
                                        context.has_references = True
                                    elif match["type"] == "comment":
                                        context.has_comments = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                if pattern_name in PATTERN_METRICS:
                                    PATTERN_METRICS[pattern_name].update(
                                        False,
                                        time.time(),
                                        context.get_context_key(),
                                        "ini"
                                    )
                                continue
            
            # Update final status
            await global_health_monitor.update_component_status(
                "ini_pattern_processor",
                ComponentStatus.HEALTHY,
                details={
                    "operation": "pattern_extraction_complete",
                    "patterns_found": len(patterns),
                    "context": {
                        "section_names": len(context.section_names),
                        "property_names": len(context.property_names),
                        "has_includes": context.has_includes,
                        "has_references": context.has_references,
                        "has_comments": context.has_comments
                    }
                }
            )
    
    except Exception as e:
        await log(f"Error extracting INI patterns: {e}", level="error")
        await global_health_monitor.update_component_status(
            "ini_pattern_processor",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"error": str(e)}
        )
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "section": {
        PatternRelationType.CONTAINS: ["property", "comment"],
        PatternRelationType.DEPENDS_ON: ["include"],
        PatternRelationType.REFERENCES: ["reference"]
    },
    "property": {
        PatternRelationType.CONTAINED_BY: ["section", "root"],
        PatternRelationType.REFERENCES: ["reference"],
        PatternRelationType.DEPENDS_ON: ["include"]
    },
    "reference": {
        PatternRelationType.REFERENCES: ["property"],
        PatternRelationType.CONTAINED_BY: ["section", "property"]
    },
    "include": {
        PatternRelationType.DEPENDS_ON: ["property"],
        PatternRelationType.REFERENCES: ["section"]
    },
    "comment": {
        PatternRelationType.CONTAINED_BY: ["section", "property"],
        PatternRelationType.REFERENCES: []
    }
}

# Export public interfaces
__all__ = [
    'ENHANCED_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_ini_patterns_for_learning',
    'INIPatternContext',
    'pattern_learner',
    'initialize_caches',
    'PATTERN_METRICS'
] 