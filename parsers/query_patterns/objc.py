"""Query patterns for Objective-C files.

This module provides Objective-C-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "objc"

@dataclass
class ObjCPatternContext(PatternContext):
    """Objective-C-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    method_names: Set[str] = field(default_factory=set)
    property_names: Set[str] = field(default_factory=set)
    protocol_names: Set[str] = field(default_factory=set)
    has_arc: bool = False
    has_categories: bool = False
    has_blocks: bool = False
    has_extensions: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_arc}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "method": PatternPerformanceMetrics(),
    "property": PatternPerformanceMetrics(),
    "protocol": PatternPerformanceMetrics(),
    "category": PatternPerformanceMetrics()
}

OBJC_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": ResilientPattern(
                pattern="""
                [
                    (class_interface
                        name: (identifier) @syntax.class.name
                        superclass: (superclass_reference)? @syntax.class.super
                        protocols: (protocol_reference_list)? @syntax.class.protocols
                        properties: (property_declaration)* @syntax.class.properties
                        methods: (method_declaration)* @syntax.class.methods) @syntax.class.interface,
                    (class_implementation
                        name: (identifier) @syntax.class.impl.name
                        superclass: (superclass_reference)? @syntax.class.impl.super
                        ivars: (instance_variables)? @syntax.class.impl.ivars) @syntax.class.implementation
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.class.impl.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.class.interface", {}).get("start_point", [0])[0],
                    "is_implementation": "syntax.class.implementation" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["property", "method", "ivar"],
                        PatternRelationType.DEPENDS_ON: ["protocol", "class"]
                    }
                },
                name="class",
                description="Matches Objective-C class declarations",
                examples=["@interface MyClass : NSObject", "@implementation MyClass"],
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
            "method": ResilientPattern(
                pattern="""
                [
                    (method_declaration
                        type: (method_type) @syntax.method.type
                        selector: (selector) @syntax.method.selector
                        parameters: (parameter_list)? @syntax.method.params
                        body: (compound_statement)? @syntax.method.body) @syntax.method.def
                ]
                """,
                extract=lambda node: {
                    "type": "method",
                    "selector": node["captures"].get("syntax.method.selector", {}).get("text", ""),
                    "method_type": node["captures"].get("syntax.method.type", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.method.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block"],
                        PatternRelationType.DEPENDS_ON: ["class", "protocol"]
                    }
                },
                name="method",
                description="Matches Objective-C method declarations",
                examples=["- (void)viewDidLoad", "+ (instancetype)sharedInstance"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["method"],
                    "validation": {
                        "required_fields": ["selector"],
                        "method_type_format": r'^[-+]$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.MEMORY_MANAGEMENT: {
            "memory_management": AdaptivePattern(
                pattern="""
                [
                    (message_expression
                        receiver: (_) @mem.msg.receiver
                        selector: (selector) @mem.msg.selector
                        (#match? @mem.msg.selector "alloc|retain|release|autorelease|dealloc")) @mem.msg,
                        
                    (property_declaration
                        attributes: (property_attributes) @mem.prop.attrs) @mem.prop
                ]
                """,
                extract=lambda node: {
                    "type": "memory_management",
                    "line_number": node["captures"].get("mem.msg", {}).get("start_point", [0])[0],
                    "is_memory_message": "mem.msg" in node["captures"],
                    "uses_arc_attributes": "mem.prop" in node["captures"] and "strong" in (node["captures"].get("mem.prop.attrs", {}).get("text", "") or ""),
                    "memory_selector": node["captures"].get("mem.msg.selector", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["class"],
                        PatternRelationType.REFERENCES: ["property"]
                    }
                },
                name="memory_management",
                description="Matches memory management patterns",
                examples=["[object retain]", "@property (nonatomic, strong) NSString *name"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.MEMORY_MANAGEMENT,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["memory"],
                    "validation": {
                        "required_fields": []
                    }
                }
            )
        },
        PatternPurpose.CATEGORIES: {
            "category": AdaptivePattern(
                pattern="""
                [
                    (category_interface
                        name: (identifier) @cat.class
                        category: (identifier) @cat.name) @cat.interface,
                        
                    (category_implementation
                        name: (identifier) @cat.impl.class
                        category: (identifier) @cat.impl.name) @cat.implementation
                ]
                """,
                extract=lambda node: {
                    "type": "category",
                    "class_name": (
                        node["captures"].get("cat.class", {}).get("text", "") or
                        node["captures"].get("cat.impl.class", {}).get("text", "")
                    ),
                    "category_name": (
                        node["captures"].get("cat.name", {}).get("text", "") or
                        node["captures"].get("cat.impl.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("cat.interface", {}).get("start_point", [0])[0],
                    "is_implementation": "cat.implementation" in node["captures"],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["class"],
                        PatternRelationType.CONTAINS: ["method", "property"]
                    }
                },
                name="category",
                description="Matches Objective-C categories",
                examples=["@interface NSString (MyAdditions)", "@implementation UIView (Animations)"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.CATEGORIES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["category"],
                    "validation": {
                        "required_fields": ["class_name", "category_name"],
                        "class_name_format": r'^[A-Z][a-zA-Z0-9_]*$',
                        "category_name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_objc_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Objective-C content for repository learning."""
    patterns = []
    context = ObjCPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in OBJC_PATTERNS:
                category_patterns = OBJC_PATTERNS[category]
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
                                    elif match["type"] == "method":
                                        context.method_names.add(match["selector"])
                                    elif match["type"] == "memory_management":
                                        if match["uses_arc_attributes"]:
                                            context.has_arc = True
                                    elif match["type"] == "category":
                                        context.has_categories = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Objective-C patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["property", "method", "ivar"],
        PatternRelationType.DEPENDS_ON: ["protocol", "class"]
    },
    "method": {
        PatternRelationType.CONTAINS: ["parameter", "block"],
        PatternRelationType.DEPENDS_ON: ["class", "protocol"]
    },
    "property": {
        PatternRelationType.DEPENDS_ON: ["class"],
        PatternRelationType.REFERENCES: ["class"]
    },
    "category": {
        PatternRelationType.DEPENDS_ON: ["class"],
        PatternRelationType.CONTAINS: ["method", "property"]
    }
}

# Export public interfaces
__all__ = [
    'OBJC_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_objc_patterns_for_learning',
    'ObjCPatternContext',
    'pattern_learner'
] 