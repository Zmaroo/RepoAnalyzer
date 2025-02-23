import os
import asyncio
from typing import List, Set, Optional, Callable, Awaitable, Any, Dict
import aiofiles
from utils.logger import log
from indexer.file_processor import FileProcessor
from parsers.models import (  # Add imports from models
    FileType,
    FileClassification,
    ParserResult,
    ExtractedFeatures
)

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

def async_handle_errors(async_func):
    """[3.1] Decorator for consistent async error handling."""
    async def wrapper(*args, **kwargs):
        try:
            return await async_func(*args, **kwargs)
        except Exception as e:
            log(f"Async error in function '{async_func.__name__}': {e}", level="error")
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
async def async_read_text_file(file_path: str) -> Optional[str]:
    """Read text file content asynchronously with encoding detection."""
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            return await f.read()
    except UnicodeDecodeError:
        # Try alternative encodings
        encodings = ['latin-1', 'cp1252', 'iso-8859-1']
        for encoding in encodings:
            try:
                async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                    return await f.read()
            except UnicodeDecodeError:
                continue
        log(f"Unable to decode file with any encoding: {file_path}", level="error")
        return None

@async_handle_errors
async def async_process_index_file(
    file_path: str,
    base_path: str,
    repo_id: int,
    processor: FileProcessor,
    file_type: FileType  # Updated to use FileType enum
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
    """[3.3] Enhanced batch processing with progress tracking.
    
    Flow:
    1. Initialize processor
    2. Process files in batches
    3. Track progress
    4. Clean up resources
    """
    processor = FileProcessor()
    total_files = len(files)
    processed = 0
    
    try:
        for i in range(0, total_files, batch_size):
            batch = files[i:i + batch_size]
            tasks = [
                async_process_index_file(
                    file_path=f,
                    base_path=base_path,
                    repo_id=repo_id,
                    processor=processor,
                    file_type="code"
                )
                for f in batch
            ]
            await asyncio.gather(*tasks)
            
            processed += len(batch)
            if progress_callback:
                progress_callback(processed, total_files)
    finally:
        processor.clear_cache() 