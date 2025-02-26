"""
Query patterns for various languages used for pattern matching and feature extraction.
"""

from typing import Dict, Any, List, Optional, Tuple
from parsers.types import QueryPattern, PatternCategory
from parsers.pattern_processor import pattern_processor
from utils.logger import log
import importlib
import logging

__all__ = ["pattern_processor", "QueryPattern", "PatternCategory"]

# Global variable to store modules with patterns
modules_with_patterns = []

# Function to register patterns for repository learning
def register_repository_learning_patterns():
    """
    Register patterns specifically for repository learning and pattern extraction.
    
    This ensures that all language modules have the necessary patterns for:
    - Code structure pattern extraction
    - Naming convention pattern extraction  
    - Error handling pattern extraction
    - Documentation structure pattern extraction
    - Architecture pattern extraction
    """
    log("Registering repository learning patterns", level="debug")
    
    # Define the base set of modules
    global modules_with_patterns
    modules_with_patterns = []
    
    # Import query pattern modules that have repository learning patterns
    try:
        # Document/config format parsers
        from parsers.query_patterns import (
            markdown, asciidoc, cobalt, editorconfig, env, 
            graphql, html, json, ini, rst, plaintext, 
            xml, toml, yaml
        )
        modules_with_patterns.extend([markdown, asciidoc, cobalt, editorconfig, env, 
                                     graphql, html, json, ini, rst, plaintext, 
                                     xml, toml, yaml])
        log("Loaded document and config format parser patterns", level="debug")
    except ImportError as e:
        log(f"Error loading document format patterns: {e}", level="error")
    
    # Try to import programming language pattern modules
    try:
        # Programming languages with tree-sitter support
        from parsers.query_patterns import (
            python, javascript, typescript, java, cpp, csharp,
            go, rust, kotlin, swift, ruby, scala
        )
        modules_with_patterns.extend([python, javascript, typescript, java, cpp, csharp,
                                     go, rust, kotlin, swift, ruby, scala])
        log("Loaded programming language parser patterns", level="debug")
    except ImportError as e:
        # Continue even if some patterns aren't available
        log(f"Some programming language patterns couldn't be loaded: {e}", level="debug")
    
    # Specialized languages
    try:
        from parsers.query_patterns import (
            sql, bash, css, dockerfile, lua, make
        )
        modules_with_patterns.extend([sql, bash, css, dockerfile, lua, make])
        log("Loaded specialized language parser patterns", level="debug")
    except ImportError as e:
        log(f"Some specialized language patterns couldn't be loaded: {e}", level="debug")
    
    # Count registered patterns
    pattern_count = 0
    repo_learning_count = 0
    
    for module in modules_with_patterns:
        # Check if the module has patterns 
        if hasattr(module, 'PATTERNS'):
            pattern_count += 1
            
        # Check for repository learning patterns specifically
        if hasattr(module, 'REPOSITORY_LEARNING') or any('REPOSITORY_LEARNING' in getattr(module, pat, {}) 
                                                       for pat in ['PATTERNS', module.__name__.upper() + '_PATTERNS']):
            repo_learning_count += 1
    
    log(f"Registered {pattern_count} pattern modules with {repo_learning_count} repository learning pattern modules", level="debug")
    
    # Register modules globally for external access
    return repo_learning_count

# Register patterns on module import
register_repository_learning_patterns()

# Map of language to patterns
_patterns_by_language: Dict[str, Dict[str, QueryPattern]] = {}

def register_patterns(language: str, patterns: Dict[str, QueryPattern]):
    """Register patterns for a language."""
    if language not in _patterns_by_language:
        _patterns_by_language[language] = {}
    _patterns_by_language[language].update(patterns)
    logging.debug(f"Registered {len(patterns)} patterns for {language}")

def get_patterns(language: str) -> Dict[str, QueryPattern]:
    """Get all patterns for a language."""
    return _patterns_by_language.get(language, {})

def get_pattern(language: str, pattern_name: str) -> Optional[QueryPattern]:
    """Get a specific pattern for a language."""
    return _patterns_by_language.get(language, {}).get(pattern_name)

def extract_patterns_for_learning(language: str, content: str) -> List[Dict[str, Any]]:
    """
    Extract patterns from content for repository learning.
    This delegates to the appropriate extract_*_patterns_for_learning function.
    
    Args:
        language: The language/format of the content
        content: The content to extract patterns from
        
    Returns:
        List of extracted patterns with metadata
    """
    try:
        # Find the appropriate module for this language
        module = None
        for m in modules_with_patterns:
            module_language = getattr(m, 'LANGUAGE', None)
            if module_language and module_language.lower() == language.lower():
                module = m
                break
        
        if not module:
            logging.debug(f"No pattern extraction module found for {language}")
            return []
        
        # Look for the appropriate extraction function
        extract_func_name = f"extract_{language.lower()}_patterns_for_learning"
        extract_func = getattr(module, extract_func_name, None)
        
        if not extract_func:
            logging.debug(f"No pattern extraction function '{extract_func_name}' found")
            return []
        
        # Extract patterns
        patterns = extract_func(content)
        logging.debug(f"Extracted {len(patterns)} patterns for {language}")
        return patterns
        
    except Exception as e:
        logging.error(f"Error extracting patterns for {language}: {e}")
        return []

# Initialize - load patterns from all modules
for module in modules_with_patterns:
    language = getattr(module, 'LANGUAGE', None)
    patterns = getattr(module, 'PATTERNS', {})
    if language and patterns:
        register_patterns(language, patterns)

# Allow importing pattern_processor directly
from parsers.pattern_processor import PatternProcessor