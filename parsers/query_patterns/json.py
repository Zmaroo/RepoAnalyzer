"""Query patterns for JSON files.

This module provides JSON-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
import json
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
LANGUAGE = "json"

@dataclass
class JSONPatternContext(PatternContext):
    """JSON-specific pattern context."""
    object_types: Set[str] = field(default_factory=set)
    array_types: Set[str] = field(default_factory=set)
    key_names: Set[str] = field(default_factory=set)
    value_types: Set[str] = field(default_factory=set)
    has_schema: bool = False
    has_metadata: bool = False
    nesting_level: int = 0
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.object_types)}:{self.nesting_level}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "object": PatternPerformanceMetrics(),
    "array": PatternPerformanceMetrics(),
    "value": PatternPerformanceMetrics(),
    "schema": PatternPerformanceMetrics(),
    "metadata": PatternPerformanceMetrics()
}

def extract_object(node: Dict) -> Dict[str, Any]:
    """Extract object information."""
    return {
        "type": "object",
        "path": node["path"],
        "keys": [child["key"] for child in node.get("children", [])],
        "line_number": node.get("line_number", 0),
        "relationships": {
            PatternRelationType.CONTAINS: ["object", "array", "value"],
            PatternRelationType.DEPENDS_ON: []
        }
    }

def extract_array(node: Dict) -> Dict[str, Any]:
    """Extract array information."""
    return {
        "type": "array",
        "path": node["path"],
        "length": len(node.get("children", [])),
        "line_number": node.get("line_number", 0),
        "relationships": {
            PatternRelationType.CONTAINS: ["object", "array", "value"],
            PatternRelationType.DEPENDS_ON: []
        }
    }

JSON_PATTERNS = {
    PatternCategory.SYNTAX: {
        "object": ResilientPattern(
            pattern=r'\{[^{}]*\}',
            extract=lambda m: {
                "type": "object",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINS: ["object", "array", "value"],
                    PatternRelationType.DEPENDS_ON: []
                }
            },
            description="Matches JSON objects",
            examples=["{\"key\": \"value\"}"],
            name="object",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["object"],
                "validation": {
                    "required_fields": ["content"],
                    "is_valid_json": True
                }
            }
        ),
        "array": ResilientPattern(
            pattern=r'\[[^\[\]]*\]',
            extract=lambda m: {
                "type": "array",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINS: ["object", "array", "value"],
                    PatternRelationType.DEPENDS_ON: []
                }
            },
            description="Matches JSON arrays",
            examples=["[1, 2, 3]"],
            name="array",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["array"],
                "validation": {
                    "required_fields": ["content"],
                    "is_valid_json": True
                }
            }
        )
    },
    
    PatternCategory.SEMANTICS: {
        "schema": AdaptivePattern(
            pattern=r'\{"type":\s*"[^"]+",\s*"properties":\s*\{[^}]+\}\}',
            extract=lambda m: {
                "type": "schema",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINS: ["object"],
                    PatternRelationType.REFERENCES: ["type"]
                }
            },
            description="Matches JSON Schema definitions",
            examples=["{\"type\": \"object\", \"properties\": {\"name\": {\"type\": \"string\"}}}"],
            name="schema",
            category=PatternCategory.SEMANTICS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.9,
            metadata={
                "metrics": PATTERN_METRICS["schema"],
                "validation": {
                    "required_fields": ["content"],
                    "is_valid_schema": True
                }
            }
        ),
        "type": AdaptivePattern(
            pattern=r'"type":\s*"([^"]+)"',
            extract=lambda m: {
                "type": "type",
                "value": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["schema", "object"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches type definitions",
            examples=["\"type\": \"string\""],
            name="type",
            category=PatternCategory.SEMANTICS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.9,
            metadata={
                "metrics": PATTERN_METRICS["type"],
                "validation": {
                    "required_fields": ["value"],
                    "valid_types": ["string", "number", "boolean", "object", "array", "null"]
                }
            }
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "description": ResilientPattern(
            pattern=r'"description":\s*"([^"]+)"',
            extract=lambda m: {
                "type": "description",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["object"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches description fields",
            examples=["\"description\": \"A user object\""],
            name="description",
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["description"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "metadata": ResilientPattern(
            pattern=r'"metadata":\s*(\{[^}]+\})',
            extract=lambda m: {
                "type": "metadata",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["object"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches metadata objects",
            examples=["\"metadata\": {\"version\": \"1.0\"}"],
            name="metadata",
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["metadata"],
                "validation": {
                    "required_fields": ["content"],
                    "is_valid_json": True
                }
            }
        )
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_json_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from JSON content for repository learning."""
    patterns = []
    context = JSONPatternContext()
    
    try:
        # First try to parse as JSON to validate
        try:
            json_data = json.loads(content)
            context.has_schema = "$schema" in json_data or "type" in json_data
            context.has_metadata = "metadata" in json_data
        except json.JSONDecodeError:
            await log("Invalid JSON content", level="warning")
            return patterns
        
        # Process each pattern category
        for category in PatternCategory:
            if category in JSON_PATTERNS:
                category_patterns = JSON_PATTERNS[category]
                for pattern_name, pattern in category_patterns.items():
                    if isinstance(pattern, (ResilientPattern, AdaptivePattern)):
                        try:
                            matches = await pattern.matches(content, context)
                            for match in matches:
                                patterns.append({
                                    "name": pattern_name,
                                    "category": category.value,
                                    "content": match.get("text", ""),
                                    "metadata": match,
                                    "confidence": pattern.confidence,
                                    "relationships": match.get("relationships", {})
                                })
                                
                                # Update context
                                if match["type"] == "object":
                                    context.object_types.add(match.get("path", ""))
                                elif match["type"] == "array":
                                    context.array_types.add(match.get("path", ""))
                                elif match["type"] == "type":
                                    context.value_types.add(match["value"])
                                
                        except Exception as e:
                            await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                            continue
    
    except Exception as e:
        await log(f"Error extracting JSON patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "object": {
        PatternRelationType.CONTAINS: ["object", "array", "value"],
        PatternRelationType.DEPENDS_ON: []
    },
    "array": {
        PatternRelationType.CONTAINS: ["object", "array", "value"],
        PatternRelationType.DEPENDS_ON: []
    },
    "schema": {
        PatternRelationType.CONTAINS: ["object"],
        PatternRelationType.REFERENCES: ["type"]
    },
    "type": {
        PatternRelationType.CONTAINED_BY: ["schema", "object"],
        PatternRelationType.REFERENCES: []
    },
    "description": {
        PatternRelationType.CONTAINED_BY: ["object"],
        PatternRelationType.REFERENCES: []
    }
}

# Export public interfaces
__all__ = [
    'JSON_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_json_patterns_for_learning',
    'JSONPatternContext',
    'pattern_learner'
] 