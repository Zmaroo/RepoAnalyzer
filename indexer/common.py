"""
Common utilities and functions shared across the indexer module.
This module helps break circular dependencies.
"""

import os
import asyncio
import aiofiles
from typing import List, Set, Optional, Callable, Awaitable, Any, Dict
from utils.logger import log
from utils.error_handling import handle_async_errors
from functools import wraps

# Deprecated: Use handle_async_errors from utils.error_handling instead
# Keeping this for backward compatibility but marking as deprecated
def async_handle_errors(async_func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """[DEPRECATED] Use handle_async_errors from utils.error_handling instead."""
    from utils.error_handling import handle_async_errors
    return handle_async_errors()(async_func)

@handle_async_errors
async def async_read_file(file_path: str, try_encodings: bool = True) -> Optional[str]:
    """[3.2] Unified file reading with encoding detection.
    
    Flow:
    1. Try UTF-8 first
    2. Fall back to alternative encodings if needed
    3. Handle read errors gracefully
    """
    encodings = ['utf-8']
    if try_encodings:
        encodings.extend(['latin-1', 'cp1252', 'iso-8859-1'])
        
    for encoding in encodings:
        try:
            async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                return await f.read()
        except UnicodeDecodeError:
            if encoding == encodings[-1]:
                log(f"Unable to decode file with any encoding: {file_path}", level="error")
                return None
            continue
        except Exception as e:
            log(f"Error reading file {file_path}: {e}", level="error")
            return None 