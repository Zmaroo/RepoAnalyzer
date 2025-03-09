"""Query patterns for Ruby files.

This module provides Ruby-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "ruby"

@dataclass
class RubyPatternContext(PatternContext):
    """Ruby-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    method_names: Set[str] = field(default_factory=set)
    gem_names: Set[str] = field(default_factory=set)
    has_rails: bool = False
    has_rspec: bool = False
    has_modules: bool = False
    has_mixins: bool = False
    has_blocks: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_rails}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics(),
    "method": PatternPerformanceMetrics(),
    "gem": PatternPerformanceMetrics(),
    "block": PatternPerformanceMetrics()
}

RUBY_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class
                        name: (constant) @syntax.class.name
                        superclass: (constant)? @syntax.class.super
                        body: (_)? @syntax.class.body) @syntax.class.def,
                    (singleton_class
                        value: (_) @syntax.singleton.value
                        body: (_)? @syntax.singleton.body) @syntax.singleton.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0],
                    "superclass": node["captures"].get("syntax.class.super", {}).get("text", ""),
                    "is_singleton": "syntax.singleton.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "constant", "include"],
                        PatternRelationType.DEPENDS_ON: ["class", "module"]
                    }
                },
                name="class",
                description="Matches Ruby class declarations",
                examples=["class MyClass < BaseClass", "class << self"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["class"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "module": ResilientPattern(
                pattern="""
                [
                    (module
                        name: (constant) @syntax.module.name
                        body: (_)? @syntax.module.body) @syntax.module.def,
                    (include
                        name: (constant) @syntax.include.name) @syntax.include.def,
                    (extend
                        name: (constant) @syntax.extend.name) @syntax.extend.def
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "name": (
                        node["captures"].get("syntax.module.name", {}).get("text", "") or
                        node["captures"].get("syntax.include.name", {}).get("text", "") or
                        node["captures"].get("syntax.extend.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.module.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.include.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.extend.def", {}).get("start_point", [0])[0]
                    ),
                    "is_include": "syntax.include.def" in node["captures"],
                    "is_extend": "syntax.extend.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "constant"],
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="module",
                description="Matches Ruby module declarations and inclusions",
                examples=["module MyModule", "include Enumerable", "extend ActiveSupport::Concern"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["module"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_:]*$'
                    }
                }
            ),
            "method": ResilientPattern(
                pattern="""
                [
                    (method
                        name: (identifier) @syntax.method.name
                        parameters: (method_parameters)? @syntax.method.params
                        body: (_)? @syntax.method.body) @syntax.method.def,
                    (singleton_method
                        object: (_) @syntax.singleton.method.obj
                        name: (identifier) @syntax.singleton.method.name
                        parameters: (method_parameters)? @syntax.singleton.method.params
                        body: (_)? @syntax.singleton.method.body) @syntax.singleton.method.def
                ]
                """,
                extract=lambda node: {
                    "type": "method",
                    "name": (
                        node["captures"].get("syntax.method.name", {}).get("text", "") or
                        node["captures"].get("syntax.singleton.method.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.method.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.singleton.method.def", {}).get("start_point", [0])[0]
                    ),
                    "is_singleton": "syntax.singleton.method.def" in node["captures"],
                    "has_params": (
                        "syntax.method.params" in node["captures"] or
                        "syntax.singleton.method.params" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["block", "call"],
                        PatternRelationType.DEPENDS_ON: ["class", "module"]
                    }
                },
                name="method",
                description="Matches Ruby method declarations",
                examples=["def process(data)", "def self.create", "def my_method; end"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["method"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z_][a-zA-Z0-9_]*[?!=]?$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.DEPENDENCIES: {
            "gem": AdaptivePattern(
                pattern="""
                [
                    (call
                        method: (identifier) @gem.name
                        arguments: (argument_list
                            (string) @gem.version)? @gem.args) @gem.def
                        (#match? @gem.name "^gem$"),
                    (call
                        method: (identifier) @gem.require.name
                        arguments: (argument_list
                            (string) @gem.require.path) @gem.require.args) @gem.require.def
                        (#match? @gem.require.name "^require$")
                ]
                """,
                extract=lambda node: {
                    "type": "gem",
                    "line_number": (
                        node["captures"].get("gem.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("gem.require.def", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("gem.args", {}).get("text", "") or
                        node["captures"].get("gem.require.path", {}).get("text", "")
                    ),
                    "version": node["captures"].get("gem.version", {}).get("text", ""),
                    "is_require": "gem.require.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.PROVIDES: ["class", "module", "method"],
                        PatternRelationType.DEPENDS_ON: ["gem"]
                    }
                },
                name="gem",
                description="Matches Ruby gem declarations and requires",
                examples=["gem 'rails', '~> 6.1.0'", "require 'json'"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.DEPENDENCIES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["gem"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-z0-9_-]*$'
                    }
                }
            )
        },
        PatternPurpose.BLOCKS: {
            "block": AdaptivePattern(
                pattern="""
                [
                    (block
                        call: (call) @block.call
                        parameters: (block_parameters)? @block.params
                        body: (_)? @block.body) @block.def,
                    (do_block
                        call: (call) @block.do.call
                        parameters: (block_parameters)? @block.do.params
                        body: (_)? @block.do.body) @block.do.def
                ]
                """,
                extract=lambda node: {
                    "type": "block",
                    "line_number": (
                        node["captures"].get("block.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("block.do.def", {}).get("start_point", [0])[0]
                    ),
                    "has_params": (
                        "block.params" in node["captures"] or
                        "block.do.params" in node["captures"]
                    ),
                    "is_do": "block.do.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["method", "class"],
                        PatternRelationType.DEPENDS_ON: ["method"]
                    }
                },
                name="block",
                description="Matches Ruby block expressions",
                examples=["[1,2,3].each { |n| puts n }", "5.times do |i| end"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.BLOCKS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["block"],
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

async def extract_ruby_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Ruby content for repository learning."""
    patterns = []
    context = RubyPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in RUBY_PATTERNS:
                category_patterns = RUBY_PATTERNS[category]
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
                                    if match["type"] == "class":
                                        context.class_names.add(match["name"])
                                    elif match["type"] == "module":
                                        context.module_names.add(match["name"])
                                        context.has_modules = True
                                        if match["is_include"] or match["is_extend"]:
                                            context.has_mixins = True
                                    elif match["type"] == "method":
                                        context.method_names.add(match["name"])
                                    elif match["type"] == "gem":
                                        context.gem_names.add(match["name"])
                                        if match["name"] == "rails":
                                            context.has_rails = True
                                        elif match["name"] == "rspec":
                                            context.has_rspec = True
                                    elif match["type"] == "block":
                                        context.has_blocks = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Ruby patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "constant", "include"],
        PatternRelationType.DEPENDS_ON: ["class", "module"]
    },
    "module": {
        PatternRelationType.CONTAINS: ["method", "constant"],
        PatternRelationType.DEPENDS_ON: ["module"]
    },
    "method": {
        PatternRelationType.CONTAINS: ["block", "call"],
        PatternRelationType.DEPENDS_ON: ["class", "module"]
    },
    "gem": {
        PatternRelationType.PROVIDES: ["class", "module", "method"],
        PatternRelationType.DEPENDS_ON: ["gem"]
    },
    "block": {
        PatternRelationType.CONTAINED_BY: ["method", "class"],
        PatternRelationType.DEPENDS_ON: ["method"]
    }
}

# Export public interfaces
__all__ = [
    'RUBY_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_ruby_patterns_for_learning',
    'RubyPatternContext',
    'pattern_learner'
] 