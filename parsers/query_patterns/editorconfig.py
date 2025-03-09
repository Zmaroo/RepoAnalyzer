"""
Query patterns for EditorConfig files with enhanced pattern support.

These patterns target the custom AST produced by our custom editorconfig parser.
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
LANGUAGE = "editorconfig"

@dataclass
class EditorconfigPatternContext(PatternContext):
    """EditorConfig-specific pattern context."""
    section_names: Set[str] = field(default_factory=set)
    property_names: Set[str] = field(default_factory=set)
    glob_patterns: Set[str] = field(default_factory=set)
    has_root: bool = False
    has_sections: bool = False
    has_properties: bool = False
    has_comments: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.section_names)}:{len(self.property_names)}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "section": PatternPerformanceMetrics(),
    "property": PatternPerformanceMetrics(),
    "glob": PatternPerformanceMetrics(),
    "comment": PatternPerformanceMetrics()
}

# Initialize caches
_pattern_cache = UnifiedCache("editorconfig_patterns")
_context_cache = UnifiedCache("editorconfig_contexts")

async def initialize_caches():
    """Initialize pattern caches."""
    await cache_coordinator.register_cache("editorconfig_patterns", _pattern_cache)
    await cache_coordinator.register_cache("editorconfig_contexts", _context_cache)
    
    # Register warmup functions
    analytics = await get_cache_analytics()
    analytics.register_warmup_function(
        "editorconfig_patterns",
        _warmup_pattern_cache
    )
    analytics.register_warmup_function(
        "editorconfig_contexts",
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
            context = EditorconfigPatternContext()
            results[key] = context.__dict__
        except Exception as e:
            await log(f"Error warming up context cache for {key}: {e}", level="warning")
    return results

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "glob": match.group(1).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "confidence": 0.95
    }

def extract_property(match: Match) -> Dict[str, Any]:
    """Extract property information."""
    return {
        "type": "property",
        "key": match.group(1).strip(),
        "value": match.group(2).strip(),
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "confidence": 0.95
    }

EDITORCONFIG_PATTERNS = {
    PatternCategory.SYNTAX: {
        "section": QueryPattern(
            pattern=r'^\[(.*)\]$',
            extract=extract_section,
            description="Matches EditorConfig section headers",
            examples=["[*.py]", "[*.{js,py}]"]
        ),
        "property": QueryPattern(
            pattern=r'^([^=]+)=(.*)$',
            extract=extract_property,
            description="Matches EditorConfig property assignments",
            examples=["indent_size = 4", "end_of_line = lf"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "root": QueryPattern(
            pattern=r'^root\s*=\s*(true|false)$',
            extract=lambda m: {
                "type": "root",
                "value": m.group(1).lower() == "true",
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig root declaration",
            examples=["root = true"]
        ),
        "glob_pattern": QueryPattern(
            pattern=r'^\[([^\]]+)\]$',
            extract=lambda m: {
                "type": "glob_pattern",
                "pattern": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches glob patterns in section headers",
            examples=["[*.{js,py}]", "[lib/**.js]"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": QueryPattern(
            pattern=r'^[#;](.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig comments",
            examples=["# This is a comment", "; Another comment"]
        ),
        "section_comment": QueryPattern(
            pattern=r'^[#;]\s*Section:\s*(.*)$',
            extract=lambda m: {
                "type": "section_comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches section documentation",
            examples=["# Section: JavaScript files"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "indent": QueryPattern(
            pattern=r'^indent_(style|size)\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "indent",
                "property": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig indentation settings",
            examples=["indent_style = space", "indent_size = 2"]
        ),
        "charset": QueryPattern(
            pattern=r'^charset\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "charset",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches EditorConfig charset settings",
            examples=["charset = utf-8"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "file_type_pattern": QueryPattern(
            pattern=r'^\[.*\.([\w,{}]+)\]$',
            extract=lambda m: {
                "type": "file_type_pattern",
                "extensions": m.group(1).split(','),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches file type patterns",
            examples=["[*.{js,ts}]", "[*.py]"]
        ),
        "code_style": QueryPattern(
            pattern=r'^(max_line_length|tab_width|quote_type)\s*=\s*(.+)$',
            extract=lambda m: {
                "type": "code_style",
                "property": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches code style settings",
            examples=["max_line_length = 80", "quote_type = single"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "include_pattern": QueryPattern(
            pattern=r'^\[.*/?([\w-]+/)*\*\*?/.*\]$',
            extract=lambda m: {
                "type": "include_pattern",
                "path": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches dependency inclusion patterns",
            examples=["[lib/**.js]", "[vendor/**/*.ts]"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "whitespace": QueryPattern(
            pattern=r'^(trim_trailing_whitespace|insert_final_newline)\s*=\s*(true|false)$',
            extract=lambda m: {
                "type": "whitespace",
                "property": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches whitespace best practices",
            examples=["trim_trailing_whitespace = true"]
        ),
        "end_of_line": QueryPattern(
            pattern=r'^end_of_line\s*=\s*(lf|crlf|cr)$',
            extract=lambda m: {
                "type": "end_of_line",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches line ending settings",
            examples=["end_of_line = lf"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "invalid_value": QueryPattern(
            pattern=r'^([^=]+)=\s*(.*?)\s*$',
            extract=lambda m: {
                "type": "invalid_value",
                "key": m.group(1).strip(),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects potentially invalid values",
            examples=["indent_size = invalid"]
        ),
        "duplicate_section": QueryPattern(
            pattern=r'^\[(.*)\]$',
            extract=lambda m: {
                "type": "duplicate_section",
                "glob": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Detects duplicate section headers",
            examples=["[*.py]", "[*.py]"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_property": QueryPattern(
            pattern=r'^([a-z][a-z0-9_]*)\s*=\s*(.*)$',
            extract=lambda m: {
                "type": "custom_property",
                "key": m.group(1),
                "value": m.group(2).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom EditorConfig properties",
            examples=["my_setting = value"]
        )
    }
}

# Add repository learning patterns
EDITORCONFIG_PATTERNS[PatternCategory.LEARNING] = {
    "configuration_patterns": QueryPattern(
        pattern=r'(?s)\[\*\].*?indent_style\s*=\s*(tab|space).*?indent_size\s*=\s*(\d+)',
        extract=lambda m: {
            "type": "indentation_config",
            "indent_style": m.group(1),
            "indent_size": m.group(2),
            "complete_config": True,
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches complete indentation configuration",
        examples=["[*]\nindent_style = space\nindent_size = 2"]
    ),
    "language_specific_patterns": QueryPattern(
        pattern=r'(?s)\[\*\.(?:py|js|jsx|ts|tsx|html|css|htm)\](.*?)(?=\[|$)',
        extract=lambda m: {
            "type": "language_config_pattern",
            "language": m.group(0).split('.')[1].split(']')[0],
            "content": m.group(1),
            "has_language_config": True,
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches language-specific configuration",
        examples=["[*.py]\nindent_size = 4"]
    ),
    "best_practices_patterns": QueryPattern(
        pattern=r'(?s)\[(.*?)\].*?(end_of_line|trim_trailing_whitespace|insert_final_newline)\s*=\s*(.*?)(?=\n|$)',
        extract=lambda m: {
            "type": "best_practice_pattern",
            "glob": m.group(1),
            "property": m.group(2),
            "value": m.group(3),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches best practice configurations",
        examples=["[*]\nend_of_line = lf"]
    )
}

# Convert existing patterns to enhanced types
def create_enhanced_pattern(pattern_def: Dict[str, Any]) -> Union[AdaptivePattern, ResilientPattern]:
    """Create enhanced pattern from definition."""
    base_pattern = pattern_def.copy()
    
    # Determine if pattern should be resilient based on importance
    is_resilient = base_pattern.get("type") in {
        "section", "property", "root", "glob_pattern"
    }
    
    pattern_class = ResilientPattern if is_resilient else AdaptivePattern
    return pattern_class(**base_pattern)

# Convert EDITORCONFIG_PATTERNS to ENHANCED_PATTERNS
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
    for category, patterns in EDITORCONFIG_PATTERNS.items()
}

# Initialize pattern learner with error handling
pattern_learner = CrossProjectPatternLearner()

@handle_async_errors(error_types=ProcessingError)
@cached_in_request
async def extract_editorconfig_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from EditorConfig content for repository learning."""
    patterns = []
    context = EditorconfigPatternContext()
    
    try:
        async with AsyncErrorBoundary(
            "editorconfig_pattern_extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            # Update health status
            await global_health_monitor.update_component_status(
                "editorconfig_pattern_processor",
                ComponentStatus.PROCESSING,
                details={"operation": "pattern_extraction"}
            )
            
            # Process patterns with monitoring
            with monitor_operation("extract_patterns", "editorconfig_processor"):
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
                                    if match["type"] == "section":
                                        context.section_names.add(match.get("glob", ""))
                                        context.has_sections = True
                                    elif match["type"] == "property":
                                        context.property_names.add(match.get("key", ""))
                                        context.has_properties = True
                                    elif match["type"] == "glob_pattern":
                                        context.glob_patterns.add(match.get("pattern", ""))
                                    elif match["type"] == "root":
                                        context.has_root = True
                                    elif match["type"] == "comment":
                                        context.has_comments = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
            
            # Update final status
            await global_health_monitor.update_component_status(
                "editorconfig_pattern_processor",
                ComponentStatus.HEALTHY,
                details={
                    "operation": "pattern_extraction_complete",
                    "patterns_found": len(patterns),
                    "context": {
                        "section_names": len(context.section_names),
                        "property_names": len(context.property_names),
                        "glob_patterns": len(context.glob_patterns),
                        "has_root": context.has_root,
                        "has_comments": context.has_comments
                    }
                }
            )
    
    except Exception as e:
        await log(f"Error extracting EditorConfig patterns: {e}", level="error")
        await global_health_monitor.update_component_status(
            "editorconfig_pattern_processor",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"error": str(e)}
        )
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "section": {
        PatternRelationType.CONTAINS: ["property", "comment"],
        PatternRelationType.DEPENDS_ON: ["root"]
    },
    "property": {
        PatternRelationType.CONTAINS: [],
        PatternRelationType.DEPENDS_ON: ["section"]
    },
    "root": {
        PatternRelationType.CONTAINS: [],
        PatternRelationType.DEPENDS_ON: []
    },
    "glob_pattern": {
        PatternRelationType.CONTAINS: [],
        PatternRelationType.DEPENDS_ON: ["section"]
    },
    "comment": {
        PatternRelationType.CONTAINS: [],
        PatternRelationType.DEPENDS_ON: ["section", "property"]
    }
}

# Export public interfaces
__all__ = [
    'ENHANCED_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_editorconfig_patterns_for_learning',
    'EditorconfigPatternContext',
    'pattern_learner',
    'initialize_caches',
    'PATTERN_METRICS'
] 