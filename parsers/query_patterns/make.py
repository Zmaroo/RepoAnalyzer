"""Query patterns for Make files.

This module provides Make-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "make"

@dataclass
class MakePatternContext(PatternContext):
    """Make-specific pattern context."""
    target_names: Set[str] = field(default_factory=set)
    variable_names: Set[str] = field(default_factory=set)
    include_paths: Set[str] = field(default_factory=set)
    has_phony_targets: bool = False
    has_pattern_rules: bool = False
    has_conditionals: bool = False
    has_functions: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.target_names)}:{self.has_pattern_rules}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "target": PatternPerformanceMetrics(),
    "variable": PatternPerformanceMetrics(),
    "include": PatternPerformanceMetrics(),
    "rule": PatternPerformanceMetrics()
}

MAKE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "target": ResilientPattern(
                pattern="""
                [
                    (rule
                        targets: (targets
                            (word) @syntax.target.name)
                        prerequisites: (prerequisites
                            (word)* @syntax.target.prereq)
                        recipe: (recipe
                            (shell_command)* @syntax.target.recipe)) @syntax.target.def,
                    (phony_declaration
                        targets: (word) @syntax.phony.name) @syntax.phony.def
                ]
                """,
                extract=lambda node: {
                    "type": "target",
                    "name": (
                        node["captures"].get("syntax.target.name", {}).get("text", "") or
                        node["captures"].get("syntax.phony.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.target.def", {}).get("start_point", [0])[0],
                    "is_phony": "syntax.phony.def" in node["captures"],
                    "prerequisite_count": len(node["captures"].get("syntax.target.prereq", [])),
                    "recipe_count": len(node["captures"].get("syntax.target.recipe", [])),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["target"],
                        PatternRelationType.REFERENCES: ["variable"]
                    }
                },
                name="target",
                description="Matches Make targets and rules",
                examples=["target: deps\n\tcommand", ".PHONY: clean"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["target"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_\-.]+$'
                    }
                }
            ),
            "variable": ResilientPattern(
                pattern="""
                [
                    (variable_assignment
                        name: (word) @syntax.var.name
                        value: (text) @syntax.var.value) @syntax.var.def,
                    (conditional_variable_assignment
                        name: (word) @syntax.cond.name
                        value: (text) @syntax.cond.value) @syntax.cond.def
                ]
                """,
                extract=lambda node: {
                    "type": "variable",
                    "name": (
                        node["captures"].get("syntax.var.name", {}).get("text", "") or
                        node["captures"].get("syntax.cond.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.var.def", {}).get("start_point", [0])[0],
                    "is_conditional": "syntax.cond.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["target", "variable"],
                        PatternRelationType.DEPENDS_ON: ["variable"]
                    }
                },
                name="variable",
                description="Matches Make variable assignments",
                examples=["VAR = value", "VAR ?= default"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["variable"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Za-z_][A-Za-z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.PATTERN_RULES: {
            "pattern_rule": AdaptivePattern(
                pattern="""
                [
                    (rule
                        targets: (targets
                            (word) @pattern.target.name
                            (#match? @pattern.target.name "%"))
                        prerequisites: (prerequisites
                            (word)* @pattern.target.prereq)
                        recipe: (recipe
                            (shell_command)* @pattern.target.recipe)) @pattern.target.def,
                        
                    (variable_reference
                        name: (word) @pattern.var.name
                        (#match? @pattern.var.name "\\$[@%<]")) @pattern.var.ref
                ]
                """,
                extract=lambda node: {
                    "type": "pattern_rule",
                    "line_number": node["captures"].get("pattern.target.def", {}).get("start_point", [0])[0],
                    "uses_pattern_target": "%" in (node["captures"].get("pattern.target.name", {}).get("text", "") or ""),
                    "uses_automatic_var": "pattern.var.ref" in node["captures"],
                    "automatic_var": node["captures"].get("pattern.var.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["target"],
                        PatternRelationType.REFERENCES: ["variable"]
                    }
                },
                name="pattern_rule",
                description="Matches pattern rules and automatic variables",
                examples=["%.o: %.c\n\t$(CC) -c $<", "%.pdf: %.tex\n\t$(TEX) $<"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PATTERN_RULES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["rule"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z0-9_\-.%]+$'
                    }
                }
            )
        },
        PatternPurpose.INCLUDES: {
            "include": AdaptivePattern(
                pattern="""
                [
                    (include_statement
                        files: (word)* @include.file.name) @include.def,
                        
                    (conditional_include_statement
                        files: (word)* @include.cond.name) @include.cond.def,
                        
                    (sinclude_statement
                        files: (word)* @include.silent.name) @include.silent.def
                ]
                """,
                extract=lambda node: {
                    "type": "include",
                    "line_number": node["captures"].get("include.def", {}).get("start_point", [0])[0],
                    "is_conditional": "include.cond.def" in node["captures"],
                    "is_silent": "include.silent.def" in node["captures"],
                    "included_files": [
                        file.get("text", "") for file in (
                            node["captures"].get("include.file.name", []) or
                            node["captures"].get("include.cond.name", []) or
                            node["captures"].get("include.silent.name", [])
                        )
                    ],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["variable"],
                        PatternRelationType.REFERENCES: ["include"]
                    }
                },
                name="include",
                description="Matches include statements",
                examples=["include config.mk", "-include *.d", "sinclude common.mk"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.INCLUDES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["include"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z0-9_\-.*]+\.mk$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_make_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Make content for repository learning."""
    patterns = []
    context = MakePatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in MAKE_PATTERNS:
                category_patterns = MAKE_PATTERNS[category]
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
                                    if match["type"] == "target":
                                        context.target_names.add(match["name"])
                                        if match["is_phony"]:
                                            context.has_phony_targets = True
                                    elif match["type"] == "variable":
                                        context.variable_names.add(match["name"])
                                    elif match["type"] == "pattern_rule":
                                        context.has_pattern_rules = True
                                    elif match["type"] == "include":
                                        context.include_paths.update(match["included_files"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Make patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "target": {
        PatternRelationType.DEPENDS_ON: ["target"],
        PatternRelationType.REFERENCES: ["variable"]
    },
    "variable": {
        PatternRelationType.REFERENCED_BY: ["target", "variable"],
        PatternRelationType.DEPENDS_ON: ["variable"]
    },
    "pattern_rule": {
        PatternRelationType.DEPENDS_ON: ["target"],
        PatternRelationType.REFERENCES: ["variable"]
    },
    "include": {
        PatternRelationType.DEPENDS_ON: ["variable"],
        PatternRelationType.REFERENCES: ["include"]
    }
}

# Export public interfaces
__all__ = [
    'MAKE_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_make_patterns_for_learning',
    'MakePatternContext',
    'pattern_learner'
]