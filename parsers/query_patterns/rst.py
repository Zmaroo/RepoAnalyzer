"""Query patterns for reStructuredText files.

This module provides reStructuredText-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.logger import log

# Language identifier
LANGUAGE = "rst"

@dataclass
class RSTPatternContext(PatternContext):
    """reStructuredText-specific pattern context."""
    section_names: Set[str] = field(default_factory=set)
    directive_names: Set[str] = field(default_factory=set)
    role_names: Set[str] = field(default_factory=set)
    reference_names: Set[str] = field(default_factory=set)
    has_sections: bool = False
    has_directives: bool = False
    has_roles: bool = False
    has_references: bool = False
    has_substitutions: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.section_names)}:{self.has_directives}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "section": PatternPerformanceMetrics(),
    "directive": PatternPerformanceMetrics(),
    "role": PatternPerformanceMetrics(),
    "reference": PatternPerformanceMetrics(),
    "list": PatternPerformanceMetrics()
}

RST_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "section": ResilientPattern(
                pattern="""
                [
                    (section
                        title: (_) @syntax.section.title
                        underline: (_) @syntax.section.underline
                        content: (_)* @syntax.section.content) @syntax.section.def,
                    (subsection
                        title: (_) @syntax.subsection.title
                        underline: (_) @syntax.subsection.underline
                        content: (_)* @syntax.subsection.content) @syntax.subsection.def
                ]
                """,
                extract=lambda node: {
                    "type": "section",
                    "title": (
                        node["captures"].get("syntax.section.title", {}).get("text", "") or
                        node["captures"].get("syntax.subsection.title", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.section.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.subsection.def", {}).get("start_point", [0])[0]
                    ),
                    "is_subsection": "syntax.subsection.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["section", "directive", "list"],
                        PatternRelationType.DEPENDS_ON: ["section"]
                    }
                },
                name="section",
                description="Matches reStructuredText section declarations",
                examples=["Title\n=====", "Section\n-------"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["section"],
                    "validation": {
                        "required_fields": ["title"],
                        "name_format": r'^[^\n]+$'
                    }
                }
            ),
            "directive": ResilientPattern(
                pattern="""
                [
                    (directive
                        name: (_) @syntax.directive.name
                        options: (directive_options)? @syntax.directive.options
                        content: (_)* @syntax.directive.content) @syntax.directive.def,
                    (role
                        name: (_) @syntax.role.name
                        content: (_) @syntax.role.content) @syntax.role.def
                ]
                """,
                extract=lambda node: {
                    "type": "directive",
                    "name": (
                        node["captures"].get("syntax.directive.name", {}).get("text", "") or
                        node["captures"].get("syntax.role.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.directive.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.role.def", {}).get("start_point", [0])[0]
                    ),
                    "is_role": "syntax.role.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["section"],
                        PatternRelationType.DEPENDS_ON: ["directive"]
                    }
                },
                name="directive",
                description="Matches reStructuredText directives and roles",
                examples=[".. note::", ":ref:`link`"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["directive"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-z0-9_-]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.REFERENCES: {
            "reference": AdaptivePattern(
                pattern="""
                [
                    (reference
                        name: (_) @ref.name
                        target: (_) @ref.target) @ref.def,
                    (substitution
                        name: (_) @ref.sub.name
                        value: (_) @ref.sub.value) @ref.sub.def,
                    (footnote
                        label: (_) @ref.footnote.label
                        content: (_) @ref.footnote.content) @ref.footnote.def
                ]
                """,
                extract=lambda node: {
                    "type": "reference",
                    "line_number": (
                        node["captures"].get("ref.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("ref.sub.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("ref.footnote.def", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("ref.name", {}).get("text", "") or
                        node["captures"].get("ref.sub.name", {}).get("text", "") or
                        node["captures"].get("ref.footnote.label", {}).get("text", "")
                    ),
                    "reference_type": (
                        "reference" if "ref.def" in node["captures"] else
                        "substitution" if "ref.sub.def" in node["captures"] else
                        "footnote" if "ref.footnote.def" in node["captures"] else
                        "unknown"
                    ),
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["section", "directive"],
                        PatternRelationType.DEPENDS_ON: ["reference"]
                    }
                },
                name="reference",
                description="Matches reStructuredText references",
                examples=["`link`_", "|substitution|", "[1]_"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REFERENCES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["reference"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_-]+$'
                    }
                }
            ),
            "list": AdaptivePattern(
                pattern="""
                [
                    (bullet_list
                        items: (list_item
                            content: (_) @list.bullet.content)* @list.bullet.items) @list.bullet.def,
                    (enumerated_list
                        items: (list_item
                            content: (_) @list.enum.content)* @list.enum.items) @list.enum.def,
                    (definition_list
                        items: (definition_item
                            term: (_) @list.def.term
                            definition: (_) @list.def.content)* @list.def.items) @list.def.def
                ]
                """,
                extract=lambda node: {
                    "type": "list",
                    "line_number": (
                        node["captures"].get("list.bullet.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("list.enum.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("list.def.def", {}).get("start_point", [0])[0]
                    ),
                    "list_type": (
                        "bullet" if "list.bullet.def" in node["captures"] else
                        "enumerated" if "list.enum.def" in node["captures"] else
                        "definition" if "list.def.def" in node["captures"] else
                        "unknown"
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["section", "directive"],
                        PatternRelationType.CONTAINS: ["list_item"]
                    }
                },
                name="list",
                description="Matches reStructuredText lists",
                examples=["* Item", "1. Item", "term\n  Definition"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REFERENCES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["list"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_rst_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from reStructuredText content for repository learning."""
    patterns = []
    context = RSTPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in RST_PATTERNS:
                category_patterns = RST_PATTERNS[category]
                for purpose in category_patterns:
                    for pattern_name, pattern in category_patterns[purpose].items():
                        if isinstance(pattern, (ResilientPattern, AdaptivePattern)):
                            try:
                                matches = await pattern.matches(content, context)
                                for match in matches:
                                    patterns.append({
                                        "name": pattern_name,
                                        "category": category.value,
                                        "purpose": purpose.value,
                                        "content": match.get("text", ""),
                                        "metadata": match,
                                        "confidence": pattern.confidence,
                                        "relationships": match.get("relationships", {})
                                    })
                                    
                                    # Update context
                                    if match["type"] == "section":
                                        context.has_sections = True
                                        context.section_names.add(match["title"])
                                    elif match["type"] == "directive":
                                        if match["is_role"]:
                                            context.has_roles = True
                                            context.role_names.add(match["name"])
                                        else:
                                            context.has_directives = True
                                            context.directive_names.add(match["name"])
                                    elif match["type"] == "reference":
                                        context.has_references = True
                                        context.reference_names.add(match["name"])
                                        if match["reference_type"] == "substitution":
                                            context.has_substitutions = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting reStructuredText patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "section": {
        PatternRelationType.CONTAINS: ["section", "directive", "list"],
        PatternRelationType.DEPENDS_ON: ["section"]
    },
    "directive": {
        PatternRelationType.CONTAINED_BY: ["section"],
        PatternRelationType.DEPENDS_ON: ["directive"]
    },
    "reference": {
        PatternRelationType.REFERENCED_BY: ["section", "directive"],
        PatternRelationType.DEPENDS_ON: ["reference"]
    },
    "list": {
        PatternRelationType.CONTAINED_BY: ["section", "directive"],
        PatternRelationType.CONTAINS: ["list_item"]
    }
}

# Export public interfaces
__all__ = [
    'RST_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_rst_patterns_for_learning',
    'RSTPatternContext',
    'pattern_learner'
] 