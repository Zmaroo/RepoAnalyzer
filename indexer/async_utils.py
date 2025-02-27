import os
import asyncio
from typing import List, Set, Optional, Callable, Awaitable, Any, Dict
import aiofiles
from utils.logger import log
from indexer.file_processor import FileProcessor
from parsers.types import (
    FileType,
    # Other lightweight types (if needed)...
)
from parsers.models import (  # Domain-specific models
    FileClassification,
    ParserResult,
    ExtractedFeatures
)
from functools import wraps

"""[3.0] Asynchronous utilities for file processing.

Flow:
1. Error Handling:
   - Async function decoration
   - Consistent error logging
   - Optional return values

2. File Operations:
   - Async file reading
   - Multiple encoding support
   - Proper resource cleanup

3. Batch Processing:
   - Parallel file processing
   - Progress tracking
   - Resource management
"""

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

@async_handle_errors
async def async_process_index_file(
    file_path: str,
    base_path: str,
    repo_id: int,
    processor: FileProcessor,
    file_type: FileType  # Now using FileType enum from parsers/types
) -> None:
    """Asynchronously process and index a file using FileProcessor"""
    try:
        await processor.process_file(file_path, repo_id, base_path)
    except Exception as e:
        log(f"Error processing file {file_path}: {e}", level="error")

@async_handle_errors
async def batch_process_files(
    files: List[str],
    base_path: str,
    repo_id: int,
    batch_size: int = 10,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> None:
    """[3.3] Enhanced batch processing with progress tracking and error resilience.
    
    Flow:
    1. Initialize processor
    2. Process files in batches
    3. Track progress
    4. Clean up resources
    5. Handle task errors without stopping the entire batch
    """
    processor = FileProcessor()
    total_files = len(files)
    processed = 0
    errors = 0
    
    try:
        for i in range(0, total_files, batch_size):
            batch = files[i:i + batch_size]
            tasks = []
            
            # Create tasks for each file in the batch
            for f in batch:
                task = asyncio.create_task(
                    async_process_index_file(
                        file_path=f,
                        base_path=base_path,
                        repo_id=repo_id,
                        processor=processor,
                        file_type=FileType.CODE  # Use the enum value instead of a string
                    )
                )
                tasks.append(task)
            
            # Wait for all tasks in this batch, handling errors for individual tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Track errors but continue processing
            for result in results:
                if isinstance(result, Exception):
                    log(f"Error in batch processing: {result}", level="error")
                    errors += 1
            
            processed += len(batch)
            if progress_callback:
                progress_callback(processed, total_files)
            
            # Give other tasks a chance to run and avoid CPU hogging
            await asyncio.sleep(0)
            
        log(f"Batch processing completed: {processed} files processed, {errors} errors", 
            level="info" if errors == 0 else "warning")
            
    except asyncio.CancelledError:
        log("Batch processing cancelled", level="warning")
        # Cancel any remaining tasks
        for task in asyncio.all_tasks():
            if task != asyncio.current_task():
                task.cancel()
        raise
    except Exception as e:
        log(f"Unexpected error in batch processing: {e}", level="error")
        raise
    finally:
        processor.clear_cache() 