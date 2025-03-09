"""Query patterns for Markdown files.

This module provides Markdown-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "markdown"

@dataclass
class MarkdownPatternContext(PatternContext):
    """Markdown-specific pattern context."""
    heading_levels: Set[int] = field(default_factory=set)
    link_refs: Set[str] = field(default_factory=set)
    code_langs: Set[str] = field(default_factory=set)
    has_frontmatter: bool = False
    has_math: bool = False
    has_mermaid: bool = False
    nesting_level: int = 0
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.heading_levels)}:{self.nesting_level}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "heading": PatternPerformanceMetrics(),
    "list": PatternPerformanceMetrics(),
    "code": PatternPerformanceMetrics(),
    "link": PatternPerformanceMetrics(),
    "emphasis": PatternPerformanceMetrics()
}

MARKDOWN_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "heading": ResilientPattern(
                pattern=r'^(#{1,6})\s+(.+)$',
                extract=lambda m: {
                    "type": "heading",
                    "level": len(m.group(1)),
                    "content": m.group(2),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINS: ["emphasis", "link"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="heading",
                description="Matches Markdown headers",
                examples=["# Title", "## Section"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["heading"],
                    "validation": {
                        "required_fields": ["level", "content"],
                        "level_range": [1, 6]
                    }
                }
            ),
            "list": ResilientPattern(
                pattern=r'^(\s*)[*+-]\s+(.+)$',
                extract=lambda m: {
                    "type": "list",
                    "indent": len(m.group(1)),
                    "content": m.group(2),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINS: ["list", "emphasis", "link"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="list",
                description="Matches unordered list items",
                examples=["* Item", "- Point"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["list"],
                    "validation": {
                        "required_fields": ["content"]
                    }
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "emphasis": AdaptivePattern(
                pattern=r'(\*\*|__)(.*?)\1|(\*|_)(.*?)\3',
                extract=lambda m: {
                    "type": "emphasis",
                    "style": "strong" if m.group(1) else "emphasis",
                    "content": m.group(2) or m.group(4),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["heading", "list", "paragraph"],
                        PatternRelationType.REFERENCES: []
                    }
                },
                name="emphasis",
                description="Matches text emphasis",
                examples=["**bold**", "_italic_"],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["emphasis"],
                    "validation": {
                        "required_fields": ["content", "style"]
                    }
                }
            ),
            "link": AdaptivePattern(
                pattern=r'\[([^\]]+)\]\(([^)]+)\)',
                extract=lambda m: {
                    "type": "link",
                    "text": m.group(1),
                    "url": m.group(2),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["heading", "list", "paragraph"],
                        PatternRelationType.REFERENCES: ["link_ref"]
                    }
                },
                name="link",
                description="Matches links",
                examples=["[text](url)"],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["link"],
                    "validation": {
                        "required_fields": ["text", "url"]
                    }
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.CODE_BLOCKS: {
            "code_block": AdaptivePattern(
                pattern=r'```(\w*)\n(.*?)```',
                extract=lambda m: {
                    "type": "code_block",
                    "language": m.group(1),
                    "content": m.group(2),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["document"],
                        PatternRelationType.REFERENCES: []
                    }
                },
                name="code_block",
                description="Matches code blocks",
                examples=["```python\nprint('hello')\n```"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.CODE_BLOCKS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["code"],
                    "validation": {
                        "required_fields": ["content"]
                    }
                }
            )
        },
        PatternPurpose.DIAGRAMS: {
            "mermaid": AdaptivePattern(
                pattern=r'```mermaid\n(.*?)```',
                extract=lambda m: {
                    "type": "mermaid",
                    "content": m.group(1),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["document"],
                        PatternRelationType.REFERENCES: []
                    }
                },
                name="mermaid",
                description="Matches Mermaid diagrams",
                examples=["```mermaid\ngraph TD;\nA-->B;\n```"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.DIAGRAMS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["diagram"],
                    "validation": {
                        "required_fields": ["content"]
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_markdown_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Markdown content for repository learning."""
    patterns = []
    context = MarkdownPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in MARKDOWN_PATTERNS:
                category_patterns = MARKDOWN_PATTERNS[category]
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
                                    if match["type"] == "heading":
                                        context.heading_levels.add(match["level"])
                                    elif match["type"] == "code_block":
                                        if match["language"]:
                                            context.code_langs.add(match["language"])
                                    elif match["type"] == "mermaid":
                                        context.has_mermaid = True
                                    elif match["type"] == "link":
                                        if match["url"].startswith("#"):
                                            context.link_refs.add(match["url"][1:])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Markdown patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "heading": {
        PatternRelationType.CONTAINS: ["emphasis", "link"],
        PatternRelationType.DEPENDS_ON: []
    },
    "list": {
        PatternRelationType.CONTAINS: ["list", "emphasis", "link"],
        PatternRelationType.DEPENDS_ON: []
    },
    "emphasis": {
        PatternRelationType.CONTAINED_BY: ["heading", "list", "paragraph"],
        PatternRelationType.REFERENCES: []
    },
    "link": {
        PatternRelationType.CONTAINED_BY: ["heading", "list", "paragraph"],
        PatternRelationType.REFERENCES: ["link_ref"]
    },
    "code_block": {
        PatternRelationType.CONTAINED_BY: ["document"],
        PatternRelationType.REFERENCES: []
    }
}

# Export public interfaces
__all__ = [
    'MARKDOWN_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_markdown_patterns_for_learning',
    'MarkdownPatternContext',
    'pattern_learner'
]
