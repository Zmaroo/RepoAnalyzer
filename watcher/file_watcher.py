"""File watcher implementation."""

import os
import asyncio
import fnmatch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from utils.logger import log
from indexer.unified_indexer import ProcessingCoordinator
from indexer.clone_and_index import get_or_create_repo
from indexer.async_utils import async_process_index_file, async_read_text_file
from utils.async_runner import submit_async_task
from indexer.file_ignore_config import IGNORED_DIRECTORIES, IGNORED_FILES
from indexer.file_utils import is_binary_file, is_processable_file, get_relative_path
from parsers.language_support import language_registry
from parsers.file_classification import get_file_classification, FileType
from db.upsert_ops import upsert_code_snippet, upsert_doc, get_or_create_repo
from db.neo4j_ops import auto_reinvoke_projection_once
import aiofiles
from indexer.file_processor import FileProcessor
from semantic.search import search_code

class AsyncFileSystemEventHandler(FileSystemEventHandler):
    def __init__(self, coordinator: ProcessingCoordinator, repo_id: int):
        self.coordinator = coordinator
        self.repo_id = repo_id
        self._processing_lock = asyncio.Lock()
        
    def on_modified(self, event):
        if event.is_directory:
            return
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(self.handle_file_change(event.src_path), loop)
        
    async def handle_file_change(self, file_path: str) -> None:
        """Handle file changes with proper locking and coordination."""
        if not is_processable_file(file_path):
            return
            
        async with self._processing_lock:
            try:
                repo_path = os.getcwd()
                await self.coordinator.process_file(file_path, self.repo_id, repo_path)
                await auto_reinvoke_projection_once()
            except Exception as e:
                log(f"Error processing file change {file_path}: {e}", level="error")

async def watch_directory(directory: str, repo_id: int) -> None:
    """Enhanced async file watcher with proper coordination."""
    coordinator = ProcessingCoordinator()
    
    try:
        event_handler = AsyncFileSystemEventHandler(coordinator, repo_id)
        observer = Observer()
        observer.schedule(event_handler, directory, recursive=True)
        observer.start()
        
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        observer.stop()
        observer.join()
    finally:
        coordinator.cleanup()

def start_file_watcher(path: str = ".") -> None:
    """Start the file watcher in the current directory."""
    async def async_main():
        try:
            repo_name = os.path.basename(os.getcwd())
            repo_id = await get_or_create_repo(repo_name, repo_type="active")
            log(f"Starting file watcher for repository: {repo_name} (id: {repo_id})")
            await watch_directory(path, repo_id)
        except Exception as e:
            log(f"Error in file watcher: {e}", level="error")

    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        log("File watcher stopped by user", level="info")