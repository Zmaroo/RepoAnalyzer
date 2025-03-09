"""Query patterns for Svelte files.

This module provides Svelte-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "svelte"

@dataclass
class SveltePatternContext(PatternContext):
    """Svelte-specific pattern context."""
    component_names: Set[str] = field(default_factory=set)
    store_names: Set[str] = field(default_factory=set)
    action_names: Set[str] = field(default_factory=set)
    event_names: Set[str] = field(default_factory=set)
    has_typescript: bool = False
    has_stores: bool = False
    has_actions: bool = False
    has_transitions: bool = False
    has_animations: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.component_names)}:{self.has_stores}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "component": PatternPerformanceMetrics(),
    "script": PatternPerformanceMetrics(),
    "style": PatternPerformanceMetrics(),
    "store": PatternPerformanceMetrics(),
    "action": PatternPerformanceMetrics()
}

SVELTE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "component": ResilientPattern(
                pattern="""
                [
                    (script_element
                        attribute: (attribute)* @syntax.script.attrs
                        content: [(javascript_program) (typescript_program)]? @syntax.script.content) @syntax.script,
                    (style_element
                        attribute: (attribute)* @syntax.style.attrs
                        content: (_)? @syntax.style.content) @syntax.style,
                    (element
                        name: (tag_name) @syntax.custom.name {
                            match: "^[A-Z].*"
                        }
                        attribute: (attribute)* @syntax.custom.attrs
                        body: (_)* @syntax.custom.body) @syntax.custom
                ]
                """,
                extract=lambda node: {
                    "type": "component",
                    "line_number": (
                        node["captures"].get("syntax.script", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.style", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.custom", {}).get("start_point", [0])[0]
                    ),
                    "name": node["captures"].get("syntax.custom.name", {}).get("text", ""),
                    "has_script": "syntax.script" in node["captures"],
                    "has_style": "syntax.style" in node["captures"],
                    "has_typescript": "typescript_program" in (node["captures"].get("syntax.script.content", {}).get("type", "") or ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["script", "style", "element"],
                        PatternRelationType.DEPENDS_ON: ["component"]
                    }
                },
                name="component",
                description="Matches Svelte component declarations",
                examples=["<script>...</script>", "<style>...</style>", "<CustomComponent/>"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["component"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            ),
            "store": ResilientPattern(
                pattern="""
                [
                    (lexical_declaration
                        declarator: (variable_declarator
                            name: (identifier) @syntax.store.name
                            value: (call_expression
                                function: (identifier) @syntax.store.func {
                                    match: "^(writable|readable|derived)$"
                                }
                                arguments: (arguments) @syntax.store.args) @syntax.store.init) @syntax.store.decl) @syntax.store,
                    (assignment_expression
                        left: (member_expression
                            object: (_) @syntax.update.obj
                            property: (property_identifier) @syntax.update.prop {
                                match: "^(set|update)$"
                            }) @syntax.update.target
                        right: (_) @syntax.update.value) @syntax.update
                ]
                """,
                extract=lambda node: {
                    "type": "store",
                    "line_number": (
                        node["captures"].get("syntax.store", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.update", {}).get("start_point", [0])[0]
                    ),
                    "name": node["captures"].get("syntax.store.name", {}).get("text", ""),
                    "store_type": node["captures"].get("syntax.store.func", {}).get("text", ""),
                    "is_update": "syntax.update" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["component", "script"],
                        PatternRelationType.DEPENDS_ON: ["store"]
                    }
                },
                name="store",
                description="Matches Svelte store declarations",
                examples=["const count = writable(0)", "count.set(1)"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["store"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_$][a-zA-Z0-9_$]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.EVENTS: {
            "event_handling": AdaptivePattern(
                pattern="""
                [
                    (attribute
                        name: (attribute_name) @event.attr.name {
                            match: "^(on:[a-zA-Z]+)$"
                        }
                        value: (attribute_value) @event.attr.value) @event.attr,
                    (attribute
                        name: (attribute_name) @event.action.name {
                            match: "^(use:[a-zA-Z]+)$"
                        }
                        value: (attribute_value) @event.action.value) @event.action,
                    (lexical_declaration
                        declarator: (variable_declarator
                            name: (identifier) @event.dispatcher.name
                            value: (call_expression
                                function: (identifier) @event.dispatcher.func {
                                    match: "^(createEventDispatcher)$"
                                }) @event.dispatcher.init) @event.dispatcher.decl) @event.dispatcher,
                    (call_expression
                        function: (identifier) @event.dispatch.func {
                            match: "^(dispatch)$"
                        }
                        arguments: (arguments
                            (string) @event.dispatch.name) @event.dispatch.args) @event.dispatch
                ]
                """,
                extract=lambda node: {
                    "type": "event_handling",
                    "line_number": (
                        node["captures"].get("event.attr", {}).get("start_point", [0])[0] or
                        node["captures"].get("event.action", {}).get("start_point", [0])[0] or
                        node["captures"].get("event.dispatcher", {}).get("start_point", [0])[0] or
                        node["captures"].get("event.dispatch", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("event.attr.name", {}).get("text", "") or
                        node["captures"].get("event.action.name", {}).get("text", "") or
                        node["captures"].get("event.dispatcher.name", {}).get("text", "") or
                        node["captures"].get("event.dispatch.name", {}).get("text", "")
                    ),
                    "is_action": "event.action" in node["captures"],
                    "is_dispatcher": "event.dispatcher" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["component", "element"],
                        PatternRelationType.DEPENDS_ON: ["script"]
                    }
                },
                name="event_handling",
                description="Matches Svelte event handling patterns",
                examples=["on:click={handleClick}", "use:action", "dispatch('event')"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.EVENTS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["action"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_$][a-zA-Z0-9_$]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_svelte_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Svelte content for repository learning."""
    patterns = []
    context = SveltePatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in SVELTE_PATTERNS:
                category_patterns = SVELTE_PATTERNS[category]
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
                                    if match["type"] == "component":
                                        if match["name"]:
                                            context.component_names.add(match["name"])
                                        if match["has_typescript"]:
                                            context.has_typescript = True
                                    elif match["type"] == "store":
                                        context.has_stores = True
                                        context.store_names.add(match["name"])
                                    elif match["type"] == "event_handling":
                                        if match["is_action"]:
                                            context.has_actions = True
                                            context.action_names.add(match["name"])
                                        else:
                                            context.event_names.add(match["name"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Svelte patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "component": {
        PatternRelationType.CONTAINS: ["script", "style", "element"],
        PatternRelationType.DEPENDS_ON: ["component"]
    },
    "store": {
        PatternRelationType.REFERENCED_BY: ["component", "script"],
        PatternRelationType.DEPENDS_ON: ["store"]
    },
    "event_handling": {
        PatternRelationType.CONTAINED_BY: ["component", "element"],
        PatternRelationType.DEPENDS_ON: ["script"]
    }
}

# Export public interfaces
__all__ = [
    'SVELTE_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_svelte_patterns_for_learning',
    'SveltePatternContext',
    'pattern_learner'
] 