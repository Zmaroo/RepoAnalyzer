"""
Query patterns initialization module.
Provides lazy loading mechanism for pattern modules to avoid circular imports.
Integrates with cache analytics, error handling, and logging systems.
"""

import os
import importlib
import logging
from typing import Dict, Any, Optional, Set, List, Union, cast, Callable, Tuple
import asyncio
from utils.logger import log
from utils.error_handling import (
    handle_async_errors, 
    AsyncErrorBoundary, 
    ErrorSeverity,
    ErrorAudit
)
from utils.shutdown import register_shutdown_handler
from utils.async_runner import get_loop
from collections import OrderedDict
import time
from tree_sitter_language_pack import SupportedLanguage
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from utils.cache import UnifiedCache, cache_coordinator
from utils.cache_analytics import get_cache_analytics
from utils.request_cache import request_cache_context, get_current_request_cache
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation

# Import types needed for type annotations
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, 
    QueryPattern, PatternDefinition, PatternInfo
)

from parsers.language_mapping import normalize_language_name

# Track loaded modules to prevent redundant loading
_loaded_modules: Set[str] = set()

# Registry to store loaded patterns to avoid reloading
_pattern_registry: Dict[str, Dict[PatternCategory, Dict[PatternPurpose, Dict[str, QueryPattern]]]] = {}
_pattern_registries: Dict[str, Dict[PatternCategory, Dict[PatternPurpose, Dict[str, QueryPattern]]]] = {}

# Flag to track initialization
_initialized = False
_pending_tasks: Set[asyncio.Task] = set()

# Maximum number of patterns to cache
MAX_CACHE_SIZE = 1000

# Initialize caches
_pattern_cache = UnifiedCache("pattern_cache")
_validation_cache = UnifiedCache("validation_cache")

class LRUCache:
    """LRU cache implementation for patterns."""
    
    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        async with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                value = self._cache.pop(key)
                self._cache[key] = value
                self._metrics["hits"] += 1
                return value
            self._metrics["misses"] += 1
            return None
    
    async def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        async with self._lock:
            if key in self._cache:
                # Update existing entry
                self._cache.pop(key)
            elif len(self._cache) >= self._max_size:
                # Remove least recently used item
                self._cache.popitem(last=False)
                self._metrics["evictions"] += 1
            self._cache[key] = value
    
    async def clear(self) -> None:
        """Clear the cache."""
        async with self._lock:
            self._cache.clear()
            self._metrics = {
                "hits": 0,
                "misses": 0,
                "evictions": 0
            }

# Replace global pattern cache with LRU cache
_pattern_cache = LRUCache()

# Initialize logger
logger = logging.getLogger(__name__)

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

def _ensure_pattern_category_keys(patterns_dict: Dict[str, Any]) -> Dict[PatternCategory, Dict[PatternPurpose, Dict[str, QueryPattern]]]:
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
    result: Dict[PatternCategory, Dict[PatternPurpose, Dict[str, QueryPattern]]] = {}
    
    for key, value in patterns_dict.items():
        if isinstance(key, str):
            try:
                if key == 'REPOSITORY_LEARNING':
                    # Special case handling for learning patterns
                    result[PatternCategory.LEARNING] = value
                else:
                    # Try to convert string to enum
                    enum_key = PatternCategory[key.upper()]
                    if isinstance(value, dict):
                        # Convert inner dictionary to use PatternPurpose
                        purpose_dict: Dict[PatternPurpose, Dict[str, QueryPattern]] = {}
                        for purpose_key, patterns in value.items():
                            if isinstance(purpose_key, str):
                                try:
                                    purpose_enum = PatternPurpose[purpose_key.upper()]
                                    purpose_dict[purpose_enum] = patterns
                                except KeyError:
                                    logger.warning(f"Could not convert key '{purpose_key}' to PatternPurpose enum")
                            else:
                                purpose_dict[purpose_key] = patterns
                        result[enum_key] = purpose_dict
            except KeyError:
                logger.warning(f"Could not convert key '{key}' to PatternCategory enum")
        else:
            # Key is already an enum
            result[key] = value
    
    return result

def create_pattern(
    name: str,
    pattern: str,
    category: PatternCategory,
    purpose: PatternPurpose,
    language_id: str,
    extract: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    confidence: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None
) -> QueryPattern:
    """Create a QueryPattern instance with validation.
    
    Args:
        name: Pattern name
        pattern: Pattern definition (tree-sitter query or regex)
        category: Pattern category
        purpose: Pattern purpose
        language_id: Target language ID
        extract: Optional extraction function
        confidence: Pattern confidence score
        metadata: Optional metadata dictionary
        
    Returns:
        Validated QueryPattern instance
    """
    pattern_obj = QueryPattern(
        name=name,
        pattern=pattern,
        category=category,
        purpose=purpose,
        language_id=language_id,
        extract=extract,
        confidence=confidence,
        metadata=metadata or {}
    )
    
    if not validate_pattern(pattern_obj):
        raise ValueError(f"Invalid pattern configuration for {name}")
        
    return pattern_obj

def validate_pattern(pattern: QueryPattern) -> bool:
    """Validate a QueryPattern instance.
    
    Args:
        pattern: Pattern to validate
        
    Returns:
        True if pattern is valid
    """
    # Check required fields
    required_fields = ["name", "pattern", "category", "purpose", "language_id"]
    if not all(hasattr(pattern, field) for field in required_fields):
        return False
        
    # Validate field values
    if not pattern.name or not isinstance(pattern.name, str):
        return False
    if not pattern.pattern or not isinstance(pattern.pattern, str):
        return False
    if not isinstance(pattern.category, PatternCategory):
        return False
    if not isinstance(pattern.purpose, PatternPurpose):
        return False
    if not pattern.language_id or not isinstance(pattern.language_id, str):
        return False
        
    return True

def is_language_supported(language_id: str) -> bool:
    """Check if a language is supported by tree-sitter or custom parsers.
    
    Args:
        language_id: Language identifier
        
    Returns:
        True if language is supported
    """
    normalized = normalize_language_name(language_id)
    return normalized in SupportedLanguage.__args__ or normalized in CUSTOM_PARSER_CLASSES

def get_parser_type_for_language(language_id: str) -> str:
    """Get parser type for a language.
    
    Args:
        language_id: Language identifier
        
    Returns:
        'tree-sitter', 'custom', or 'unknown'
    """
    normalized = normalize_language_name(language_id)
    if normalized in CUSTOM_PARSER_CLASSES:
        return 'custom'
    elif normalized in SupportedLanguage.__args__:
        return 'tree-sitter'
    return 'unknown'

def get_patterns_for_language(language: str) -> Dict[PatternCategory, Dict[PatternPurpose, Dict[str, QueryPattern]]]:
    """
    Get query patterns for the specified language.
    
    Args:
        language: The language to get patterns for
        
    Returns:
        Dictionary of patterns by category or empty dict if none found
    """
    language_id = normalize_language_name(language)
    
    # Check if patterns are already loaded
    if language_id in _pattern_registry:
        return _pattern_registry[language_id]
    
    # Load patterns dynamically
    pattern_module = get_pattern_module(language_id)
    
    if pattern_module and hasattr(pattern_module, "PATTERNS"):
        patterns = _ensure_pattern_category_keys(pattern_module.PATTERNS)
        
        # Validate all patterns
        for category in patterns:
            for purpose in patterns[category]:
                for name, pattern in patterns[category][purpose].items():
                    if not validate_pattern(pattern):
                        log(f"Invalid pattern {name} for {language_id}", level="warning")
                        del patterns[category][purpose][name]
        
        _pattern_registry[language_id] = patterns
        return patterns
    
    # No patterns found for this language
    _pattern_registry[language_id] = {}
    return {}

def get_typed_patterns_for_language(language: str) -> Dict[PatternCategory, Dict[PatternPurpose, Dict[str, QueryPattern]]]:
    """
    Get tree-sitter query patterns for the specified language with type annotations.
    This is a wrapper around get_patterns_for_language that ensures keys are PatternCategory enums.
    
    Args:
        language: The language to get patterns for
        
    Returns:
        Dictionary of patterns by category with PatternCategory enum keys
    """
    patterns = get_patterns_for_language(language)
    return patterns  # Already properly typed by get_patterns_for_language

def register_common_patterns() -> Dict[PatternCategory, Dict[PatternPurpose, Dict[str, QueryPattern]]]:
    """
    Register common patterns that apply to multiple languages.
    
    Returns:
        Dictionary of registered patterns
    """
    try:
        # Import common patterns
        from parsers.query_patterns.common import COMMON_PATTERNS
        return _ensure_pattern_category_keys(COMMON_PATTERNS)
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

async def initialize_pattern_system() -> None:
    """Initialize the pattern system by preloading common patterns."""
    global _initialized
    
    try:
        # Update health status
        await global_health_monitor.update_component_status(
            "pattern_system",
            ComponentStatus.INITIALIZING,
            details={"stage": "starting"}
        )
        
        # Register caches with coordinator
        await cache_coordinator.register_cache("pattern_cache", _pattern_cache)
        await cache_coordinator.register_cache("validation_cache", _validation_cache)
        
        # Initialize cache analytics
        analytics = await get_cache_analytics()
        analytics.register_warmup_function(
            "pattern_cache",
            _warmup_pattern_cache
        )
        
        # Register common patterns
        patterns = register_common_patterns()
        
        # Initialize error audit
        await ErrorAudit.analyze_codebase("parsers/query_patterns")
        
        _initialized = True
        await log("Pattern system initialized", level="info")
        
        # Update final status
        await global_health_monitor.update_component_status(
            "pattern_system",
            ComponentStatus.HEALTHY,
            details={
                "stage": "complete",
                "common_patterns": len(patterns)
            }
        )
        
    except Exception as e:
        await log(f"Error initializing pattern system: {e}", level="error")
        await global_health_monitor.update_component_status(
            "pattern_system",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"initialization_error": str(e)}
        )
        raise

async def _warmup_pattern_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for pattern cache."""
    results = {}
    for key in keys:
        try:
            # Load common patterns for warmup
            patterns = register_common_patterns()
            if patterns:
                results[key] = patterns
        except Exception as e:
            await log(f"Error warming up pattern cache for {key}: {e}", level="warning")
    return results

async def cleanup_pattern_system() -> None:
    """Clean up pattern system resources."""
    try:
        # Update status
        await global_health_monitor.update_component_status(
            "pattern_system",
            ComponentStatus.SHUTTING_DOWN,
            details={"stage": "starting"}
        )
        
        # Clean up caches
        await cache_coordinator.unregister_cache("pattern_cache")
        await cache_coordinator.unregister_cache("validation_cache")
        
        # Save error audit report
        await ErrorAudit.save_report()
        
        # Clean up pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*_pending_tasks, return_exceptions=True)
            _pending_tasks.clear()
        
        await log("Pattern system cleaned up", level="info")
        
        # Update final status
        await global_health_monitor.update_component_status(
            "pattern_system",
            ComponentStatus.SHUTDOWN,
            details={"cleanup": "successful"}
        )
        
    except Exception as e:
        await log(f"Error cleaning up pattern system: {e}", level="error")
        await global_health_monitor.update_component_status(
            "pattern_system",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"cleanup_error": str(e)}
        )

@handle_async_errors
async def get_patterns_for_language(language_id: str) -> Optional[Dict[PatternCategory, Dict[PatternPurpose, Dict[str, QueryPattern]]]]:
    """Get patterns for a specific language with caching and error handling."""
    if not _initialized:
        await initialize_pattern_system()
    
    async with request_cache_context() as cache:
        # Check request cache first
        cache_key = f"patterns:{language_id}"
        cached_patterns = await cache.get(cache_key)
        if cached_patterns:
            return cached_patterns
        
        # Check pattern cache
        cached_patterns = await _pattern_cache.get_async(cache_key)
        if cached_patterns:
            await cache.set(cache_key, cached_patterns)
            return cached_patterns
        
        # Load patterns
        with monitor_operation("load_patterns", "pattern_system"):
            patterns = None
            module = globals().get(language_id)
            if module:
                if hasattr(module, 'get_patterns'):
                    task = asyncio.create_task(module.get_patterns())
                    _pending_tasks.add(task)
                    try:
                        patterns = await task
                    finally:
                        _pending_tasks.remove(task)
                elif hasattr(module, 'PATTERNS'):
                    patterns = _ensure_pattern_category_keys(module.PATTERNS)
            
            if patterns:
                # Cache patterns
                await _pattern_cache.set_async(cache_key, patterns)
                await cache.set(cache_key, patterns)
            
            return patterns

@handle_async_errors
async def validate_pattern(pattern: QueryPattern, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a pattern with caching and error handling."""
    cache_key = f"validation:{pattern.name}:{hash(pattern.pattern)}"
    
    # Check validation cache
    cached_result = await _validation_cache.get_async(cache_key)
    if cached_result:
        return cached_result["is_valid"], cached_result["errors"]
    
    errors = []
    is_valid = True
    
    try:
        # Validate pattern
        if not pattern.name or not isinstance(pattern.name, str):
            errors.append("Invalid pattern name")
            is_valid = False
        if not pattern.pattern or not isinstance(pattern.pattern, str):
            errors.append("Invalid pattern definition")
            is_valid = False
        if not isinstance(pattern.category, PatternCategory):
            errors.append("Invalid pattern category")
            is_valid = False
        if not isinstance(pattern.purpose, PatternPurpose):
            errors.append("Invalid pattern purpose")
            is_valid = False
        if not pattern.language_id or not isinstance(pattern.language_id, str):
            errors.append("Invalid language ID")
            is_valid = False
            
        # Cache validation result
        result = {
            "is_valid": is_valid,
            "errors": errors
        }
        await _validation_cache.set_async(cache_key, result)
        
        return is_valid, errors
        
    except Exception as e:
        await log(f"Error validating pattern: {e}", level="error")
        return False, [str(e)]

# Export key functions
__all__ = [
    'initialize_pattern_system',
    'cleanup_pattern_system',
    'get_patterns_for_language',
    'validate_pattern'
]

async def validate_all_patterns(patterns: List[Dict[str, Any]], language_id: Optional[str] = None) -> Dict[str, Any]:
    """Validate all patterns for all languages or a specific language.
    
    Args:
        patterns: List of patterns to validate
        language_id: Optional language ID to filter patterns
        
    Returns:
        Dictionary containing validation results and statistics
    """
    from parsers.pattern_processor import pattern_processor  # Import here to avoid circular import
    
    validation_results = {
        "valid_patterns": [],
        "invalid_patterns": [],
        "validation_time": 0,
        "stats": {
            "total": 0,
            "valid": 0,
            "invalid": 0
        }
    }
    
    start_time = time.time()
    
    for pattern in patterns:
        # Skip if language_id is specified and doesn't match
        if language_id and pattern.get("language_id") != language_id:
            continue
        
        validation_results["stats"]["total"] += 1
        
        # Create ProcessedPattern instance
        from parsers.models import ProcessedPattern  # Import here to avoid circular import
        processed_pattern = ProcessedPattern(
            pattern_name=pattern["name"],
            category=pattern.get("category"),
            purpose=pattern.get("purpose"),
            content=pattern.get("pattern"),
            metadata=pattern.get("metadata", {})
        )
        
        # Validate pattern
        is_valid, errors = await pattern_processor.validate_pattern(
            processed_pattern,
            {"language": pattern.get("language_id", "unknown")}
        )
        
        if is_valid:
            validation_results["valid_patterns"].append({
                "pattern": pattern["name"],
                "language": pattern.get("language_id", "unknown")
            })
            validation_results["stats"]["valid"] += 1
        else:
            validation_results["invalid_patterns"].append({
                "pattern": pattern["name"],
                "language": pattern.get("language_id", "unknown"),
                "errors": errors
            })
            validation_results["stats"]["invalid"] += 1
    
    validation_results["validation_time"] = time.time() - start_time
    
    return validation_results

async def report_validation_results(results: Dict[str, Any]) -> str:
    """Generate a human-readable report of pattern validation results.
    
    Args:
        results: Validation results from validate_all_patterns
        
    Returns:
        Formatted string containing the validation report
    """
    report = []
    report.append("Pattern Validation Report")
    report.append("=" * 25)
    report.append("")
    
    # Add statistics
    report.append("Statistics:")
    report.append(f"- Total patterns: {results['stats']['total']}")
    report.append(f"- Valid patterns: {results['stats']['valid']}")
    report.append(f"- Invalid patterns: {results['stats']['invalid']}")
    report.append(f"- Validation time: {results['validation_time']:.2f}s")
    report.append("")
    
    # Add invalid patterns if any
    if results["invalid_patterns"]:
        report.append("Invalid Patterns:")
        for pattern in results["invalid_patterns"]:
            report.append(f"- {pattern['pattern']} ({pattern['language']}):")
            for error in pattern["errors"]:
                report.append(f"  - {error}")
        report.append("")
    
    return "\n".join(report)