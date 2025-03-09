"""Query patterns for Lua files.

This module provides Lua-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "lua"

@dataclass
class LuaPatternContext(PatternContext):
    """Lua-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    table_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    has_metatables: bool = False
    has_coroutines: bool = False
    has_modules: bool = False
    has_oop: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{self.has_metatables}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "table": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics(),
    "metatable": PatternPerformanceMetrics()
}

LUA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                pattern="""
                [
                    (function_declaration
                        name: (identifier) @syntax.func.name
                        parameters: (parameters) @syntax.func.params
                        body: (block) @syntax.func.body) @syntax.func.def,
                    (local_function
                        name: (identifier) @syntax.local.name
                        parameters: (parameters) @syntax.local.params
                        body: (block) @syntax.local.body) @syntax.local.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.local.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_local": "syntax.local.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["table"]
                    }
                },
                name="function",
                description="Matches function declarations",
                examples=["function foo(x) end", "local function bar() end"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "table": ResilientPattern(
                pattern="""
                [
                    (table_constructor
                        (field
                            name: (identifier) @syntax.table.field.name
                            value: (_) @syntax.table.field.value)*) @syntax.table.def,
                    (assignment_statement
                        variables: (variable_list
                            (identifier) @syntax.table.name)
                        values: (expression_list
                            (table_constructor) @syntax.table.value)) @syntax.table.assign
                ]
                """,
                extract=lambda node: {
                    "type": "table",
                    "name": node["captures"].get("syntax.table.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.table.def", {}).get("start_point", [0])[0],
                    "field_count": len(node["captures"].get("syntax.table.field.name", [])),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["field"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="table",
                description="Matches table declarations",
                examples=["t = {x = 1, y = 2}", "local t = {}"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["table"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.METATABLES: {
            "metatable": AdaptivePattern(
                pattern="""
                [
                    (function_call
                        name: (identifier) @meta.set.name
                        arguments: (arguments
                            (table_constructor) @meta.set.table) @meta.set.args
                        (#eq? @meta.set.name "setmetatable")) @meta.set,
                        
                    (function_call
                        name: (identifier) @meta.get.name
                        arguments: (arguments) @meta.get.args
                        (#eq? @meta.get.name "getmetatable")) @meta.get,
                        
                    (index_expression
                        table: (identifier) @meta.index.table
                        index: (string) @meta.index.metamethod
                        (#match? @meta.index.metamethod "^__[a-z]+$")) @meta.index
                ]
                """,
                extract=lambda node: {
                    "type": "metatable",
                    "line_number": node["captures"].get("meta.set", {}).get("start_point", [0])[0],
                    "is_setting_metatable": "meta.set" in node["captures"],
                    "is_getting_metatable": "meta.get" in node["captures"],
                    "uses_metamethod": "meta.index" in node["captures"],
                    "metamethod": node["captures"].get("meta.index.metamethod", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["table"],
                        PatternRelationType.REFERENCES: ["function"]
                    }
                },
                name="metatable",
                description="Matches metatable operations",
                examples=["setmetatable(t, mt)", "getmetatable(t)", "mt.__index = function() end"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.METATABLES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["metatable"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^__[a-z]+$'
                    }
                }
            )
        },
        PatternPurpose.MODULES: {
            "module": AdaptivePattern(
                pattern="""
                [
                    (assignment_statement
                        variables: (variable_list
                            (identifier) @module.name)
                        values: (expression_list
                            (table_constructor) @module.table)) @module.def,
                        
                    (function_call
                        name: (identifier) @module.require.name
                        arguments: (arguments
                            (string) @module.require.path) @module.require.args
                        (#eq? @module.require.name "require")) @module.require
                ]
                """,
                extract=lambda node: {
                    "type": "module",
                    "name": node["captures"].get("module.name", {}).get("text", ""),
                    "line_number": node["captures"].get("module.def", {}).get("start_point", [0])[0],
                    "is_module_definition": "module.def" in node["captures"],
                    "is_module_import": "module.require" in node["captures"],
                    "module_path": node["captures"].get("module.require.path", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["function", "table"],
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="module",
                description="Matches module patterns",
                examples=["local M = {}", "require('module')"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.MODULES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["module"],
                    "validation": {
                        "required_fields": [],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_lua_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Lua content for repository learning."""
    patterns = []
    context = LuaPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in LUA_PATTERNS:
                category_patterns = LUA_PATTERNS[category]
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
                                    if match["type"] == "function":
                                        context.function_names.add(match["name"])
                                    elif match["type"] == "table":
                                        context.table_names.add(match["name"])
                                    elif match["type"] == "metatable":
                                        context.has_metatables = True
                                    elif match["type"] == "module":
                                        context.has_modules = True
                                        if match["is_module_definition"]:
                                            context.module_names.add(match["name"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Lua patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["table"]
    },
    "table": {
        PatternRelationType.CONTAINS: ["field"],
        PatternRelationType.DEPENDS_ON: ["function"]
    },
    "module": {
        PatternRelationType.CONTAINS: ["function", "table"],
        PatternRelationType.DEPENDS_ON: ["module"]
    },
    "metatable": {
        PatternRelationType.DEPENDS_ON: ["table"],
        PatternRelationType.REFERENCES: ["function"]
    }
}

# Export public interfaces
__all__ = [
    'LUA_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_lua_patterns_for_learning',
    'LuaPatternContext',
    'pattern_learner'
] 