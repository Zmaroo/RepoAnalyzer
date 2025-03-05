"""
File classification and language detection module.

This module provides tools for classifying files based on their content and extension,
determining the appropriate parser type, and extracting language information.
"""

import os
import re
from typing import Dict, Optional, Tuple, List, Set, Union, Callable
import asyncio

from parsers.models import FileClassification
from parsers.types import ParserType, FileType
from parsers.language_mapping import (
    # Import mappings
    TREE_SITTER_LANGUAGES,
    CUSTOM_PARSER_LANGUAGES,
    FULL_EXTENSION_MAP,
    FILENAME_MAP,
    BINARY_EXTENSIONS,
    
    # Import functions
    normalize_language_name,
    is_supported_language,
    get_parser_type,
    get_file_type,
    detect_language_from_filename,
    detect_language_from_content,
    detect_language,
    get_complete_language_info,
    get_parser_info_for_language,
    is_binary_extension
)
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.shutdown import register_shutdown_handler

# Track initialization state and tasks
_initialized = False
_pending_tasks: Set[asyncio.Task] = set()

@handle_async_errors(error_types=(Exception,))
async def initialize():
    """Initialize file classification resources."""
    global _initialized
    if not _initialized:
        try:
            async with AsyncErrorBoundary("file_classification_initialization"):
                # No special initialization needed yet
                _initialized = True
                log("File classification initialized", level="info")
        except Exception as e:
            log(f"Error initializing file classification: {e}", level="error")
            raise

@handle_async_errors(error_types=(Exception,))
async def classify_file(file_path: str, content: Optional[str] = None) -> FileClassification:
    """
    Classify a file based on its path and optionally its content.
    
    Args:
        file_path: Path to the file
        content: Optional file content for more accurate classification
        
    Returns:
        FileClassification object with parser type and language information
    """
    if not _initialized:
        await initialize()
        
    async with AsyncErrorBoundary("classify_file"):
        # Use the enhanced language detection with confidence score
        task = asyncio.create_task(detect_language(file_path, content))
        _pending_tasks.add(task)
        try:
            language_id, confidence = await task
        finally:
            _pending_tasks.remove(task)
        
        # Log detection confidence if it's low
        if confidence < 0.5:
            log(f"Low confidence ({confidence:.2f}) language detection for {file_path}: {language_id}", level="debug")
        
        # Get parser info for the detected language
        task = asyncio.create_task(get_parser_info_for_language(language_id))
        _pending_tasks.add(task)
        try:
            parser_info = await task
        finally:
            _pending_tasks.remove(task)
        
        # Check if file is binary
        task = asyncio.create_task(_is_likely_binary(file_path, content))
        _pending_tasks.add(task)
        try:
            is_binary = await task
        finally:
            _pending_tasks.remove(task)
        
        # Create classification
        classification = FileClassification(
            file_path=file_path,
            language_id=parser_info["language_id"],
            parser_type=parser_info["parser_type"],
            file_type=parser_info["file_type"],
            is_binary=is_binary,
        )
        
        return classification

@handle_async_errors(error_types=(Exception,))
async def _is_likely_binary(file_path: str, content: Optional[str] = None) -> bool:
    """
    Determine if a file is likely binary.
    
    Args:
        file_path: Path to the file
        content: Optional file content
        
    Returns:
        True if likely binary, False otherwise
    """
    # Check extension first using language_mapping function
    _, ext = os.path.splitext(file_path)
    if is_binary_extension(ext):
        return True
    
    # If content provided, check for null bytes
    if content:
        # Check sample of content for null bytes
        sample = content[:4096] if len(content) > 4096 else content
        if '\0' in sample:
            return True
    
    return False

@handle_async_errors(error_types=(Exception,))
async def get_supported_languages() -> Dict[str, ParserType]:
    """
    Get a dictionary of all supported languages and their parser types.
    Returns:
        Dictionary with language IDs as keys and parser types as values
    """
    # Use the function from language_mapping.py
    from parsers.language_mapping import get_supported_languages as get_langs
    task = asyncio.create_task(get_langs())
    _pending_tasks.add(task)
    try:
        return await task
    finally:
        _pending_tasks.remove(task)

@handle_async_errors(error_types=(Exception,))
async def get_supported_extensions() -> Dict[str, str]:
    """
    Get a dictionary of all supported file extensions and their corresponding languages.
    Returns:
        Dictionary with extensions as keys and language IDs as values
    """
    # Use the function from language_mapping.py
    from parsers.language_mapping import get_supported_extensions as get_exts
    task = asyncio.create_task(get_exts())
    _pending_tasks.add(task)
    try:
        return await task
    finally:
        _pending_tasks.remove(task)

async def cleanup():
    """Clean up file classification resources."""
    global _initialized
    try:
        # Clean up any pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*_pending_tasks, return_exceptions=True)
            _pending_tasks.clear()
        
        _initialized = False
        log("File classification cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up file classification: {e}", level="error")

# Register cleanup handler
register_shutdown_handler(cleanup) 