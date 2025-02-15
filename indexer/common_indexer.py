import asyncio
from typing import Callable, Optional
from utils.logger import log
from indexer.file_utils import get_files, process_index_file, read_text_file, is_binary_file
from indexer.async_utils import async_get_files, async_process_index_file
import os

def index_files(
    repo_path: str,
    repo_id: int,
    extensions: set,
    file_processor: Callable[[str], Optional[str]],
    index_function: Callable[[int, str, str], None],
    file_type: str
) -> None:
    """
    Synchronously indexes files in repo_path.
    """
    files = get_files(repo_path, extensions)
    log(f"Found {len(files)} {file_type} files in [{repo_id}].")
    for file_path in files:
        process_index_file(file_path, repo_path, repo_id, file_processor, index_function, file_type)

async def async_index_files(
    repo_path: str,
    repo_id: int,
    extensions: set,
    file_processor: Callable[[str], Optional[str]],
    index_function: Callable[[int, str, str], None],
    file_type: str,
    wrap_sync: bool = False
) -> None:
    """
    Asynchronously indexes files in repo_path.
    If wrap_sync is True, the file_processor will be wrapped with asyncio.to_thread.
    """
    files = await async_get_files(repo_path, extensions)
    log(f"Found {len(files)} {file_type} files for repository [{repo_id}].")
    tasks = []
    for file_path in files:
        fp = (lambda fp: asyncio.to_thread(file_processor, fp)) if wrap_sync else file_processor
        tasks.append(async_process_index_file(
            file_path=file_path,
            base_path=repo_path,
            repo_id=repo_id,
            file_processor=fp,
            index_function=index_function,
            file_type=file_type
        ))
    await asyncio.gather(*tasks, return_exceptions=True)

async def index_file_async(file_path: str, repo_id: int, base_path: str) -> None:
    """
    Asynchronously indexes a single file.
    
    This function consolidates indexing functionality that was previously duplicated.
    It reads the file and, if successful, logs that the file was processed.
    
    In a complete implementation, this function should:
      - Run language detection (via parsers)
      - Parse the file (e.g., AST extraction)
      - Upsert the processed result into a database.
    """
    if is_binary_file(file_path):
        log(f"Skipping binary file: {file_path}", level="warning")
        return
    try:
        content = read_text_file(file_path)
        if not content:
            log(f"No content from file: {file_path}", level="debug")
            return
        # Compute the relative path for logging purposes.
        relative_path = os.path.relpath(file_path, base_path)
        # TODO: Process the file content (e.g., run detect_language, generate AST, etc.)
        log(f"Indexed file {relative_path} for repo {repo_id}", level="info")
    except Exception as e:
        log(f"Error indexing file {file_path} for repo {repo_id}: {e}", level="error") 