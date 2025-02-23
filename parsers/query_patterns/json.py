"""
Query patterns for JSON files with enhanced documentation support.
"""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory

def extract_object(node: Dict) -> Dict[str, Any]:
    """Extract object information."""
    return {
        "type": "object",
        "path": node["path"],
        "keys": [child["key"] for child in node.get("children", [])]
    }

def extract_array(node: Dict) -> Dict[str, Any]:
    """Extract array information."""
    return {
        "type": "array",
        "path": node["path"],
        "length": len(node.get("children", []))
    }

JSON_PATTERNS = {
    PatternCategory.SYNTAX: {
        "object": QueryPattern(
            pattern=lambda node: node["type"] == "object",
            extract=extract_object,
            description="Matches JSON objects",
            examples=[{"name": "value"}]
        ),
        "array": QueryPattern(
            pattern=lambda node: node["type"] == "array",
            extract=extract_array,
            description="Matches JSON arrays",
            examples=[[1, 2, 3]]
        ),
        "value": QueryPattern(
            pattern=lambda node: "value" in node,
            extract=lambda node: {
                "type": "value",
                "path": node["path"],
                "value_type": type(node["value"]).__name__,
                "value": node["value"]
            },
            description="Matches JSON primitive values",
            examples=["string", 42, True, None]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "root": QueryPattern(
            pattern=lambda node: node["type"] == "json_document",
            extract=lambda node: {
                "type": "root",
                "root_type": node["root"]["type"]
            },
            description="Matches JSON document root",
            examples=[{"root": {"type": "object"}}]
        ),
        "reference": QueryPattern(
            pattern=lambda node: isinstance(node.get("value", ""), str) and "$ref" in str(node.get("key", "")),
            extract=lambda node: {
                "type": "reference",
                "path": node["path"],
                "target": node["value"]
            },
            description="Matches JSON references",
            examples=[{"$ref": "#/definitions/type"}]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "description": QueryPattern(
            pattern=lambda node: "description" in str(node.get("key", "")),
            extract=lambda node: {
                "type": "description",
                "path": node["path"],
                "content": node.get("value", "")
            },
            description="Matches description fields",
            examples=[{"description": "A detailed description"}]
        ),
        "metadata": QueryPattern(
            pattern=lambda node: node["type"] == "object" and any(
                k in ["title", "version", "$schema"] for k in 
                [child.get("key", "") for child in node.get("children", [])]
            ),
            extract=lambda node: {
                "type": "metadata",
                "path": node["path"],
                "properties": {
                    child["key"]: child["value"]
                    for child in node.get("children", [])
                    if child.get("key") in ["title", "version", "$schema"]
                }
            },
            description="Matches JSON Schema metadata",
            examples=[{"title": "Schema", "version": "1.0"}]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "variable": QueryPattern(
            pattern=lambda node: isinstance(node.get("value", ""), str) and "${" in str(node["value"]),
            extract=lambda node: {
                "type": "variable",
                "path": node["path"],
                "name": node["value"]
            },
            description="Matches variable references",
            examples=[{"key": "${variable}"}]
        ),
        "schema_type": QueryPattern(
            pattern=lambda node: "type" in str(node.get("key", "")),
            extract=lambda node: {
                "type": "schema_type",
                "path": node["path"],
                "value": node.get("value", "")
            },
            description="Matches JSON Schema type definitions",
            examples=[{"type": "string"}]
        )
    }
}

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "object": {
        "can_contain": ["object", "array", "value"],
        "can_be_contained_by": ["object", "array", "root"]
    },
    "array": {
        "can_contain": ["object", "array", "value"],
        "can_be_contained_by": ["object", "array", "root"]
    },
    "value": {
        "can_be_contained_by": ["object", "array"]
    },
    "reference": {
        "can_be_contained_by": ["object"]
    }
} 