"""Parser module initialization and lifecycle management.

This module provides centralized initialization and cleanup for all parser components:
1. Language registry
2. Pattern processor
3. Unified parser
4. Tree-sitter parsers
5. Custom parsers
"""

from typing import List, Set
import asyncio
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task, get_loop

# Export the core parser modules and additional custom parser registrations
__all__ = [
    "language_support",
    "language_mapping",
    "feature_extractor",
    "pattern_processor",
    "file_classification",  # for domain models (e.g. FileClassification)
    "types",
    "models",
    "base_parser",
    "tree_sitter_parser",
    "unified_parser",
    "initialize_parsers",
    "cleanup_parsers"
]

# Import after __all__ definition to avoid circular imports
from .language_support import language_registry
from .pattern_processor import pattern_processor
from .unified_parser import unified_parser

# Track initialization state
_initialized = False
_pending_tasks: Set[asyncio.Future] = set()

@handle_async_errors(error_types=(Exception,))
async def initialize_parsers():
    """Initialize all parser components in the correct order."""
    global _initialized
    
    if _initialized:
        return
    
    try:
        async with AsyncErrorBoundary("parser initialization"):
            # Initialize language registry first
            future = submit_async_task(language_registry.initialize())
            _pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
            finally:
                _pending_tasks.remove(future)
            
            # Initialize pattern processor
            future = submit_async_task(pattern_processor.initialize())
            _pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
            finally:
                _pending_tasks.remove(future)
            
            # Initialize unified parser last
            future = submit_async_task(unified_parser.initialize())
            _pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
            finally:
                _pending_tasks.remove(future)
            
            _initialized = True
            log("Parser components initialized successfully", level="info")
    except Exception as e:
        log(f"Error initializing parser components: {e}", level="error")
        raise

async def cleanup_parsers():
    """Clean up all parser resources."""
    global _initialized
    
    try:
        # Clean up in reverse initialization order
        cleanup_tasks = []
        
        # Clean up unified parser
        future = submit_async_task(unified_parser.cleanup())
        cleanup_tasks.append(future)
        
        # Clean up pattern processor
        future = submit_async_task(pattern_processor.cleanup())
        cleanup_tasks.append(future)
        
        # Clean up language registry
        future = submit_async_task(language_registry.cleanup())
        cleanup_tasks.append(future)
        
        # Wait for all cleanup tasks
        await asyncio.gather(*[asyncio.wrap_future(f) for f in cleanup_tasks], return_exceptions=True)
        
        # Clean up any remaining pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*[asyncio.wrap_future(f) for f in _pending_tasks], return_exceptions=True)
            _pending_tasks.clear()
        
        _initialized = False
        log("Parser components cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up parser components: {e}", level="error")

# Register cleanup handler
register_shutdown_handler(cleanup_parsers)

# Optionally, if you need to expose custom parser classes for external modules:
from .custom_parsers import CUSTOM_PARSER_CLASSES
__all__.append("CUSTOM_PARSER_CLASSES") 