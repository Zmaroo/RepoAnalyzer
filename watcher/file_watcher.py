"""File watcher implementation."""

import os
import asyncio
import fnmatch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from utils.logger import log
from indexer.unified_indexer import ProcessingCoordinator
from indexer.clone_and_index import get_or_create_repo
from indexer.file_utils import is_binary_file, is_processable_file, get_relative_path
from parsers.models import FileType, FileClassification
from parsers.language_support import language_registry
from parsers.models import get_file_classification
from db.upsert_ops import upsert_code_snippet, upsert_doc
from db.neo4j_ops import auto_reinvoke_projection_once

class AsyncFileChangeHandler(FileSystemEventHandler):
    def __init__(self, on_change):
        self.on_change = on_change

    def on_modified(self, event):
        if not event.is_directory:
            asyncio.create_task(self.on_change(event.src_path))

async def watch_directory(directory: str, repo_id: int, on_change):
    """
    Asynchronously watch a directory and invoke the provided callback on changes.
    
    Args:
        directory: The directory to watch.
        repo_id: Repository ID associated with the files.
        on_change: Asynchronous callback to execute on file changes.
    """
    event_handler = AsyncFileChangeHandler(on_change)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=True)
    observer.start()
    log(f"Started watching directory: {directory}", level="info")
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        log("File watcher cancelled.", level="warning")
    finally:
        observer.stop()
        observer.join()

def start_file_watcher(path: str = ".") -> None:
    """Start the file watcher in the current directory."""
    async def async_main():
        try:
            repo_name = os.path.basename(os.getcwd())
            repo_id = await get_or_create_repo(repo_name, repo_type="active")
            log(f"Starting file watcher for repository: {repo_name} (id: {repo_id})")
            await watch_directory(path, repo_id, lambda file_path: asyncio.create_task(handle_file_change(file_path, repo_id)))
        except Exception as e:
            log(f"Error in file watcher: {e}", level="error")

    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        log("File watcher stopped by user", level="info")