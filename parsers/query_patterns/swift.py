"""Query patterns for Swift files.

This module provides Swift-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "swift"

@dataclass
class SwiftPatternContext(PatternContext):
    """Swift-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    struct_names: Set[str] = field(default_factory=set)
    protocol_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    extension_names: Set[str] = field(default_factory=set)
    has_generics: bool = False
    has_protocols: bool = False
    has_extensions: bool = False
    has_async: bool = False
    has_throws: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_generics}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "struct": PatternPerformanceMetrics(),
    "protocol": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "extension": PatternPerformanceMetrics()
}

SWIFT_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_declaration
                        name: (type_identifier) @syntax.class.name
                        type_parameters: (generic_parameter_clause)? @syntax.class.generics
                        inheritance_clause: (type_inheritance_clause)? @syntax.class.inheritance
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                    (struct_declaration
                        name: (type_identifier) @syntax.struct.name
                        type_parameters: (generic_parameter_clause)? @syntax.struct.generics
                        inheritance_clause: (type_inheritance_clause)? @syntax.struct.inheritance
                        body: (struct_body) @syntax.struct.body) @syntax.struct.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.struct.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.struct.def", {}).get("start_point", [0])[0]
                    ),
                    "is_struct": "syntax.struct.def" in node["captures"],
                    "has_generics": (
                        "syntax.class.generics" in node["captures"] or
                        "syntax.struct.generics" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "property", "initializer"],
                        PatternRelationType.DEPENDS_ON: ["protocol", "class"]
                    }
                },
                name="class",
                description="Matches Swift class and struct declarations",
                examples=["class MyClass<T>: BaseClass", "struct Point: Codable"],
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
            "protocol": ResilientPattern(
                pattern="""
                [
                    (protocol_declaration
                        name: (type_identifier) @syntax.protocol.name
                        type_parameters: (generic_parameter_clause)? @syntax.protocol.generics
                        inheritance_clause: (type_inheritance_clause)? @syntax.protocol.inheritance
                        body: (protocol_body) @syntax.protocol.body) @syntax.protocol.def,
                    (extension_declaration
                        name: (type_identifier) @syntax.extension.name
                        type_parameters: (generic_parameter_clause)? @syntax.extension.generics
                        inheritance_clause: (type_inheritance_clause)? @syntax.extension.inheritance
                        body: (extension_body) @syntax.extension.body) @syntax.extension.def
                ]
                """,
                extract=lambda node: {
                    "type": "protocol",
                    "name": (
                        node["captures"].get("syntax.protocol.name", {}).get("text", "") or
                        node["captures"].get("syntax.extension.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.protocol.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.extension.def", {}).get("start_point", [0])[0]
                    ),
                    "is_extension": "syntax.extension.def" in node["captures"],
                    "has_generics": (
                        "syntax.protocol.generics" in node["captures"] or
                        "syntax.extension.generics" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "property", "associatedtype"],
                        PatternRelationType.DEPENDS_ON: ["protocol"]
                    }
                },
                name="protocol",
                description="Matches Swift protocol declarations and extensions",
                examples=["protocol Drawable", "extension Array: CustomStringConvertible"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["protocol"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": ResilientPattern(
                pattern="""
                [
                    (function_declaration
                        modifiers: [(async) (throws)]* @syntax.func.modifier
                        name: (identifier) @syntax.func.name
                        type_parameters: (generic_parameter_clause)? @syntax.func.generics
                        parameters: (parameter_clause) @syntax.func.params
                        return_type: (type_annotation)? @syntax.func.return
                        body: (code_block) @syntax.func.body) @syntax.func.def,
                    (initializer_declaration
                        modifiers: [(convenience) (required)]* @syntax.init.modifier
                        parameters: (parameter_clause) @syntax.init.params
                        body: (code_block) @syntax.init.body) @syntax.init.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": node["captures"].get("syntax.func.name", {}).get("text", ""),
                    "line_number": (
                        node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.init.def", {}).get("start_point", [0])[0]
                    ),
                    "is_init": "syntax.init.def" in node["captures"],
                    "is_async": "async" in (node["captures"].get("syntax.func.modifier", {}).get("text", "") or ""),
                    "is_throws": "throws" in (node["captures"].get("syntax.func.modifier", {}).get("text", "") or ""),
                    "has_generics": "syntax.func.generics" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["statement", "expression"],
                        PatternRelationType.DEPENDS_ON: ["type", "protocol"]
                    }
                },
                name="function",
                description="Matches Swift function declarations",
                examples=["func process<T>(_ data: T) async throws -> Result<T, Error>", "init(name: String)"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.EXTENSIONS: {
            "extension": AdaptivePattern(
                pattern="""
                [
                    (extension_declaration
                        name: (type_identifier) @ext.name
                        type_parameters: (generic_parameter_clause)? @ext.generics
                        inheritance_clause: (type_inheritance_clause)? @ext.inheritance
                        body: (extension_body) @ext.body) @ext.def,
                    (protocol_extension_declaration
                        name: (type_identifier) @ext.protocol.name
                        type_parameters: (generic_parameter_clause)? @ext.protocol.generics
                        inheritance_clause: (type_inheritance_clause)? @ext.protocol.inheritance
                        body: (extension_body) @ext.protocol.body) @ext.protocol.def
                ]
                """,
                extract=lambda node: {
                    "type": "extension",
                    "name": (
                        node["captures"].get("ext.name", {}).get("text", "") or
                        node["captures"].get("ext.protocol.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("ext.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("ext.protocol.def", {}).get("start_point", [0])[0]
                    ),
                    "is_protocol": "ext.protocol.def" in node["captures"],
                    "has_generics": (
                        "ext.generics" in node["captures"] or
                        "ext.protocol.generics" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.EXTENDS: ["class", "struct", "protocol"],
                        PatternRelationType.CONTAINS: ["method", "property"]
                    }
                },
                name="extension",
                description="Matches Swift extension declarations",
                examples=["extension Array where Element: Equatable", "extension Collection"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.EXTENSIONS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["extension"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_swift_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Swift content for repository learning."""
    patterns = []
    context = SwiftPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in SWIFT_PATTERNS:
                category_patterns = SWIFT_PATTERNS[category]
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
                                        if match["is_struct"]:
                                            context.struct_names.add(match["name"])
                                        else:
                                            context.class_names.add(match["name"])
                                        if match["has_generics"]:
                                            context.has_generics = True
                                    elif match["type"] == "protocol":
                                        if match["is_extension"]:
                                            context.extension_names.add(match["name"])
                                            context.has_extensions = True
                                        else:
                                            context.protocol_names.add(match["name"])
                                            context.has_protocols = True
                                    elif match["type"] == "function":
                                        context.function_names.add(match["name"])
                                        if match["is_async"]:
                                            context.has_async = True
                                        if match["is_throws"]:
                                            context.has_throws = True
                                    elif match["type"] == "extension":
                                        context.extension_names.add(match["name"])
                                        context.has_extensions = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Swift patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "property", "initializer"],
        PatternRelationType.DEPENDS_ON: ["protocol", "class"]
    },
    "protocol": {
        PatternRelationType.CONTAINS: ["method", "property", "associatedtype"],
        PatternRelationType.DEPENDS_ON: ["protocol"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["statement", "expression"],
        PatternRelationType.DEPENDS_ON: ["type", "protocol"]
    },
    "extension": {
        PatternRelationType.EXTENDS: ["class", "struct", "protocol"],
        PatternRelationType.CONTAINS: ["method", "property"]
    }
}

# Export public interfaces
__all__ = [
    'SWIFT_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_swift_patterns_for_learning',
    'SwiftPatternContext',
    'pattern_learner'
] 