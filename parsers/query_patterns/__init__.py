"""
Query patterns initialization module.
Provides lazy loading mechanism for pattern modules to avoid circular imports.
"""

import os
import importlib
import logging
from typing import Dict, Any, Optional, Set, Callable

# Track loaded modules to prevent redundant loading
_loaded_modules: Set[str] = set()

# Pattern registry for lazy loading
_pattern_registry: Dict[str, Dict[str, Any]] = {}

# Flag to track initialization
_initialized = False

# Initialize logger
logger = logging.getLogger(__name__)

# Import core pattern validation functionality
from parsers.pattern_validator import validate_all_patterns, report_validation_results

def _normalize_language_name(name: str) -> str:
    """Normalize language name to handle special cases."""
    name = name.lower().replace('-', '_')
    
    # Special case mappings
    mappings = {
        'js': 'javascript',
        'ts': 'typescript',
        'py': 'python',
        'rb': 'ruby',
        'dockerfile': 'dockerfil',  # Handle special case
    }
    
    return mappings.get(name, name)

def get_pattern_module(language: str) -> Optional[Any]:
    """
    Lazily load a specific language pattern module.
    
    Args:
        language: The programming language name
        
    Returns:
        Module object or None if not found
    """
    language = _normalize_language_name(language)
    
    # Return from cache if already loaded
    if language in _loaded_modules:
        try:
            return importlib.import_module(f"parsers.query_patterns.{language}")
        except ImportError:
            logging.error(f"Failed to import previously loaded module: {language}")
            return None
    
    # Try to load the module
    try:
        module = importlib.import_module(f"parsers.query_patterns.{language}")
        _loaded_modules.add(language)
        return module
    except ImportError as e:
        logging.debug(f"Pattern module not found for language: {language}. {str(e)}")
        return None

def get_patterns_for_language(language: str) -> Dict[str, Any]:
    """
    Get patterns for a specific language, loading them on demand.
    
    Args:
        language: The programming language name
        
    Returns:
        Dictionary of patterns or empty dict if not found
    """
    language = _normalize_language_name(language)
    
    # Return from registry if already loaded
    if language in _pattern_registry:
        return _pattern_registry[language]
    
    # Load the module and extract patterns
    module = get_pattern_module(language)
    if not module:
        return {}
    
    patterns = {}
    for attr in dir(module):
        if attr.endswith('_PATTERNS') and not attr.startswith('__'):
            pattern_dict = getattr(module, attr)
            if isinstance(pattern_dict, dict):
                patterns.update(pattern_dict)
    
    # Cache the patterns
    _pattern_registry[language] = patterns
    return patterns

def register_common_patterns() -> Dict[str, Any]:
    """Register common patterns that apply to multiple languages."""
    try:
        from parsers.query_patterns.common import COMMON_PATTERNS
        return COMMON_PATTERNS
    except ImportError:
        logging.error("Failed to import common patterns")
        return {}

def list_available_languages() -> Set[str]:
    """Return a set of all available language pattern modules."""
    pattern_dir = os.path.dirname(__file__)
    languages = set()
    
    for file in os.listdir(pattern_dir):
        if file.endswith('.py') and not file.startswith('__'):
            lang = file[:-3]  # Remove .py extension
            languages.add(lang)
    
    return languages

def initialize_pattern_system():
    """Initialize the pattern system, preparing it for use."""
    global _initialized
    if _initialized:
        return
    
    # Load common patterns
    common_patterns = register_common_patterns()
    logging.debug(f"Registered {len(common_patterns)} common patterns")
    
    # Don't eagerly load all patterns - just note what's available
    available_languages = list_available_languages()
    logging.debug(f"Found {len(available_languages)} language pattern modules")
    
    _initialized = True

# Initialize when imported, but don't load all patterns
initialize_pattern_system()

# Expose key functions
__all__ = [
    'get_pattern_module',
    'get_patterns_for_language',
    'list_available_languages',
]

# Language pattern registries
_pattern_registries = {}

def get_patterns_for_language(language_id: str) -> Dict[str, Any]:
    """
    Get patterns for the specified language, loading them if necessary.
    
    Args:
        language_id: The language identifier to get patterns for
        
    Returns:
        Dictionary of patterns for the language, or empty dict if not supported
    """
    if language_id in _pattern_registries:
        return _pattern_registries[language_id]
        
    # Try to load patterns from the appropriate module
    try:
        module_name = f"parsers.query_patterns.{language_id}"
        module = importlib.import_module(module_name)
        patterns = getattr(module, "PATTERNS", {})
        
        # Validate patterns before registering
        validation_results = validate_all_patterns({language_id: patterns})
        if validation_results:
            validation_report = report_validation_results(validation_results)
            logger.warning(f"Pattern validation found issues:\n{validation_report}")
        
        _pattern_registries[language_id] = patterns
        logger.debug(f"Loaded {len(patterns)} patterns for language {language_id}")
        return patterns
    except (ImportError, AttributeError) as e:
        logger.debug(f"No patterns available for language {language_id}: {str(e)}")
        _pattern_registries[language_id] = {}
        return {}

def get_all_available_patterns() -> Dict[str, Dict[str, Any]]:
    """
    Return a dictionary of all available patterns for all languages.
    
    Returns:
        Dictionary mapping language IDs to their pattern dictionaries
    """
    # Currently loaded patterns
    patterns = {}
    
    # Add any patterns that were already loaded
    for language_id, pattern_registry in _pattern_registries.items():
        patterns[language_id] = pattern_registry
        
    return patterns

def clear_pattern_cache():
    """Clear the pattern registry cache."""
    global _pattern_registries
    _pattern_registries = {}
    logger.debug("Pattern registry cache cleared")

def validate_loaded_patterns() -> str:
    """
    Validate all currently loaded patterns and return a report.
    
    Returns:
        String containing the validation report
    """
    patterns_by_language = get_all_available_patterns()
    validation_results = validate_all_patterns(patterns_by_language)
    return report_validation_results(validation_results)