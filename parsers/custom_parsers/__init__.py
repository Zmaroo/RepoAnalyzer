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
"""

import asyncio
from typing import Dict, Type, Set
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.shutdown import register_shutdown_handler
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType
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
from utils.error_handling import ProcessingError
from utils.cache_analytics import get_cache_analytics

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
    for language_id, parser_class in CUSTOM_PARSER_CLASSES.items():
        try:
            parser = await parser_class.create(
                language_id=language_id,
                file_type=FileType.CODE,
                parser_type=ParserType.CUSTOM
            )
            await log(f"Initialized custom parser for {language_id}", level="info")
        except Exception as e:
            await log(f"Failed to initialize custom parser for {language_id}: {e}", level="error")

async def cleanup_custom_parsers():
    """Clean up all custom parsers."""
    for language_id, parser_class in CUSTOM_PARSER_CLASSES.items():
        try:
            parser = await parser_class.create(
                language_id=language_id,
                file_type=FileType.CODE,
                parser_type=ParserType.CUSTOM
            )
            await parser.cleanup()
            await log(f"Cleaned up custom parser for {language_id}", level="info")
        except Exception as e:
            await log(f"Failed to clean up custom parser for {language_id}: {e}", level="error")

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
    'EnvParser',
    'IniParser',
    'PlaintextParser'
] 