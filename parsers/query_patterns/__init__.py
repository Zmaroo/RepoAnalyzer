"""
Query patterns initialization module.
Provides lazy loading mechanism for pattern modules to avoid circular imports.
"""

import os
import importlib
import logging
from typing import Dict, Any, Optional, Set, List, Union, cast
import asyncio
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task

# Import types needed for type annotations
from parsers.types import PatternCategory, QueryPattern, PatternInfo

# Track loaded modules to prevent redundant loading
_loaded_modules: Set[str] = set()

# Registry to store loaded patterns to avoid reloading
_pattern_registry: Dict[str, Dict[str, Any]] = {}
_pattern_registries: Dict[str, Dict[str, Any]] = {}

# Flag to track initialization
_initialized = False
_pending_tasks: Set[asyncio.Future] = set()
_pattern_cache: Dict[str, Dict[str, Any]] = {}

# Initialize logger
logger = logging.getLogger(__name__)

# Import core pattern validation functionality
from parsers.pattern_validator import validate_all_patterns, report_validation_results

# Import all language pattern modules
from . import (
    ada, asm, asciidoc, bash, bibtex, c, clojure, cmake, cobalt,
    commonlisp, cpp, csharp, css, cuda, dart, dockerfil, editorconfig,
    elisp, elixir, elm, env, erlang, fish, fortran, gdscript, gitignore,
    gleam, go, graphql, groovy, hack, haxe, hcl, html, ini, java,
    javascript, json, julia, kotlin, latex, lua, make, markdown, matlab,
    nim, nix, objc, ocaml, ocaml_interface, pascal, perl, php, plaintext,
    powershell, prisma, proto, purescript, python, qmldir, qmljs, r,
    racket, requirements, rst, ruby, rust, scala, scheme, shell, solidity,
    sql, squirrel, starlark, svelte, swift, tcl, toml, tsx, typescript,
    verilog, vhdl, vue, xml, yaml, zig
)

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

@handle_async_errors(error_types=(Exception,))
async def initialize_patterns():
    """Initialize all pattern resources."""
    global _initialized
    
    if _initialized:
        return
    
    try:
        async with AsyncErrorBoundary("pattern initialization"):
            # Initialize commonly used language patterns first
            common_languages = {'python', 'javascript', 'typescript', 'java', 'cpp'}
            for language in common_languages:
                module = globals().get(language)
                if module and hasattr(module, 'initialize'):
                    future = submit_async_task(module.initialize())
                    _pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        _pending_tasks.remove(future)
            
            _initialized = True
            log("Query patterns initialized", level="info")
    except Exception as e:
        log(f"Error initializing query patterns: {e}", level="error")
        raise

async def get_patterns_for_language(language_id: str) -> Optional[Dict[str, Any]]:
    """
    Get all patterns for a specific language.
    
    Args:
        language_id: The language identifier
        
    Returns:
        Dictionary of patterns or None if language not supported
    """
    if not _initialized:
        await initialize_patterns()
    
    # Check cache first
    if language_id in _pattern_cache:
        return _pattern_cache[language_id]
    
    # Try to get patterns from the language module
    module = globals().get(language_id)
    if module:
        if hasattr(module, 'get_patterns'):
            future = submit_async_task(module.get_patterns())
            _pending_tasks.add(future)
            try:
                patterns = await asyncio.wrap_future(future)
                _pattern_cache[language_id] = patterns
                return patterns
            finally:
                _pending_tasks.remove(future)
        elif hasattr(module, 'PATTERNS'):
            _pattern_cache[language_id] = module.PATTERNS
            return module.PATTERNS
    
    return None

async def cleanup_patterns():
    """Clean up all pattern resources."""
    global _initialized
    
    try:
        # Clean up all language modules that have cleanup functions
        cleanup_tasks = []
        
        for module_name, module in globals().items():
            if isinstance(module, type(asyncio)) and hasattr(module, 'cleanup'):
                future = submit_async_task(module.cleanup())
                cleanup_tasks.append(future)
        
        # Wait for all cleanup tasks
        await asyncio.gather(*[asyncio.wrap_future(f) for f in cleanup_tasks], return_exceptions=True)
        
        # Clean up any remaining pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*[asyncio.wrap_future(f) for f in _pending_tasks], return_exceptions=True)
            _pending_tasks.clear()
        
        # Clear pattern cache
        _pattern_cache.clear()
        
        _initialized = False
        log("Query patterns cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up query patterns: {e}", level="error")

# Register cleanup handler
register_shutdown_handler(cleanup_patterns)

# Expose key functions
__all__ = [
    'get_pattern_module',
    'get_patterns_for_language',
    'get_typed_patterns_for_language',
    'list_available_languages',
    'initialize_patterns',
    'cleanup_patterns'
]