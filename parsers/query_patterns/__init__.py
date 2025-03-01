"""
Query patterns initialization module.
Provides lazy loading mechanism for pattern modules to avoid circular imports.
"""

import os
import importlib
import logging
from typing import Dict, Any, Optional, Set, List, Union, cast

# Import types needed for type annotations
from parsers.types import PatternCategory, QueryPattern, PatternInfo

# Track loaded modules to prevent redundant loading
_loaded_modules: Set[str] = set()

# Registry to store loaded patterns to avoid reloading
_pattern_registry: Dict[str, Dict[str, Any]] = {}
_pattern_registries: Dict[str, Dict[str, Any]] = {}

# Flag to track initialization
_initialized = False

# Initialize logger
logger = logging.getLogger(__name__)

# Import core pattern validation functionality
from parsers.pattern_validator import validate_all_patterns, report_validation_results

def _normalize_language_name(language: str) -> str:
    """Normalize language name for pattern lookup."""
    return language.lower().replace(" ", "_").replace("-", "_")

def get_pattern_module(language_id: str) -> Optional[Any]:
    """
    Lazily load the pattern module for a given language.
    
    Args:
        language_id: The language identifier to load patterns for.
        
    Returns:
        The loaded module or None if not found.
    """
    try:
        # First check if there's a custom module in parsers.query_patterns
        module_name = f"parsers.query_patterns.{language_id}"
        return importlib.import_module(module_name)
    except ImportError:
        # Not found, return None
        return None

def _ensure_pattern_category_keys(patterns_dict: Dict[str, Any]) -> Dict[PatternCategory, Any]:
    """
    Ensures that all keys in the patterns dictionary are PatternCategory enum values.
    
    This function checks if the keys in the provided dictionary are already PatternCategory enums.
    If not, it attempts to convert string keys to the corresponding enum values, handling
    special cases like 'REPOSITORY_LEARNING'.
    
    Args:
        patterns_dict: Dictionary with string keys
        
    Returns:
        Dictionary with PatternCategory enum keys
    """
    result: Dict[PatternCategory, Any] = {}
    
    for key, value in patterns_dict.items():
        # Try to convert string to enum
        try:
            if key == 'REPOSITORY_LEARNING':
                # Special case handling for this category
                enum_key = cast(PatternCategory, key)
                result[enum_key] = value
            else:
                try:
                    enum_key = PatternCategory[key]
                    result[enum_key] = value
                except KeyError:
                    # If conversion fails, log a warning
                    logger.warning(f"Could not convert key '{key}' to PatternCategory enum")
        except (KeyError, TypeError):
            # If conversion fails, log a warning but preserve the key for backward compatibility
            logger.warning(f"Could not convert key '{key}' to PatternCategory enum")
    
    return result

def get_patterns_for_language(language: str) -> Dict[str, Any]:
    """
    Get tree-sitter query patterns for the specified language.
    
    Args:
        language: The language to get patterns for
        
    Returns:
        Dictionary of patterns by category or empty dict if none found
    """
    language_id = _normalize_language_name(language)
    
    # Check if patterns are already loaded
    if language_id in _pattern_registry:
        return _pattern_registry[language_id]
    
    # Load patterns dynamically
    pattern_module = get_pattern_module(language_id)
    
    if pattern_module and hasattr(pattern_module, "PATTERNS"):
        _pattern_registry[language_id] = pattern_module.PATTERNS
        return pattern_module.PATTERNS
    
    # No patterns found for this language
    _pattern_registry[language_id] = {}
    return {}

def get_typed_patterns_for_language(language: str) -> Dict[PatternCategory, Dict[str, QueryPattern]]:
    """
    Get tree-sitter query patterns for the specified language with type annotations.
    This is a wrapper around get_patterns_for_language that ensures keys are PatternCategory enums.
    
    Args:
        language: The language to get patterns for
        
    Returns:
        Dictionary of patterns by category with PatternCategory enum keys
    """
    patterns = get_patterns_for_language(language)
    # Type conversion handling is done inside _ensure_pattern_category_keys
    return _ensure_pattern_category_keys(patterns)

def register_common_patterns() -> Dict[str, Any]:
    """
    Register common patterns that apply to multiple languages.
    
    Returns:
        Dictionary of registered patterns
    """
    try:
        # Import common patterns
        from parsers.query_patterns.common import COMMON_PATTERNS
        return COMMON_PATTERNS
    except ImportError:
        logger.warning("Common patterns module not found")
        return {}

def list_available_languages() -> Set[str]:
    """
    List all available language pattern modules.
    
    Returns:
        Set of available language pattern module names
    """
    languages = set()
    
    # Get the directory path
    dir_path = os.path.dirname(os.path.abspath(__file__))
    
    # Iterate through files in the directory
    for filename in os.listdir(dir_path):
        if filename.endswith(".py") and filename != "__init__.py" and filename != "common.py":
            language = filename[:-3]  # Remove .py extension
            languages.add(language)
    
    return languages

def initialize_pattern_system() -> None:
    """Initialize the pattern system by preloading common patterns."""
    register_common_patterns()

def get_all_available_patterns() -> Dict[str, Dict[str, Any]]:
    """
    Get all available patterns for all languages.
    
    Returns:
        Dictionary of patterns by language
    """
    patterns = {}
    for language in list_available_languages():
        language_patterns = get_patterns_for_language(language)
        if language_patterns:
            patterns[language] = language_patterns
    
    return patterns

def clear_pattern_cache() -> None:
    """Clear the pattern registry cache."""
    global _pattern_registry
    _pattern_registry = {}

def validate_loaded_patterns() -> str:
    """
    Validate all currently loaded patterns.
    
    Returns:
        Summary of validation results
    """
    patterns_by_language = get_all_available_patterns()
    validation_results = validate_all_patterns(patterns_by_language)
    return report_validation_results(validation_results)

# Initialize when imported, but don't load all patterns
initialize_pattern_system()

# Expose key functions
__all__ = [
    'get_pattern_module',
    'get_patterns_for_language',
    'get_typed_patterns_for_language',
    'list_available_languages',
]