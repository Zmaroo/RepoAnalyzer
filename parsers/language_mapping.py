"""Language mapping and normalization for parsers.

This module handles language detection and parser type selection,
integrating both custom parsers and tree-sitter parsers.
"""

from typing import Dict, Optional, Tuple, Set
import asyncio
from tree_sitter_language_pack import SupportedLanguage
from parsers.types import ParserType
from utils.logger import log
from utils.error_handling import handle_async_errors, ProcessingError
from utils.async_runner import submit_async_task

# Will be populated during initialization
CUSTOM_PARSER_CLASSES: Set[str] = set()
_initialized = False
_lock = asyncio.Lock()

def normalize_language_name(language_id: str) -> str:
    """Normalize a language identifier."""
    return language_id.lower().replace("-", "_").replace(" ", "_")

async def initialize_language_mapping():
    """Initialize language mapping system."""
    global _initialized, CUSTOM_PARSER_CLASSES
    
    if _initialized:
        return
        
    async with _lock:
        if _initialized:
            return
            
        try:
            # Import custom parsers only during initialization
            from parsers.custom_parsers import get_custom_parser_classes
            CUSTOM_PARSER_CLASSES = get_custom_parser_classes()
            
            _initialized = True
            await log("Language mapping initialized", level="info")
        except Exception as e:
            await log(f"Error initializing language mapping: {e}", level="error")
            raise

@handle_async_errors(error_types=ProcessingError)
async def get_parser_type(language_id: str) -> Tuple[ParserType, str]:
    """Get parser type for a language."""
    if not _initialized:
        await initialize_language_mapping()
    
    normalized = normalize_language_name(language_id)
    
    # Custom parsers take precedence
    if normalized in CUSTOM_PARSER_CLASSES:
        return ParserType.CUSTOM, normalized
    
    # Check tree-sitter support
    if normalized in SupportedLanguage.__args__:
        return ParserType.TREE_SITTER, normalized
    
    return ParserType.UNKNOWN, normalized

# Export public interfaces
__all__ = [
    'normalize_language_name',
    'get_parser_type',
    'initialize_language_mapping'
]
