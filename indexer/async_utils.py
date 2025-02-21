import os
import asyncio
from typing import List, Set, Optional, Callable, Awaitable, Any, Dict
import aiofiles
from utils.logger import log
from indexer.file_processor import FileProcessor

def async_handle_errors(async_func):
    """
    A decorator for async functions to catch and log exceptions.
    The decorator logs the error and returns None.
    """
    async def wrapper(*args, **kwargs):
        try:
            return await async_func(*args, **kwargs)
        except Exception as e:
            log(f"Async error in function '{async_func.__name__}': {e}", level="error")
            return None
    return wrapper

@async_handle_errors
async def async_read_file(file_path: str) -> Optional[str]:
    """Read file content asynchronously."""
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            return await f.read()
    except UnicodeDecodeError:
        log(f"Binary or invalid encoding in file: {file_path}", level="debug")
        return None
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
    file_type: str
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
    batch_size: int = 10
) -> None:
    """Process files in batches using FileProcessor"""
    processor = FileProcessor()
    try:
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            tasks = [
                async_process_index_file(
                    file_path=f,
                    base_path=base_path,
                    repo_id=repo_id,
                    processor=processor,
                    file_type="code"  # FileProcessor handles type internally
                )
                for f in batch
            ]
            await asyncio.gather(*tasks)
    finally:
        processor.clear_cache() 