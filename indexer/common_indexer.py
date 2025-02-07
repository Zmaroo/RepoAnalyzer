import asyncio
from typing import Callable, Optional
from utils.logger import log
from indexer.file_utils import get_files, process_index_file
from indexer.async_utils import async_get_files, async_process_index_file

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