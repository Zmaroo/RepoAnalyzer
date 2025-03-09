"""Query patterns for TOML files.

This module provides TOML-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "toml"

@dataclass
class TOMLPatternContext(PatternContext):
    """TOML-specific pattern context."""
    table_names: Set[str] = field(default_factory=set)
    key_names: Set[str] = field(default_factory=set)
    array_names: Set[str] = field(default_factory=set)
    has_arrays: bool = False
    has_inline_tables: bool = False
    has_dotted_keys: bool = False
    has_multiline_strings: bool = False
    has_dates: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.table_names)}:{self.has_arrays}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "table": PatternPerformanceMetrics(),
    "key_value": PatternPerformanceMetrics(),
    "array": PatternPerformanceMetrics(),
    "inline_table": PatternPerformanceMetrics(),
    "string": PatternPerformanceMetrics()
}

TOML_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "table": ResilientPattern(
                pattern="""
                [
                    (table
                        name: (_) @syntax.table.name
                        body: (_)* @syntax.table.body) @syntax.table.def,
                    (array_table
                        name: (_) @syntax.array.table.name
                        body: (_)* @syntax.array.table.body) @syntax.array.table.def
                ]
                """,
                extract=lambda node: {
                    "type": "table",
                    "name": (
                        node["captures"].get("syntax.table.name", {}).get("text", "") or
                        node["captures"].get("syntax.array.table.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.table.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.array.table.def", {}).get("start_point", [0])[0]
                    ),
                    "is_array": "syntax.array.table.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["key_value", "array", "inline_table"],
                        PatternRelationType.DEPENDS_ON: ["table"]
                    }
                },
                name="table",
                description="Matches TOML table declarations",
                examples=["[table]", "[[array_table]]"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["table"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_.-]+$'
                    }
                }
            ),
            "key_value": ResilientPattern(
                pattern="""
                [
                    (pair
                        name: (_) @syntax.pair.name
                        value: (_) @syntax.pair.value) @syntax.pair.def,
                    (dotted_key
                        parts: (_)+ @syntax.dotted.parts
                        value: (_) @syntax.dotted.value) @syntax.dotted.def
                ]
                """,
                extract=lambda node: {
                    "type": "key_value",
                    "name": (
                        node["captures"].get("syntax.pair.name", {}).get("text", "") or
                        ".".join(part.get("text", "") for part in node["captures"].get("syntax.dotted.parts", []))
                    ),
                    "line_number": (
                        node["captures"].get("syntax.pair.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.dotted.def", {}).get("start_point", [0])[0]
                    ),
                    "is_dotted": "syntax.dotted.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["table"],
                        PatternRelationType.DEPENDS_ON: ["value"]
                    }
                },
                name="key_value",
                description="Matches TOML key-value pairs",
                examples=["key = value", "server.host = 'localhost'"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["key_value"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_.-]+$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.VALUES: {
            "array": AdaptivePattern(
                pattern="""
                [
                    (array
                        values: (_)* @value.array.items) @value.array.def,
                    (array_table
                        name: (_) @value.array.table.name
                        body: (_)* @value.array.table.body) @value.array.table.def
                ]
                """,
                extract=lambda node: {
                    "type": "array",
                    "line_number": (
                        node["captures"].get("value.array.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("value.array.table.def", {}).get("start_point", [0])[0]
                    ),
                    "is_table": "value.array.table.def" in node["captures"],
                    "table_name": node["captures"].get("value.array.table.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["value"],
                        PatternRelationType.DEPENDS_ON: ["table"]
                    }
                },
                name="array",
                description="Matches TOML array values",
                examples=["values = [1, 2, 3]", "[[products]]"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.VALUES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["array"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            ),
            "inline_table": AdaptivePattern(
                pattern="""
                [
                    (inline_table
                        pairs: (pair
                            name: (_) @value.table.pair.name
                            value: (_) @value.table.pair.value)* @value.table.pairs) @value.table.def
                ]
                """,
                extract=lambda node: {
                    "type": "inline_table",
                    "line_number": node["captures"].get("value.table.def", {}).get("start_point", [0])[0],
                    "pairs": [
                        {
                            "name": name.get("text", ""),
                            "value": value.get("text", "")
                        }
                        for name, value in zip(
                            node["captures"].get("value.table.pair.name", []),
                            node["captures"].get("value.table.pair.value", [])
                        )
                    ],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["key_value"],
                        PatternRelationType.DEPENDS_ON: ["value"]
                    }
                },
                name="inline_table",
                description="Matches TOML inline tables",
                examples=["point = { x = 1, y = 2 }"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.VALUES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["inline_table"],
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

async def extract_toml_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from TOML content for repository learning."""
    patterns = []
    context = TOMLPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in TOML_PATTERNS:
                category_patterns = TOML_PATTERNS[category]
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
                                    if match["type"] == "table":
                                        context.table_names.add(match["name"])
                                        if match["is_array"]:
                                            context.has_arrays = True
                                    elif match["type"] == "key_value":
                                        context.key_names.add(match["name"])
                                        if match["is_dotted"]:
                                            context.has_dotted_keys = True
                                    elif match["type"] == "array":
                                        context.has_arrays = True
                                        if match["is_table"]:
                                            context.array_names.add(match["table_name"])
                                    elif match["type"] == "inline_table":
                                        context.has_inline_tables = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting TOML patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "table": {
        PatternRelationType.CONTAINS: ["key_value", "array", "inline_table"],
        PatternRelationType.DEPENDS_ON: ["table"]
    },
    "key_value": {
        PatternRelationType.CONTAINED_BY: ["table"],
        PatternRelationType.DEPENDS_ON: ["value"]
    },
    "array": {
        PatternRelationType.CONTAINS: ["value"],
        PatternRelationType.DEPENDS_ON: ["table"]
    },
    "inline_table": {
        PatternRelationType.CONTAINS: ["key_value"],
        PatternRelationType.DEPENDS_ON: ["value"]
    }
}

# Export public interfaces
__all__ = [
    'TOML_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_toml_patterns_for_learning',
    'TOMLPatternContext',
    'pattern_learner'
] 