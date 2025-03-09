"""Query patterns for YAML files.

This module provides YAML-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "yaml"

@dataclass
class YAMLPatternContext(PatternContext):
    """YAML-specific pattern context."""
    key_names: Set[str] = field(default_factory=set)
    anchor_names: Set[str] = field(default_factory=set)
    tag_names: Set[str] = field(default_factory=set)
    has_anchors: bool = False
    has_aliases: bool = False
    has_tags: bool = False
    has_sequences: bool = False
    has_mappings: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.key_names)}:{self.has_anchors}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "mapping": PatternPerformanceMetrics(),
    "sequence": PatternPerformanceMetrics(),
    "anchor": PatternPerformanceMetrics(),
    "tag": PatternPerformanceMetrics(),
    "scalar": PatternPerformanceMetrics()
}

YAML_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "mapping": ResilientPattern(
                pattern="""
                [
                    (block_mapping_pair
                        key: (_) @syntax.map.key
                        value: (_) @syntax.map.value) @syntax.map.pair,
                    (flow_mapping
                        (flow_pair
                            key: (_) @syntax.flow.map.key
                            value: (_) @syntax.flow.map.value) @syntax.flow.map.pair) @syntax.flow.map
                ]
                """,
                extract=lambda node: {
                    "type": "mapping",
                    "line_number": (
                        node["captures"].get("syntax.map.pair", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.flow.map", {}).get("start_point", [0])[0]
                    ),
                    "key": (
                        node["captures"].get("syntax.map.key", {}).get("text", "") or
                        node["captures"].get("syntax.flow.map.key", {}).get("text", "")
                    ),
                    "is_flow": "syntax.flow.map" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["scalar", "sequence", "mapping"],
                        PatternRelationType.DEPENDS_ON: ["anchor", "tag"]
                    }
                },
                name="mapping",
                description="Matches YAML mapping patterns",
                examples=["key: value", "{ key: value }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["mapping"],
                    "validation": {
                        "required_fields": ["key"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
                    }
                }
            ),
            "sequence": ResilientPattern(
                pattern="""
                [
                    (block_sequence
                        (block_sequence_item
                            (_) @syntax.seq.item) @syntax.seq.entry) @syntax.seq,
                    (flow_sequence
                        (_)* @syntax.flow.seq.item) @syntax.flow.seq
                ]
                """,
                extract=lambda node: {
                    "type": "sequence",
                    "line_number": (
                        node["captures"].get("syntax.seq", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.flow.seq", {}).get("start_point", [0])[0]
                    ),
                    "is_flow": "syntax.flow.seq" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["scalar", "sequence", "mapping"],
                        PatternRelationType.DEPENDS_ON: ["anchor", "tag"]
                    }
                },
                name="sequence",
                description="Matches YAML sequence patterns",
                examples=["- item1\n- item2", "[item1, item2]"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["sequence"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.ANCHORS: {
            "anchor": AdaptivePattern(
                pattern="""
                [
                    (anchor
                        name: (_) @anchor.name) @anchor.def,
                    (alias
                        name: (_) @alias.name) @alias.def
                ]
                """,
                extract=lambda node: {
                    "type": "anchor",
                    "name": (
                        node["captures"].get("anchor.name", {}).get("text", "") or
                        node["captures"].get("alias.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("anchor.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("alias.def", {}).get("start_point", [0])[0]
                    ),
                    "is_alias": "alias.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["mapping", "sequence", "scalar"],
                        PatternRelationType.DEPENDS_ON: ["anchor"]
                    }
                },
                name="anchor",
                description="Matches YAML anchor and alias patterns",
                examples=["&anchor value", "*alias"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.ANCHORS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["anchor"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
                    }
                }
            )
        },
        PatternPurpose.TAGS: {
            "tag": AdaptivePattern(
                pattern="""
                [
                    (tag
                        name: (_) @tag.name) @tag.def,
                    (verbatim_tag
                        name: (_) @tag.verbatim.name) @tag.verbatim.def
                ]
                """,
                extract=lambda node: {
                    "type": "tag",
                    "name": (
                        node["captures"].get("tag.name", {}).get("text", "") or
                        node["captures"].get("tag.verbatim.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("tag.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("tag.verbatim.def", {}).get("start_point", [0])[0]
                    ),
                    "is_verbatim": "tag.verbatim.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.APPLIES_TO: ["mapping", "sequence", "scalar"],
                        PatternRelationType.DEPENDS_ON: ["tag"]
                    }
                },
                name="tag",
                description="Matches YAML tag patterns",
                examples=["!!str value", "!<tag> value"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.TAGS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["tag"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[!][a-zA-Z0-9_-]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_yaml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from YAML content for repository learning."""
    patterns = []
    context = YAMLPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in YAML_PATTERNS:
                category_patterns = YAML_PATTERNS[category]
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
                                    if match["type"] == "mapping":
                                        context.key_names.add(match["key"])
                                        context.has_mappings = True
                                    elif match["type"] == "sequence":
                                        context.has_sequences = True
                                    elif match["type"] == "anchor":
                                        if match["is_alias"]:
                                            context.has_aliases = True
                                        else:
                                            context.anchor_names.add(match["name"])
                                            context.has_anchors = True
                                    elif match["type"] == "tag":
                                        context.tag_names.add(match["name"])
                                        context.has_tags = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting YAML patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "mapping": {
        PatternRelationType.CONTAINS: ["scalar", "sequence", "mapping"],
        PatternRelationType.DEPENDS_ON: ["anchor", "tag"]
    },
    "sequence": {
        PatternRelationType.CONTAINS: ["scalar", "sequence", "mapping"],
        PatternRelationType.DEPENDS_ON: ["anchor", "tag"]
    },
    "anchor": {
        PatternRelationType.REFERENCED_BY: ["mapping", "sequence", "scalar"],
        PatternRelationType.DEPENDS_ON: ["anchor"]
    },
    "tag": {
        PatternRelationType.APPLIES_TO: ["mapping", "sequence", "scalar"],
        PatternRelationType.DEPENDS_ON: ["tag"]
    }
}

# Export public interfaces
__all__ = [
    'YAML_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_yaml_patterns_for_learning',
    'YAMLPatternContext',
    'pattern_learner'
] 