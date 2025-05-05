"""
Common utilities and functions shared across the indexer module.
This module helps break circular dependencies.
"""

import os
import asyncio
import aiofiles
from typing import List, Set, Optional, Callable, Awaitable, Any, Dict
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ErrorSeverity,
    ProcessingError,
    DatabaseError
)
from config import FileConfig

# Initialize file config
file_config = FileConfig()

# Re-export handle_async_errors for backward compatibility
handle_errors = handle_async_errors

@handle_async_errors()
async def async_read_file(file_path: str, try_encodings: bool = True) -> Optional[str]:
    """[3.2] Unified file reading with encoding detection.
    
    Flow:
    1. Try UTF-8 first
    2. Fall back to alternative encodings if needed
    3. Handle read errors gracefully
    
    Args:
        file_path: Path to the file to read
        try_encodings: Whether to try multiple encodings
        
    Returns:
        File contents as string or None if reading fails
    """
    async with AsyncErrorBoundary(f"reading file {file_path}", severity=ErrorSeverity.ERROR):
        # Check file size first
        try:
            if os.path.getsize(file_path) > file_config.max_file_size:
                log(f"File too large to process: {file_path}", level="warning")
                return None
        except OSError as e:
            log(f"Error checking file size: {e}", level="error")
            return None
        
        # Try encodings in order
        encodings = file_config.supported_encodings if try_encodings else ['utf-8']
        
        for encoding in encodings:
            try:
                async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                    content = await f.read()
                    # Validate content is actually text
                    content.encode(encoding)
                    return content
            except UnicodeDecodeError:
                if encoding == encodings[-1]:
                    log(f"Unable to decode file with any encoding: {file_path}", level="error")
                    return None
                continue
            except UnicodeEncodeError:
                # Content wasn't actually text
                if encoding == encodings[-1]:
                    log(f"File contains invalid text: {file_path}", level="error")
                    return None
                continue
            except Exception as e:
                log(f"Error reading file {file_path}: {e}", level="error")
                return None
        
        return None 