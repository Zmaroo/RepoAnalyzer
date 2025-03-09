"""
Query patterns for Perl files.

This module provides Perl-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "perl"

@dataclass
class PerlPatternContext(PatternContext):
    """Perl-specific pattern context."""
    subroutine_names: Set[str] = field(default_factory=set)
    package_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    has_moose: bool = False
    has_regex: bool = False
    has_dbi: bool = False
    has_object_oriented: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.subroutine_names)}:{self.has_moose}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "subroutine": PatternPerformanceMetrics(),
    "package": PatternPerformanceMetrics(),
    "regex": PatternPerformanceMetrics(),
    "object": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics()
}

PERL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "subroutine": ResilientPattern(
                pattern="""
                [
                    (subroutine_declaration
                        attributes: (attribute_list)? @syntax.sub.attrs
                        name: [(bare_word) @syntax.sub.name
                              (package_qualified_word) @syntax.sub.qualified_name]
                        prototype: (prototype)? @syntax.sub.proto
                        signature: (signature)? @syntax.sub.sig
                        body: (block) @syntax.sub.body) @syntax.sub.def
                ]
                """,
                extract=lambda node: {
                    "type": "subroutine",
                    "name": (
                        node["captures"].get("syntax.sub.name", {}).get("text", "") or
                        node["captures"].get("syntax.sub.qualified_name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.sub.def", {}).get("start_point", [0])[0],
                    "has_signature": "syntax.sub.sig" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="subroutine",
                description="Matches Perl subroutine declarations",
                examples=["sub process_data { }", "sub MyPackage::handle_event { }"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["subroutine"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_:]*$'
                    }
                }
            ),
            "package": ResilientPattern(
                pattern="""
                [
                    (package_statement
                        name: (package_qualified_word) @syntax.pkg.name
                        version: (version_number)? @syntax.pkg.version
                        block: (block)? @syntax.pkg.body) @syntax.pkg.def,
                    (use_statement
                        module: (package_qualified_word) @syntax.use.module
                        version: (version_number)? @syntax.use.version
                        imports: (import_list)? @syntax.use.imports) @syntax.use.def
                ]
                """,
                extract=lambda node: {
                    "type": "package",
                    "name": (
                        node["captures"].get("syntax.pkg.name", {}).get("text", "") or
                        node["captures"].get("syntax.use.module", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.pkg.def", {}).get("start_point", [0])[0],
                    "is_use": "syntax.use.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["subroutine"],
                        PatternRelationType.DEPENDS_ON: ["package"]
                    }
                },
                name="package",
                description="Matches Perl package declarations",
                examples=["package MyModule;", "use strict;"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["package"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9:]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.OBJECT_ORIENTED: {
            "moose": AdaptivePattern(
                pattern="""
                [
                    (use_statement
                        module: (package_qualified_word) @oop.module
                        (#match? @oop.module "^(Moose|Moo|Mouse|Class::Accessor)$")) @oop.use,
                        
                    (function_call
                        function: (bare_word) @oop.func.name
                        (#match? @oop.func.name "^(has|extends|with|method|before|after|around)$")
                        arguments: (argument_list) @oop.func.args) @oop.func
                ]
                """,
                extract=lambda node: {
                    "type": "object_oriented",
                    "line_number": node["captures"].get("oop.use", {}).get("start_point", [0])[0],
                    "framework": node["captures"].get("oop.module", {}).get("text", ""),
                    "method_type": node["captures"].get("oop.func.name", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["package"],
                        PatternRelationType.CONTAINS: ["subroutine"]
                    }
                },
                name="moose",
                description="Matches Perl OOP patterns",
                examples=["use Moose;", "has 'name' => (is => 'rw');"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.OBJECT_ORIENTED,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["object"],
                    "validation": {
                        "required_fields": []
                    }
                }
            )
        },
        PatternPurpose.REGEX: {
            "regex": AdaptivePattern(
                pattern="""
                [
                    (regex
                        pattern: (_) @regex.pattern
                        modifiers: (_)? @regex.mods) @regex.def,
                        
                    (substitution
                        pattern: (_) @regex.sub.pattern
                        replacement: (_) @regex.sub.repl
                        modifiers: (_)? @regex.sub.mods) @regex.sub
                ]
                """,
                extract=lambda node: {
                    "type": "regex",
                    "line_number": node["captures"].get("regex.def", {}).get("start_point", [0])[0],
                    "is_substitution": "regex.sub" in node["captures"],
                    "pattern": (
                        node["captures"].get("regex.pattern", {}).get("text", "") or
                        node["captures"].get("regex.sub.pattern", {}).get("text", "")
                    ),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: [],
                        PatternRelationType.REFERENCES: []
                    }
                },
                name="regex",
                description="Matches Perl regex patterns",
                examples=["m/pattern/g", "s/pattern/replacement/"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REGEX,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["regex"],
                    "validation": {
                        "required_fields": ["pattern"]
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_perl_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Perl content for repository learning."""
    patterns = []
    context = PerlPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in PERL_PATTERNS:
                category_patterns = PERL_PATTERNS[category]
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
                                    if match["type"] == "subroutine":
                                        context.subroutine_names.add(match["name"])
                                    elif match["type"] == "package":
                                        context.package_names.add(match["name"])
                                    elif match["type"] == "object_oriented":
                                        context.has_object_oriented = True
                                        if match["framework"] == "Moose":
                                            context.has_moose = True
                                    elif match["type"] == "regex":
                                        context.has_regex = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Perl patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "subroutine": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["package"]
    },
    "package": {
        PatternRelationType.CONTAINS: ["subroutine"],
        PatternRelationType.DEPENDS_ON: ["package"]
    },
    "object_oriented": {
        PatternRelationType.DEPENDS_ON: ["package"],
        PatternRelationType.CONTAINS: ["subroutine"]
    },
    "regex": {
        PatternRelationType.DEPENDS_ON: [],
        PatternRelationType.REFERENCES: []
    }
}

# Export public interfaces
__all__ = [
    'PERL_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_perl_patterns_for_learning',
    'PerlPatternContext',
    'pattern_learner'
] 