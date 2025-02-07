import os
import asyncio
from typing import List, Set, Optional, Callable, Awaitable
import aiofiles
from indexer.file_utils import get_files, is_binary_file
from utils.logger import log

async def async_read_text_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    Asynchronously reads and returns the content of a text file using aiofiles.
    Logs an error and returns an empty string if the file cannot be read.
    """
    try:
        async with aiofiles.open(file_path, "r", encoding=encoding) as f:
            return await f.read()
    except Exception as e:
        log(f"Error asynchronously reading text file {file_path}: {e}", level="error")
        return ""

async def async_get_files(
    dir_path: str, 
    extensions: Set[str], 
    ignore_dirs: Optional[Set[str]] = None
) -> List[str]:
    """
    Asynchronously collects files from dir_path that match the given extensions.
    Wraps the synchronous get_files function in run_in_executor.
    """
    loop = asyncio.get_running_loop()
    files = await loop.run_in_executor(None, get_files, dir_path, extensions, ignore_dirs)
    return files

async def async_process_index_file(
    file_path: str,
    base_path: str,
    repo_id: int,
    file_processor: Callable[[str], Awaitable[Optional[str]]],
    index_function: Callable[[int, str, str], None],
    file_type: str
) -> None:
    """
    Asynchronously processes a file for indexing in a standardized way.

    Parameters:
      file_path: Absolute path of the file to process.
      base_path: Base directory used to compute the relative path.
      repo_id: Identifier of the repository.
      file_processor: Asynchronous function to process the file (e.g., async_read_text_file).
      index_function: Function to upsert the processed file (e.g., upsert_code or upsert_doc).
      file_type: A string indicating the type of file ("code" or "doc") for logging.
    """
    try:
        if is_binary_file(file_path):
            log(f"Skipping binary file asynchronously: {file_path}", level="warning")
            return
        result = await file_processor(file_path)
        if not result:
            log(f"No result from processing asynchronously {file_path}", level="debug")
            return
        rel_path = os.path.relpath(file_path, base_path)
        index_function(repo_id, rel_path, result)
        log(f"Indexed {file_type} file asynchronously: {rel_path}", level="info")
    except Exception as e:
        log(f"Error processing {file_type} file asynchronously {file_path}: {e}", level="error") 