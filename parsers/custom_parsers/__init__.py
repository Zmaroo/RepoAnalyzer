"""Custom parser implementations.

This module provides custom parser implementations for languages that don't have
tree-sitter support or where a custom implementation is preferred.

Each parser must:
1. Inherit from BaseParser and CustomParserMixin
2. Implement parse() method
3. Handle initialization and cleanup
4. Support async operations
5. Support caching through CustomParserMixin
6. Support AI capabilities through AIParserInterface
7. Support proper node type handling and pattern relationships
"""

# Define CUSTOM_PARSER_CLASSES at module level before imports
CUSTOM_PARSER_CLASSES = set()

import asyncio
from typing import Dict, Type, Set
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.shutdown import register_shutdown_handler
from parsers.base_parser import BaseParser
from parsers.types import (
    FileType, ParserType, PatternCategory, PatternType,
    FeatureCategory, PatternRelationType
)
from .base_imports import CustomParserMixin
from parsers.pattern_processor import PatternProcessor
from parsers.ai_pattern_processor import AIPatternProcessor
from parsers.language_config import get_language_config
from parsers.language_support import get_language_support
from parsers.file_classification import get_file_classifier
from parsers.block_extractor import get_block_extractor
from parsers.pattern_processor import get_pattern_processor
from parsers.ai_pattern_processor import get_ai_pattern_processor
from parsers.unified_parser import get_unified_parser
from utils.health_monitor import global_health_monitor, ComponentStatus
from utils.error_handling import ProcessingError, handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.cache_analytics import get_cache_analytics
from utils.cache import UnifiedCache
from utils.cache import cache_coordinator
from utils.async_runner import submit_async_task
from db.transaction import get_transaction_coordinator, transaction_scope

# Import all custom parser classes
from .custom_asciidoc_parser import AsciidocParser
from .custom_cobalt_parser import CobaltParser
from .custom_editorconfig_parser import EditorconfigParser
from .custom_ini_parser import IniParser
from .custom_plaintext_parser import PlaintextParser

# Dictionary to store custom parser classes
CUSTOM_PARSER_CLASSES: Dict[str, Type[BaseParser]] = {}

def _init_custom_parser_classes():
    """Initialize the CUSTOM_PARSER_CLASSES dictionary."""
    CUSTOM_PARSER_CLASSES.update({
        'asciidoc': AsciidocParser,
        'cobalt': CobaltParser,
        'editorconfig': EditorconfigParser,
        'ini': IniParser,
        'plaintext': PlaintextParser
    })

# Initialize when module is imported
_init_custom_parser_classes()

def get_custom_parser_classes() -> Set[str]:
    """Get the set of available custom parser language IDs."""
    return set(CUSTOM_PARSER_CLASSES.keys())

@handle_async_errors(error_types=(Exception,))
async def initialize_custom_parsers():
    """Initialize all custom parsers."""
    try:
        # Update health status
        await global_health_monitor.update_component_status(
            "custom_parsers",
            ComponentStatus.INITIALIZING,
            details={"stage": "starting"}
        )
        
        # Wait for database initialization
        while not await get_transaction_coordinator().is_ready():
            await asyncio.sleep(0.1)
        
        for language_id, parser_class in CUSTOM_PARSER_CLASSES.items():
            try:
                # Submit parser creation through async_runner
                parser_task = submit_async_task(
                    parser_class.create(
                        language_id=language_id,
                        file_type=FileType.CODE,
                        parser_type=ParserType.CUSTOM
                    )
                )
                parser = await asyncio.wrap_future(parser_task)
                await log(f"Initialized custom parser for {language_id}", level="info")
                
                # Initialize cache with proper configuration
                parser._cache = UnifiedCache(
                    f"custom_parser_{language_id}",
                    eviction_policy="lru",
                    max_size=1000,
                    ttl=3600  # 1 hour TTL
                )
                
                # Submit cache registration through async_runner
                cache_task = submit_async_task(
                    cache_coordinator.register_cache(parser._cache)
                )
                await asyncio.wrap_future(cache_task)
                
                # Register cache analytics
                analytics = await get_cache_analytics()
                analytics.register_warmup_function(
                    f"custom_parser_{language_id}",
                    parser._warmup_cache
                )
                
                # Initialize node types through async_runner
                node_task = submit_async_task(parser._initialize_node_types())
                await asyncio.wrap_future(node_task)
                
                # Initialize pattern relationships through async_runner
                pattern_task = submit_async_task(parser._initialize_pattern_relationships())
                await asyncio.wrap_future(pattern_task)
                
            except Exception as e:
                await log(f"Failed to initialize custom parser for {language_id}: {e}", level="error")
                await global_health_monitor.update_component_status(
                    "custom_parsers",
                    ComponentStatus.DEGRADED,
                    error=True,
                    details={
                        "parser": language_id,
                        "error": str(e)
                    }
                )
        
        # Update final status
        await global_health_monitor.update_component_status(
            "custom_parsers",
            ComponentStatus.HEALTHY,
            details={"stage": "complete"}
        )
        
    except Exception as e:
        await log(f"Error in custom parser initialization: {e}", level="error")
        await global_health_monitor.update_component_status(
            "custom_parsers",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"error": str(e)}
        )
        raise

async def cleanup_custom_parsers():
    """Clean up all custom parsers."""
    try:
        # Update status
        await global_health_monitor.update_component_status(
            "custom_parsers",
            ComponentStatus.SHUTTING_DOWN,
            details={"stage": "starting"}
        )
        
        for language_id, parser_class in CUSTOM_PARSER_CLASSES.items():
            try:
                # Submit parser creation through async_runner
                parser_task = submit_async_task(
                    parser_class.create(
                        language_id=language_id,
                        file_type=FileType.CODE,
                        parser_type=ParserType.CUSTOM
                    )
                )
                parser = await asyncio.wrap_future(parser_task)
                
                # Clean up cache
                if parser._cache:
                    cache_task = submit_async_task(
                        cache_coordinator.unregister_cache(f"custom_parser_{language_id}")
                    )
                    await asyncio.wrap_future(cache_task)
                    parser._cache = None
                
                # Clean up node types
                node_task = submit_async_task(parser._cleanup_node_types())
                await asyncio.wrap_future(node_task)
                
                # Clean up pattern relationships
                pattern_task = submit_async_task(parser._cleanup_pattern_relationships())
                await asyncio.wrap_future(pattern_task)
                
                # Submit cleanup through async_runner
                cleanup_task = submit_async_task(parser.cleanup())
                await asyncio.wrap_future(cleanup_task)
                
                await log(f"Cleaned up custom parser for {language_id}", level="info")
                
            except Exception as e:
                await log(f"Failed to clean up custom parser for {language_id}: {e}", level="error")
                await global_health_monitor.update_component_status(
                    "custom_parsers",
                    ComponentStatus.DEGRADED,
                    error=True,
                    details={
                        "parser": language_id,
                        "cleanup_error": str(e)
                    }
                )
        
        # Update final status
        await global_health_monitor.update_component_status(
            "custom_parsers",
            ComponentStatus.SHUTDOWN,
            details={"cleanup": "successful"}
        )
        
    except Exception as e:
        await log(f"Error cleaning up custom parsers: {e}", level="error")
        await global_health_monitor.update_component_status(
            "custom_parsers",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"cleanup_error": str(e)}
        )
        raise ProcessingError(f"Failed to cleanup custom parsers: {e}")

# Register cleanup handler
register_shutdown_handler(cleanup_custom_parsers)

# Export all parser classes and initialization functions
__all__ = [
    'CUSTOM_PARSER_CLASSES',
    'get_custom_parser_classes',
    'initialize_custom_parsers',
    'cleanup_custom_parsers',
    'CustomParserMixin',
    'AsciidocParser',
    'CobaltParser',
    'EditorconfigParser',
    'IniParser',
    'PlaintextParser'
] 