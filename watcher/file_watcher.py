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

def is_pattern_relevant_file(file_path: str) -> bool:
    """
    Determine if a file is relevant for pattern extraction.
    
    Args:
        file_path: Path to the file
        
    Returns:
        bool: True if the file is relevant for pattern extraction
    """
    # Get file extension
    _, ext = os.path.splitext(file_path)
    
    # Code files are relevant for pattern extraction
    code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rb', '.php'}
    return ext.lower() in code_extensions

async def handle_file_change(file_path: str, repo_id: int):
    """
    Handle file changes by reprocessing the file and updating patterns.
    
    Args:
        file_path: Path to the file that changed
        repo_id: Repository ID
    """
    log(f"File changed: {file_path}", level="info")
    
    # Process the changed file
    from indexer.unified_indexer import process_repository_indexing
    await process_repository_indexing(file_path, repo_id, single_file=True)
    
    # Update repository patterns if the file is relevant
    if is_pattern_relevant_file(file_path):
        try:
            # Import here to avoid circular imports
            from ai_tools.reference_repository_learning import ReferenceRepositoryLearning
            from db.psql import query
            
            # Get the repository type
            repo_result = await query("SELECT repo_type FROM repositories WHERE id = %s", (repo_id,))
            
            # Only update patterns for reference repositories
            if repo_result and repo_result[0]['repo_type'] == 'reference':
                ref_repo_learning = ReferenceRepositoryLearning()
                log(f"Updating patterns for file: {file_path}", level="info")
                
                # Get relative path for the file
                base_path = os.path.dirname(os.path.dirname(file_path))
                rel_path = get_relative_path(file_path, base_path)
                
                # Update patterns for the specific file
                await ref_repo_learning.update_patterns_for_file(repo_id, rel_path)
        except Exception as e:
            log(f"Error updating patterns for file {file_path}: {e}", level="error")
    
    # Update graph analysis
    from ai_tools.graph_capabilities import graph_analysis
    await graph_analysis.analyze_code_structure(repo_id)

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