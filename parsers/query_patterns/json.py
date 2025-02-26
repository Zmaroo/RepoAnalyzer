"""
Query patterns for JSON files with enhanced documentation support.
"""

from typing import Dict, Any, List, Match, Optional
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory, PatternInfo
import re
import json

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

# Language identifier
LANGUAGE = "json"

# JSON patterns for documentation and semantics
JSON_PATTERNS = {
    PatternCategory.DOCUMENTATION: {
        'description': PatternInfo(
            pattern=r'description|desc|summary|info',
            extract=lambda match: {'description': match.group(0)}
        ),
        'metadata': PatternInfo(
            pattern=r'metadata|meta',
            extract=lambda match: {'metadata': match.group(0)}
        ),
    },
    PatternCategory.SEMANTICS: {
        'variable': PatternInfo(
            pattern=lambda node: node.get('type') == 'value' and isinstance(node.get('key'), str) and node.get('key') in ['var', 'variable', 'const', 'let'],
            extract=lambda node: {'variable_name': node.get('value')}
        ),
        'schema_type': PatternInfo(
            pattern=lambda node: node.get('type') == 'value' and isinstance(node.get('key'), str) and node.get('key') in ['type', 'dataType', 'data_type'],
            extract=lambda node: {'schema_type': node.get('value')}
        ),
    }
}

# JSON patterns specifically for repository learning
JSON_PATTERNS_FOR_LEARNING = {
    # Structure patterns
    'config_structure': PatternInfo(
        pattern=r'(config|configuration|settings|options)',
        extract=lambda match: {
            'type': 'configuration',
            'key': match.group(1)
        }
    ),
    
    'schema_structure': PatternInfo(
        pattern=r'(schema|model|type|interface)',
        extract=lambda match: {
            'type': 'schema',
            'key': match.group(1)
        }
    ),
    
    'data_structure': PatternInfo(
        pattern=r'(data|items|records|entities)',
        extract=lambda match: {
            'type': 'data',
            'key': match.group(1)
        }
    ),
    
    # Naming convention patterns
    'camel_case': PatternInfo(
        pattern=r'"([a-z][a-zA-Z0-9]*)"',  # camelCase
        extract=lambda match: {
            'key': match.group(1),
            'convention': 'camelCase'
        }
    ),
    
    'snake_case': PatternInfo(
        pattern=r'"([a-z][a-z0-9_]+)"',  # snake_case
        extract=lambda match: {
            'key': match.group(1),
            'convention': 'snake_case' if '_' in match.group(1) else 'lowercase'
        }
    ),
    
    'kebab_case': PatternInfo(
        pattern=r'"([a-z][a-z0-9-]+)"',  # kebab-case
        extract=lambda match: {
            'key': match.group(1),
            'convention': 'kebab-case'
        }
    ),
    
    'pascal_case': PatternInfo(
        pattern=r'"([A-Z][a-zA-Z0-9]*)"',  # PascalCase
        extract=lambda match: {
            'key': match.group(1),
            'convention': 'PascalCase'
        }
    ),
    
    # Common field patterns
    'id_field': PatternInfo(
        pattern=r'"(id|_id|uuid|guid)"',
        extract=lambda match: {
            'field': match.group(1),
            'type': 'identifier'
        }
    ),
    
    'timestamp_field': PatternInfo(
        pattern=r'"(created_at|updated_at|timestamp|date|time|created|updated)"',
        extract=lambda match: {
            'field': match.group(1),
            'type': 'timestamp'
        }
    ),
    
    'status_field': PatternInfo(
        pattern=r'"(status|state|active|enabled|disabled)"',
        extract=lambda match: {
            'field': match.group(1),
            'type': 'status'
        }
    ),
    
    # Value format patterns
    'date_format': PatternInfo(
        pattern=r'"(\d{4}-\d{2}-\d{2})"',
        extract=lambda match: {
            'value': match.group(1),
            'format': 'ISO date'
        }
    ),
    
    'datetime_format': PatternInfo(
        pattern=r'"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.0-9]*Z?)"',
        extract=lambda match: {
            'value': match.group(1),
            'format': 'ISO datetime'
        }
    ),
    
    'uuid_format': PatternInfo(
        pattern=r'"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
        extract=lambda match: {
            'value': match.group(1),
            'format': 'UUID'
        }
    ),
    
    'url_format': PatternInfo(
        pattern=r'"(https?://[^\s"]+)"',
        extract=lambda match: {
            'value': match.group(1),
            'format': 'URL'
        }
    ),
}

# Update JSON_PATTERNS with learning patterns
JSON_PATTERNS[PatternCategory.LEARNING] = JSON_PATTERNS_FOR_LEARNING

def extract_json_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """
    Extract JSON patterns from content for repository learning.
    
    Args:
        content: The JSON content to analyze
        
    Returns:
        List of extracted patterns with metadata
    """
    patterns = []
    
    try:
        # Try to parse the JSON first
        json_data = json.loads(content)
        
        # Analyze JSON structure
        structure_patterns = _extract_json_structure_patterns(json_data)
        patterns.extend(structure_patterns)
        
        # Analyze naming conventions
        naming_patterns = _extract_json_naming_patterns(content)
        patterns.extend(naming_patterns)
        
        # Analyze field patterns
        field_patterns = _extract_json_field_patterns(json_data, content)
        patterns.extend(field_patterns)
        
        # Analyze schema patterns
        schema_patterns = _extract_json_schema_patterns(json_data)
        patterns.extend(schema_patterns)
        
    except json.JSONDecodeError:
        # If JSON is invalid, we can still extract some patterns from the text
        patterns.append({
            'name': 'json_invalid',
            'content': 'Invalid JSON format',
            'metadata': {
                'pattern_type': 'syntax_error'
            },
            'confidence': 0.99
        })
        
        # Try to extract naming conventions from text
        naming_patterns = _extract_json_naming_patterns(content)
        patterns.extend(naming_patterns)
    
    return patterns

def _extract_json_structure_patterns(data: Any) -> List[Dict[str, Any]]:
    """Extract structure patterns from JSON data."""
    patterns = []
    
    if isinstance(data, dict):
        # Detect configuration patterns
        if any(k in data for k in ['config', 'configuration', 'settings', 'options']):
            patterns.append({
                'name': 'json_config_structure',
                'content': json.dumps({'type': 'configuration', 'keys': list(data.keys())}, indent=2),
                'metadata': {
                    'structure_type': 'configuration',
                    'top_level_keys': list(data.keys())
                },
                'confidence': 0.9
            })
            
        # Detect API response patterns
        if any(k in data for k in ['data', 'results', 'items', 'response']):
            patterns.append({
                'name': 'json_api_response',
                'content': json.dumps({'type': 'api_response', 'keys': list(data.keys())}, indent=2),
                'metadata': {
                    'structure_type': 'api_response',
                    'top_level_keys': list(data.keys())
                },
                'confidence': 0.85
            })
            
        # Detect metadata patterns
        if any(k in data for k in ['meta', 'metadata', 'info', 'about']):
            patterns.append({
                'name': 'json_metadata_structure',
                'content': json.dumps({'type': 'metadata', 'keys': list(data.keys())}, indent=2),
                'metadata': {
                    'structure_type': 'metadata',
                    'top_level_keys': list(data.keys())
                },
                'confidence': 0.85
            })
            
        # Detect schema definition patterns
        if any(k in data for k in ['schema', 'type', 'properties', 'required']):
            patterns.append({
                'name': 'json_schema_definition',
                'content': json.dumps({'type': 'schema_definition', 'keys': list(data.keys())}, indent=2),
                'metadata': {
                    'structure_type': 'schema_definition',
                    'top_level_keys': list(data.keys())
                },
                'confidence': 0.9
            })
            
    elif isinstance(data, list) and data:
        # Detect collection pattern
        if all(isinstance(item, dict) for item in data):
            # Check if all items have common fields
            if len(data) > 1:
                first_item_keys = set(data[0].keys())
                common_keys = set.intersection(*[set(item.keys()) for item in data])
                
                if common_keys and len(common_keys) >= 2:
                    patterns.append({
                        'name': 'json_collection',
                        'content': json.dumps({'type': 'collection', 'common_fields': list(common_keys)}, indent=2),
                        'metadata': {
                            'structure_type': 'collection',
                            'common_fields': list(common_keys),
                            'item_count': len(data)
                        },
                        'confidence': 0.9
                    })
    
    return patterns

def _extract_json_naming_patterns(content: str) -> List[Dict[str, Any]]:
    """Extract naming convention patterns from JSON content."""
    patterns = []
    
    # Count occurrences of different naming conventions
    camel_case = len(re.findall(r'"([a-z][a-zA-Z0-9]*)"', content))
    snake_case = len(re.findall(r'"([a-z][a-z0-9_]+)"', content))
    kebab_case = len(re.findall(r'"([a-z][a-z0-9-]+)"', content))
    pascal_case = len(re.findall(r'"([A-Z][a-zA-Z0-9]*)"', content))
    upper_case = len(re.findall(r'"([A-Z][A-Z0-9_]+)"', content))
    
    # Determine the dominant convention
    conventions = {
        'camelCase': camel_case,
        'snake_case': snake_case,
        'kebab-case': kebab_case,
        'PascalCase': pascal_case,
        'UPPER_CASE': upper_case
    }
    
    if conventions:
        max_convention = max(conventions.items(), key=lambda x: x[1])
        
        # Only add a pattern if we have a significant number of occurrences
        if max_convention[1] >= 3:
            patterns.append({
                'name': f'json_naming_convention_{max_convention[0]}',
                'content': f"JSON naming convention: {max_convention[0]}",
                'metadata': {
                    'convention': max_convention[0],
                    'count': max_convention[1],
                    'all_conventions': conventions
                },
                'confidence': min(0.7 + (max_convention[1] / 20), 0.95)  # Higher confidence with more instances
            })
    
    return patterns

def _extract_json_field_patterns(data: Any, content: str) -> List[Dict[str, Any]]:
    """Extract common field patterns from JSON data and content."""
    patterns = []
    
    # Check for common field patterns using regex
    id_fields = re.findall(r'"(id|_id|uuid|guid)"', content)
    if id_fields:
        patterns.append({
            'name': 'json_id_field_pattern',
            'content': json.dumps({'field_type': 'identifier', 'fields': id_fields}, indent=2),
            'metadata': {
                'field_type': 'identifier',
                'fields': id_fields
            },
            'confidence': 0.9
        })
        
    timestamp_fields = re.findall(r'"(created_at|updated_at|timestamp|date|time|created|updated)"', content)
    if timestamp_fields:
        patterns.append({
            'name': 'json_timestamp_field_pattern',
            'content': json.dumps({'field_type': 'timestamp', 'fields': timestamp_fields}, indent=2),
            'metadata': {
                'field_type': 'timestamp',
                'fields': timestamp_fields
            },
            'confidence': 0.9
        })
        
    status_fields = re.findall(r'"(status|state|active|enabled|disabled)"', content)
    if status_fields:
        patterns.append({
            'name': 'json_status_field_pattern',
            'content': json.dumps({'field_type': 'status', 'fields': status_fields}, indent=2),
            'metadata': {
                'field_type': 'status',
                'fields': status_fields
            },
            'confidence': 0.85
        })
        
    # Check for field value formats
    date_values = re.findall(r'"(\d{4}-\d{2}-\d{2})"', content)
    datetime_values = re.findall(r'"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.0-9]*Z?)"', content)
    uuid_values = re.findall(r'"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', content)
    url_values = re.findall(r'"(https?://[^\s"]+)"', content)
    
    value_formats = {}
    if date_values:
        value_formats['ISO_date'] = len(date_values)
    if datetime_values:
        value_formats['ISO_datetime'] = len(datetime_values)
    if uuid_values:
        value_formats['UUID'] = len(uuid_values)
    if url_values:
        value_formats['URL'] = len(url_values)
        
    if value_formats:
        patterns.append({
            'name': 'json_value_formats',
            'content': json.dumps({'value_formats': value_formats}, indent=2),
            'metadata': {
                'value_formats': value_formats
            },
            'confidence': 0.9
        })
    
    return patterns

def _extract_json_schema_patterns(data: Any) -> List[Dict[str, Any]]:
    """Extract schema patterns from JSON data."""
    patterns = []
    
    # Check if this looks like a JSON Schema
    if isinstance(data, dict):
        if '$schema' in data or 'properties' in data:
            # This is likely a JSON Schema document
            patterns.append({
                'name': 'json_schema_document',
                'content': json.dumps({'type': 'json_schema'}, indent=2),
                'metadata': {
                    'schema_version': data.get('$schema', 'unknown'),
                    'has_properties': 'properties' in data,
                    'has_definitions': 'definitions' in data or '$defs' in data
                },
                'confidence': 0.95
            })
            
            # Extract property types if present
            if 'properties' in data and isinstance(data['properties'], dict):
                property_types = {}
                for prop_name, prop_def in data['properties'].items():
                    if isinstance(prop_def, dict) and 'type' in prop_def:
                        property_types[prop_name] = prop_def['type']
                        
                if property_types:
                    patterns.append({
                        'name': 'json_schema_property_types',
                        'content': json.dumps({'property_types': property_types}, indent=2),
                        'metadata': {
                            'property_types': property_types
                        },
                        'confidence': 0.9
                    })
    
    return patterns

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