"""Query patterns for the Cobalt programming language with enhanced pattern support."""

from typing import Dict, Any, List, Match, Optional, Set, Union
from dataclasses import dataclass, field
import time
from parsers.types import (
    FileType, QueryPattern, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics
)
from parsers.query_patterns.enhanced_patterns import (
    TreeSitterResilientPattern, TreeSitterAdaptivePattern, TreeSitterCrossProjectPatternLearner
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
LANGUAGE = "cobalt"

@dataclass
class CobaltPatternContext(PatternContext):
    """Cobalt-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    class_names: Set[str] = field(default_factory=set)
    namespace_names: Set[str] = field(default_factory=set)
    type_names: Set[str] = field(default_factory=set)
    has_functions: bool = False
    has_classes: bool = False
    has_namespaces: bool = False
    has_types: bool = False
    has_error_handling: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{len(self.class_names)}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "class": PatternPerformanceMetrics(),
    "namespace": PatternPerformanceMetrics(),
    "type": PatternPerformanceMetrics(),
    "error_handling": PatternPerformanceMetrics()
}

# Initialize caches
_pattern_cache = UnifiedCache("cobalt_patterns")
_context_cache = UnifiedCache("cobalt_contexts")

async def initialize_caches():
    """Initialize pattern caches."""
    await cache_coordinator.register_cache("cobalt_patterns", _pattern_cache)
    await cache_coordinator.register_cache("cobalt_contexts", _context_cache)
    
    # Register warmup functions
    analytics = await get_cache_analytics()
    analytics.register_warmup_function(
        "cobalt_patterns",
        _warmup_pattern_cache
    )
    analytics.register_warmup_function(
        "cobalt_contexts",
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
            context = CobaltPatternContext()
            results[key] = context.__dict__
        except Exception as e:
            await log(f"Error warming up context cache for {key}: {e}", level="warning")
    return results

def extract_function(match: Match) -> Dict[str, Any]:
    """Extract function information."""
    return {
        "type": "function",
        "name": match.group(1),
        "parameters": match.group(2),
        "return_type": match.group(3) if match.lastindex >= 3 else None,
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "confidence": 0.95
    }

def extract_class(match: Match) -> Dict[str, Any]:
    """Extract class information."""
    return {
        "type": "class",
        "name": match.group(1),
        "parent": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "confidence": 0.95
    }

# Define base patterns
COBALT_PATTERNS = {
    PatternCategory.SYNTAX: {
        "function": QueryPattern(
            name="function",
            pattern=r'fn\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)(?:\s*->\s*([a-zA-Z_][a-zA-Z0-9_<>]*))?\s*{',
            extract=extract_function,
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches Cobalt function definitions", "examples": ["fn main()", "fn process(data: String) -> Result"]}
        ),
        "class": QueryPattern(
            name="class",
            pattern=r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::\s*([a-zA-Z_][a-zA-Z0-9_<>]*))?\s*{',
            extract=extract_class,
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches Cobalt class definitions", "examples": ["class MyClass", "class Child: Parent"]}
        ),
        "namespace": QueryPattern(
            name="namespace",
            pattern=r'namespace\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*{',
            extract=lambda m: {
                "type": "namespace",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches Cobalt namespace definitions", "examples": ["namespace MyNamespace"]}
        )
    },
    
    PatternCategory.SEMANTICS: {
        "type_definition": QueryPattern(
            name="type_definition",
            pattern=r'type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=\s*([^;]+))?;',
            extract=lambda m: {
                "type": "type_definition",
                "name": m.group(1),
                "value": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.SEMANTICS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches Cobalt type definitions", "examples": ["type MyType = i32", "type Result = Success | Error"]}
        ),
        "enum": QueryPattern(
            name="enum",
            pattern=r'enum\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*{([^}]*)}',
            extract=lambda m: {
                "type": "enum",
                "name": m.group(1),
                "variants": [v.strip() for v in m.group(2).split(',') if v.strip()],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.SEMANTICS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches Cobalt enum definitions", "examples": ["enum Color { Red, Green, Blue }"]}
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "doc_comment": QueryPattern(
            name="doc_comment",
            pattern=r'///\s*(.+)$',
            extract=lambda m: {
                "type": "doc_comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches Cobalt documentation comments", "examples": ["/// Function documentation"]}
        ),
        "module_doc": QueryPattern(
            name="module_doc",
            pattern=r'//!\s*(.+)$',
            extract=lambda m: {
                "type": "module_doc",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches Cobalt module documentation", "examples": ["//! Module documentation"]}
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "error_handling": QueryPattern(
            name="error_handling",
            pattern=r'try\s*{[^}]*}\s*catch\s*(?:\(([^)]+)\))?\s*{',
            extract=lambda m: {
                "type": "error_handling",
                "error_type": m.group(1) if m.group(1) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches Cobalt error handling", "examples": ["try { ... } catch(Error) { ... }"]}
        ),
        "pattern_matching": QueryPattern(
            name="pattern_matching",
            pattern=r'match\s+([^{]+)\s*{([^}]*)}',
            extract=lambda m: {
                "type": "pattern_matching",
                "value": m.group(1),
                "patterns": [p.strip() for p in m.group(2).split(',') if p.strip()],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Matches Cobalt pattern matching", "examples": ["match value { Some(x) => x, None => 0 }"]}
        )
    }
}

# Convert existing patterns to enhanced types
def create_enhanced_pattern(pattern_def: Dict[str, Any]) -> Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern]:
    """Create enhanced pattern from definition."""
    base_pattern = pattern_def.copy()
    
    # Determine if pattern should be resilient based on importance
    is_resilient = base_pattern.get("type") in {
        "function", "class", "namespace", "type", "enum"
    }
    
    pattern_class = TreeSitterResilientPattern if is_resilient else TreeSitterAdaptivePattern
    return pattern_class(**base_pattern)

# Convert COBALT_PATTERNS to ENHANCED_PATTERNS
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
    for category, patterns in COBALT_PATTERNS.items()
}

# Initialize pattern learner with error handling
pattern_learner = TreeSitterCrossProjectPatternLearner()

@handle_async_errors(error_types=ProcessingError)
@cached_in_request
async def extract_cobalt_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Cobalt content for repository learning."""
    patterns = []
    context = CobaltPatternContext()
    
    try:
        async with AsyncErrorBoundary(
            "cobalt_pattern_extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            # Update health status
            await global_health_monitor.update_component_status(
                "cobalt_pattern_processor",
                ComponentStatus.PROCESSING,
                details={"operation": "pattern_extraction"}
            )
            
            # Process patterns with monitoring
            with monitor_operation("extract_patterns", "cobalt_processor"):
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
                                    if match["type"] == "function":
                                        context.function_names.add(match.get("name", ""))
                                        context.has_functions = True
                                    elif match["type"] == "class":
                                        context.class_names.add(match.get("name", ""))
                                        context.has_classes = True
                                    elif match["type"] == "namespace":
                                        context.namespace_names.add(match.get("name", ""))
                                        context.has_namespaces = True
                                    elif match["type"] == "type":
                                        context.type_names.add(match.get("name", ""))
                                        context.has_types = True
                                    elif match["type"] in ["try_catch", "throw"]:
                                        context.has_error_handling = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
            
            # Update final status
            await global_health_monitor.update_component_status(
                "cobalt_pattern_processor",
                ComponentStatus.HEALTHY,
                details={
                    "operation": "pattern_extraction_complete",
                    "patterns_found": len(patterns),
                    "context": {
                        "function_names": len(context.function_names),
                        "class_names": len(context.class_names),
                        "namespace_names": len(context.namespace_names),
                        "type_names": len(context.type_names),
                        "has_error_handling": context.has_error_handling
                    }
                }
            )
    
    except Exception as e:
        await log(f"Error extracting Cobalt patterns: {e}", level="error")
        await global_health_monitor.update_component_status(
            "cobalt_pattern_processor",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"error": str(e)}
        )
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.USES: ["variable", "comment", "docstring", "try_catch", "throw"],
        PatternRelationType.DEPENDS_ON: ["class", "namespace"]
    },
    "class": {
        PatternRelationType.USES: ["function", "variable", "comment", "docstring", "type"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    },
    "namespace": {
        PatternRelationType.USES: ["class", "function", "variable", "comment", "type"],
        PatternRelationType.DEPENDS_ON: ["namespace"]
    },
    "type": {
        PatternRelationType.USES: [],
        PatternRelationType.DEPENDS_ON: ["class", "namespace"]
    },
    "try_catch": {
        PatternRelationType.USES: ["throw"],
        PatternRelationType.DEPENDS_ON: ["function", "class"]
    },
    "throw": {
        PatternRelationType.USES: [],
        PatternRelationType.DEPENDS_ON: ["try_catch", "function"]
    }
}

# Export public interfaces
__all__ = [
    'ENHANCED_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_cobalt_patterns_for_learning',
    'CobaltPatternContext',
    'pattern_learner',
    'initialize_caches',
    'PATTERN_METRICS'
] 