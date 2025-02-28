"""
Common utilities and functions shared across the indexer module.
This module helps break circular dependencies.
"""

import os
import asyncio
import aiofiles
from typing import List, Set, Optional, Callable, Awaitable, Any, Dict
from utils.logger import log
from functools import wraps

def async_handle_errors(async_func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """[3.1] Decorator for consistent async error handling."""
    import inspect
    from typing import get_type_hints, List, Dict
    
    @wraps(async_func)
    async def wrapper(*args, **kwargs):
        try:
            return await async_func(*args, **kwargs)
        except Exception as e:
            log(f"Async error in function '{async_func.__name__}': {e}", level="error")
            
            # Try to determine appropriate return type based on function annotation
            try:
                return_type_hints = get_type_hints(async_func)
                if 'return' in return_type_hints:
                    return_hint = return_type_hints['return']
                    # Handle various common return types
                    origin = getattr(return_hint, '__origin__', None)
                    if origin is list or (hasattr(return_hint, '_name') and return_hint._name == 'List'):
                        return []
                    elif origin is dict or (hasattr(return_hint, '_name') and return_hint._name == 'Dict'):
                        return {}
                    elif return_hint is bool or return_hint == bool:
                        return False
                    elif inspect.isclass(return_hint) and issubclass(return_hint, (list, List)):
                        return []
                    elif inspect.isclass(return_hint) and issubclass(return_hint, (dict, Dict)):
                        return {}
            except Exception as type_error:
                log(f"Error determining return type for {async_func.__name__}: {type_error}", level="debug")
            
            # Default fallback
            return None
    return wrapper

@async_handle_errors
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