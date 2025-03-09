"""Query patterns for AsciiDoc files with enhanced pattern support."""

from typing import Dict, Any, List, Match, Optional, Set, Union
from dataclasses import dataclass, field
from parsers.types import (
    FileType, QueryPattern, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
import re
from parsers.utils import handle_async_errors, cached_in_request
from parsers.health import global_health_monitor, ComponentStatus
from parsers.monitoring import monitor_operation
from parsers.errors import ProcessingError
from parsers.utils import AsyncErrorBoundary

# Language identifier
LANGUAGE = "asciidoc"

@dataclass
class AsciiDocPatternContext(PatternContext):
    """AsciiDoc-specific pattern context."""
    header_levels: Set[int] = field(default_factory=set)
    block_types: Set[str] = field(default_factory=set)
    attribute_names: Set[str] = field(default_factory=set)
    macro_types: Set[str] = field(default_factory=set)
    has_header: bool = False
    has_sections: bool = False
    has_blocks: bool = False
    has_attributes: bool = False
    has_macros: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.header_levels)}:{len(self.block_types)}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "header": PatternPerformanceMetrics(),
    "block": PatternPerformanceMetrics(),
    "list": PatternPerformanceMetrics(),
    "attribute": PatternPerformanceMetrics()
}

# Initialize caches
_pattern_cache = UnifiedCache("asciidoc_patterns")
_context_cache = UnifiedCache("asciidoc_contexts")

async def initialize_caches():
    """Initialize pattern caches."""
    await cache_coordinator.register_cache("asciidoc_patterns", _pattern_cache)
    await cache_coordinator.register_cache("asciidoc_contexts", _context_cache)
    
    # Register warmup functions
    analytics = await get_cache_analytics()
    analytics.register_warmup_function(
        "asciidoc_patterns",
        _warmup_pattern_cache
    )
    analytics.register_warmup_function(
        "asciidoc_contexts",
        _warmup_context_cache
    )

async def _warmup_pattern_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for pattern cache."""
    results = {}
    for key in keys:
        try:
            patterns = ASCIIDOC_PATTERNS.get(PatternCategory.SYNTAX, {})
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
            context = AsciiDocPatternContext()
            results[key] = context.__dict__
        except Exception as e:
            await log(f"Error warming up context cache for {key}: {e}", level="warning")
    return results

# Update existing patterns to use enhanced types
def create_enhanced_pattern(pattern_def: Dict[str, Any]) -> Union[AdaptivePattern, ResilientPattern]:
    """Create enhanced pattern from definition."""
    base_pattern = pattern_def.copy()
    
    # Determine if pattern should be resilient based on importance
    is_resilient = base_pattern.get("type") in {
        "header", "section", "block", "list", "attribute"
    }
    
    pattern_class = ResilientPattern if is_resilient else AdaptivePattern
    return pattern_class(**base_pattern)

# Convert existing patterns to enhanced types
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
    for category, patterns in ASCIIDOC_PATTERNS.items()
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

def extract_header(match: Match) -> Dict[str, Any]:
    """Extract header information."""
    return {
        "type": "header",
        "title": match.group(1),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_section(match: Match) -> Dict[str, Any]:
    """Extract section information."""
    return {
        "type": "section",
        "level": len(match.group(1)),
        "title": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_attribute(match: Match) -> Dict[str, Any]:
    """Extract attribute information."""
    return {
        "type": "attribute",
        "name": match.group(1),
        "value": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

ASCIIDOC_PATTERNS = {
    PatternCategory.SYNTAX: {
        "header": QueryPattern(
            pattern=r'^=\s+(.+)$',
            extract=extract_header,
            description="Matches AsciiDoc document headers",
            examples=["= Document Title"]
        ),
        "section": QueryPattern(
            pattern=r'^(=+)\s+(.+)$',
            extract=extract_section,
            description="Matches AsciiDoc section headers",
            examples=["== Section Title", "=== Subsection Title"]
        ),
        "attribute": QueryPattern(
            pattern=r'^:([^:]+):\s*(.*)$',
            extract=extract_attribute,
            description="Matches AsciiDoc attributes",
            examples=[":attribute-name: value"]
        ),
        "block": QueryPattern(
            pattern=r'^(----|\[.*?\])\s*$',
            extract=lambda m: {
                "type": "block",
                "delimiter": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc blocks",
            examples=["----", "[source,python]"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "include": QueryPattern(
            pattern=r'^include::([^[\]]+)(?:\[(.*?)\])?$',
            extract=lambda m: {
                "type": "include",
                "path": m.group(1),
                "options": m.group(2) if m.group(2) else {},
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc include directives",
            examples=["include::file.adoc[]"]
        ),
        "anchor": QueryPattern(
            pattern=r'^\[\[([^\]]+)\]\]$',
            extract=lambda m: {
                "type": "anchor",
                "id": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc anchors",
            examples=["[[anchor-id]]"]
        ),
        "list": QueryPattern(
            pattern=r'^(\s*)(?:\*|\d+\.|[a-zA-Z]\.|\[.*?\])\s+(.+)$',
            extract=lambda m: {
                "type": "list",
                "indent": len(m.group(1)),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc lists",
            examples=["* Item", "1. Item", "[square] Item"]
        ),
        "table": QueryPattern(
            pattern=r'\|===\n(.*?)\n\|===',
            extract=lambda m: {
                "type": "table",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9,
                "metadata": {
                    "has_header": bool(re.search(r'\[%header\]', m.group(0)))
                }
            },
            description="Matches table structures",
            examples=["|===\n|Header 1|Header 2\n|Cell 1|Cell 2\n|==="]
        ),
        "sidebar": QueryPattern(
            pattern=r'^\[sidebar\]\n====\n(.*?)\n====',
            extract=lambda m: {
                "type": "sidebar",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            description="Matches sidebar blocks",
            examples=["[sidebar]\n====\nSidebar content\n===="]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "admonition": QueryPattern(
            pattern=r'^(NOTE|TIP|IMPORTANT|WARNING|CAUTION):\s+(.+)$',
            extract=lambda m: {
                "type": "admonition",
                "admonition_type": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95,
                "metadata": {
                    "severity": "high" if m.group(1) in ["WARNING", "CAUTION"] else "normal"
                }
            },
            description="Matches admonition blocks",
            examples=["NOTE: Important information", "WARNING: Critical warning"]
        ),
        "comment": QueryPattern(
            pattern=r'^//\s*(.*)$',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc comments",
            examples=["// This is a comment"]
        ),
        "metadata": QueryPattern(
            pattern=r'^:([^:]+)!?:\s*(.*)$',
            extract=lambda m: {
                "type": "metadata",
                "key": m.group(1),
                "value": m.group(2),
                "is_locked": m.group(1).endswith('!'),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc metadata",
            examples=[":author: John Doe", ":version!: 1.0"]
        ),
        "inline_annotation": QueryPattern(
            pattern=r'\[#([^\]]+)\](?:\[([^\]]+)\])?',
            extract=lambda m: {
                "type": "inline_annotation",
                "id": m.group(1),
                "attributes": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            description="Matches inline annotations",
            examples=["[#note-1]", "[#important][role=critical]"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "callout": QueryPattern(
            pattern=r'<(\d+)>',
            extract=lambda m: {
                "type": "callout",
                "number": int(m.group(1)),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc callouts",
            examples=["<1>"]
        ),
        "macro": QueryPattern(
            pattern=r'([a-z]+)::([^[\]]+)(?:\[(.*?)\])?',
            extract=lambda m: {
                "type": "macro",
                "name": m.group(1),
                "target": m.group(2),
                "attributes": m.group(3) if m.group(3) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc macros",
            examples=["image::file.png[]", "link::https://example.com[]"]
        ),
        "inline_markup": QueryPattern(
            pattern=r'(?:\*\*(.+?)\*\*|__(.+?)__|`(.+?)`|\+\+(.+?)\+\+)',
            extract=lambda m: {
                "type": "inline_markup",
                "style": "bold" if m.group(1) else "italic" if m.group(2) else "monospace" if m.group(3) else "passthrough",
                "content": m.group(1) or m.group(2) or m.group(3) or m.group(4),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches AsciiDoc inline markup",
            examples=["**bold**", "__italic__", "`monospace`", "++passthrough++"]
        ),
        "attribute_reference": QueryPattern(
            pattern=r'\{([^}]+)\}',
            extract=lambda m: {
                "type": "attribute_reference",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            description="Matches attribute references",
            examples=["{author}", "{version}"]
        ),
        "macro_definition": QueryPattern(
            pattern=r'^:([^:]+)!?:\s*(.*)$',
            extract=lambda m: {
                "type": "macro_definition",
                "name": m.group(1),
                "value": m.group(2),
                "is_locked": "!" in m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            description="Matches macro definitions",
            examples=[":macro-name: value", ":locked-macro!: value"]
        ),
        "conditional_directive": QueryPattern(
            pattern=r'^ifdef::([^]]+)\[(.*?)endif::.*?\]',
            extract=lambda m: {
                "type": "conditional",
                "condition": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.85
            },
            description="Matches conditional content",
            examples=["ifdef::env-github[GitHub content]endif::[]"]
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "source_block": QueryPattern(
            pattern=r'^\[source,\s*([^\]]+)\]\s*\n----\s*\n(.*?)\n----',
            extract=lambda m: {
                "type": "source_block",
                "language": m.group(1),
                "code": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches source code blocks",
            examples=["[source,python]\n----\nprint('Hello')\n----"]
        ),
        "inline_code": QueryPattern(
            pattern=r'`([^`]+)`',
            extract=lambda m: {
                "type": "inline_code",
                "code": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches inline code",
            examples=["`code`"]
        )
    },
    
    PatternCategory.DEPENDENCIES: {
        "xref": QueryPattern(
            pattern=r'<<([^,>]+)(?:,\s*([^>]+))?>',
            extract=lambda m: {
                "type": "xref",
                "target": m.group(1),
                "text": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches cross-references",
            examples=["<<section>>", "<<section,See section>>"]
        ),
        "include_dependency": QueryPattern(
            pattern=r'^include::([^[\]]+)\[(.*?)\]$',
            extract=lambda m: {
                "type": "include_dependency",
                "path": m.group(1),
                "attributes": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches include dependencies",
            examples=["include::common.adoc[tag=snippet]"]
        ),
        "external_reference": QueryPattern(
            pattern=r'link:([^\[]+)\[(.*?)\]',
            extract=lambda m: {
                "type": "external_reference",
                "url": m.group(1),
                "text": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches external references",
            examples=["link:https://example.com[Example]"]
        ),
        "internal_reference": QueryPattern(
            pattern=r'<<([^,>]+)(?:,\s*([^>]+))?>',
            extract=lambda m: {
                "type": "internal_reference",
                "target": m.group(1),
                "text": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches internal references",
            examples=["<<section>>", "<<section,See section>>"]
        )
    },
    
    PatternCategory.BEST_PRACTICES: {
        "heading_hierarchy": QueryPattern(
            pattern=r'^(=+)\s+(.+)$(?:\n(?!=).*)*(?:\n(=+)\s+(.+)$)?',
            extract=lambda m: {
                "type": "heading_hierarchy",
                "parent_level": len(m.group(1)),
                "parent_title": m.group(2),
                "child_level": len(m.group(3)) if m.group(3) else None,
                "child_title": m.group(4) if m.group(4) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "follows_hierarchy": m.group(3) and len(m.group(3)) <= len(m.group(1)) + 1
            },
            description="Checks heading hierarchy",
            examples=["= Title\n== Section"]
        ),
        "attribute_naming": QueryPattern(
            pattern=r'^:([a-z][a-z0-9-]*?)!?:\s*(.*)$',
            extract=lambda m: {
                "type": "attribute_naming",
                "name": m.group(1),
                "value": m.group(2),
                "follows_convention": bool(re.match(r'^[a-z][a-z0-9-]*$', m.group(1))),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Checks attribute naming conventions",
            examples=[":good-name: value", ":BadName: value"]
        )
    },
    
    PatternCategory.COMMON_ISSUES: {
        "broken_xref": QueryPattern(
            pattern=r'<<([^,>]+)(?:,\s*([^>]+))?>',
            extract=lambda m: {
                "type": "broken_xref",
                "target": m.group(1),
                "text": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            description="Detects potentially broken cross-references",
            examples=["<<missing-section>>"]
        ),
        "inconsistent_attributes": QueryPattern(
            pattern=r'^:([^:]+)!?:\s*(.*)$\n(?:.*\n)*?^:\1!?:\s*(.*)$',
            extract=lambda m: {
                "type": "inconsistent_attributes",
                "name": m.group(1),
                "first_value": m.group(2),
                "second_value": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "is_inconsistent": m.group(2) != m.group(3)
            },
            description="Detects inconsistent attribute definitions",
            examples=[":attr: value1\n:attr: value2"]
        ),
        "broken_include": QueryPattern(
            pattern=r'include::([^[\]]+)(?:\[(.*?)\])?$',
            extract=lambda m: {
                "type": "broken_include",
                "path": m.group(1),
                "options": m.group(2) if m.group(2) else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True,
                "confidence": 0.8
            },
            description="Detects potentially broken includes",
            examples=["include::missing-file.adoc[]"]
        ),
        "malformed_attribute": QueryPattern(
            pattern=r':([^:]*?):(?!\s)',
            extract=lambda m: {
                "type": "malformed_attribute",
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9,
                "error_type": "missing_space"
            },
            description="Detects malformed attributes",
            examples=[":attribute:value"]
        )
    },
    
    PatternCategory.USER_PATTERNS: {
        "custom_block": QueryPattern(
            pattern=r'^\[([^\]]+)\]\s*\n====\s*\n(.*?)\n====',
            extract=lambda m: {
                "type": "custom_block",
                "role": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom block types",
            examples=["[custom]\n====\nContent\n===="]
        ),
        "custom_macro": QueryPattern(
            pattern=r'(\w+):([^[\]]+)\[(.*?)\]',
            extract=lambda m: {
                "type": "custom_macro",
                "name": m.group(1),
                "target": m.group(2),
                "attributes": m.group(3),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches custom macro definitions",
            examples=["custom:target[attrs]"]
        )
    }
}

# Add the repository learning patterns
ASCIIDOC_PATTERNS[PatternCategory.LEARNING] = {
    "document_structure": QueryPattern(
        pattern=r'(?s)^=\s+([^\n]+)\n\n(.*?)(?=\n=\s|$)',
        extract=lambda m: {
            "type": "document_structure",
            "title": m.group(1),
            "content": m.group(2),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Matches document structure patterns",
        examples=["= Title\n\nContent"]
    ),
    "section_patterns": QueryPattern(
        pattern=r'(?s)(=+)\s+([^\n]+)\n\n(.*?)(?=\n=|$)',
        extract=lambda m: {
            "type": "section_pattern",
            "level": len(m.group(1)),
            "title": m.group(2),
            "content": m.group(3),
            "line_number": m.string.count('\n', 0, m.start()) + 1
        },
        description="Learns section organization patterns",
        examples=["== Section\n\nContent"]
    ),
    "pattern_evolution": QueryPattern(
        pattern=r'(?s)(=+)\s+([^\n]+)\n\n(.*?)(?=\n=|$)',
        extract=lambda m: {
            "type": "pattern_evolution",
            "level": len(m.group(1)),
            "title": m.group(2),
            "content": m.group(3),
            "line_number": m.string.count('\n', 0, m.start()) + 1,
            "adaptable": True,
            "context_aware": True
        },
        description="Learns evolving document patterns",
        examples=["= Title\n\nContent that evolves"]
    ),
    "style_patterns": QueryPattern(
        pattern=r'(?s)^((?:[-=*_]{3,}|\+\+\+)\n.*?\n\1)$',
        extract=lambda m: {
            "type": "style_pattern",
            "content": m.group(1),
            "line_number": m.string.count('\n', 0, m.start()) + 1,
            "style_type": "block",
            "adaptable": True
        },
        description="Learns document styling patterns",
        examples=["===\nStyled content\n==="]
    )
}

@handle_async_errors(error_types=ProcessingError)
@cached_in_request
async def extract_asciidoc_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from AsciiDoc content for repository learning."""
    patterns = []
    context = AsciiDocPatternContext()
    
    try:
        async with AsyncErrorBoundary(
            "asciidoc_pattern_extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            # Update health status
            await global_health_monitor.update_component_status(
                "asciidoc_pattern_processor",
                ComponentStatus.PROCESSING,
                details={"operation": "pattern_extraction"}
            )
            
            # Process patterns with monitoring
            with monitor_operation("extract_patterns", "asciidoc_processor"):
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
                                        context.header_levels.add(match.get("level", 1))
                                        context.has_header = True
                                    elif match["type"] == "section":
                                        context.has_sections = True
                                    elif match["type"] == "block":
                                        context.block_types.add(match.get("block_type", "unknown"))
                                        context.has_blocks = True
                                    elif match["type"] == "attribute":
                                        context.attribute_names.add(match.get("name", ""))
                                        context.has_attributes = True
                                    elif match["type"] == "macro":
                                        context.macro_types.add(match.get("name", ""))
                                        context.has_macros = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
            
            # Update final status
            await global_health_monitor.update_component_status(
                "asciidoc_pattern_processor",
                ComponentStatus.HEALTHY,
                details={
                    "operation": "pattern_extraction_complete",
                    "patterns_found": len(patterns),
                    "context": {
                        "header_levels": len(context.header_levels),
                        "block_types": len(context.block_types),
                        "attribute_names": len(context.attribute_names),
                        "macro_types": len(context.macro_types)
                    }
                }
            )
    
    except Exception as e:
        await log(f"Error extracting asciidoc patterns: {e}", level="error")
        await global_health_monitor.update_component_status(
            "asciidoc_pattern_processor",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"error": str(e)}
        )
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "document": {
        "can_contain": ["header", "section", "block", "list"],
        "can_be_contained_by": []
    },
    "section": {
        "can_contain": ["section", "block", "list", "paragraph"],
        "can_be_contained_by": ["document", "section"]
    },
    "block": {
        "can_contain": ["source", "listing", "quote", "example"],
        "can_be_contained_by": ["document", "section"]
    },
    "list": {
        "can_contain": ["list_item"],
        "can_be_contained_by": ["document", "section", "list_item"]
    },
    "custom_block": {
        "can_contain": ["block", "list", "paragraph"],
        "can_be_contained_by": ["document", "section"]
    },
    "admonition": {
        "can_contain": ["paragraph", "list", "block"],
        "can_be_contained_by": ["document", "section"]
    },
    "table": {
        "can_contain": ["cell", "header"],
        "can_be_contained_by": ["document", "section", "block"]
    },
    "sidebar": {
        "can_contain": ["paragraph", "list", "block"],
        "can_be_contained_by": ["document", "section"]
    },
    "conditional": {
        "can_contain": ["block", "list", "paragraph"],
        "can_be_contained_by": ["document", "section", "block"]
    }
}

def extract_asciidoc_features(ast: dict) -> dict:
    """Extract features that align with pattern categories."""
    features = {
        "syntax": {
            "headers": [],
            "sections": [],
            "blocks": []
        },
        "structure": {
            "includes": [],
            "anchors": [],
            "lists": []
        },
        "semantics": {
            "callouts": [],
            "macros": [],
            "inline_markup": []
        },
        "documentation": {
            "admonitions": [],
            "comments": [],
            "metadata": {}
        }
    }
    return features 

# Add pattern validation rules
PATTERN_VALIDATION_RULES = {
    "attribute_naming": {
        "pattern": r'^[a-z][a-z0-9-]*$',
        "message": "Attribute names should be lowercase with hyphens"
    },
    "heading_hierarchy": {
        "max_depth": 6,
        "message": "Heading levels should not exceed 6 levels deep"
    },
    "block_nesting": {
        "max_depth": 4,
        "message": "Block nesting should not exceed 4 levels"
    },
    "list_nesting": {
        "max_depth": 3,
        "message": "List nesting should not exceed 3 levels"
    }
} 