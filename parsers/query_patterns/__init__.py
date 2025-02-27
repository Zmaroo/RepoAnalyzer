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