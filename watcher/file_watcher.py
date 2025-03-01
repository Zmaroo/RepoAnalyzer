"""File watcher implementation."""
import os
import asyncio
import fnmatch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from utils.logger import log
from indexer.unified_indexer import ProcessingCoordinator
from indexer.clone_and_index import get_or_create_repo
from indexer.file_utils import is_binary_file, is_processable_file, get_relative_path, get_file_classification
from parsers.models import FileType, FileClassification
from parsers.language_support import language_registry
from db.upsert_ops import upsert_code_snippet, upsert_doc
from db.neo4j_ops import auto_reinvoke_projection_once
from utils.error_handling import handle_async_errors, ErrorBoundary, AsyncErrorBoundary


class AsyncFileChangeHandler(FileSystemEventHandler):

    def __init__(self, on_change):
        self.on_change = on_change
        self._tasks = set()

    def on_modified(self, event):
        if not event.is_directory:
            task = asyncio.create_task(self._handle_change(event.src_path))
            self._tasks.add(task)
            task.add_done_callback(lambda t: self._tasks.remove(t) if t in
                self._tasks else None)

    @handle_async_errors
    async def _handle_change(self, file_path):
        """Handle file change in a properly tracked async task."""
        with AsyncErrorBoundary(f'handling file change for {file_path}'):
            await self.on_change(file_path)


@handle_async_errors
async def watch_directory(directory: str, repo_id: int, on_change):
    """
    Asynchronously watch a directory and invoke the provided callback on changes.
    
    Args:
        directory: The directory to watch.
        repo_id: Repository ID associated with the files.
        on_change: Asynchronous callback to execute on file changes.
    """
    with AsyncErrorBoundary(f'watching directory {directory}'):
        event_handler = AsyncFileChangeHandler(on_change)
        observer = Observer()
        observer.schedule(event_handler, directory, recursive=True)
        observer.start()
        log(f'Started watching directory: {directory}', level='info')
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            log('File watcher cancelled.', level='warning')
            for task in asyncio.all_tasks():
                if task != asyncio.current_task():
                    task.cancel()
            pending = asyncio.all_tasks() - {asyncio.current_task()}
            if pending:
                await asyncio.wait(pending, timeout=5)
        finally:
            observer.stop()
            observer.join()


def is_pattern_relevant_file(file_path: str) ->bool:
    """
    Determine if a file is relevant for pattern extraction.
    
    Args:
        file_path: Path to the file
        
    Returns:
        bool: True if the file is relevant for pattern extraction
    """
    _, ext = os.path.splitext(file_path)
    code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h',
        '.go', '.rb', '.php'}
    return ext.lower() in code_extensions


@handle_async_errors
async def handle_file_change(file_path: str, repo_id: int):
    """
    Handle file changes by reprocessing the file and updating patterns.
    
    Args:
        file_path: Path to the file that changed
        repo_id: Repository ID
    """
    with AsyncErrorBoundary(f'handling file change for {file_path}'):
        log(f'File changed: {file_path}', level='info')
        from indexer.unified_indexer import process_repository_indexing
        await process_repository_indexing(file_path, repo_id, single_file=True)
        if is_pattern_relevant_file(file_path):
            try:
                from ai_tools.reference_repository_learning import ReferenceRepositoryLearning
                from db.psql import query
                repo_result = await query(
                    'SELECT repo_type FROM repositories WHERE id = %s', (
                    repo_id,))
                if repo_result and repo_result[0]['repo_type'] == 'reference':
                    ref_repo_learning = ReferenceRepositoryLearning()
                    log(f'Updating patterns for file: {file_path}', level=
                        'info')
                    base_path = os.path.dirname(os.path.dirname(file_path))
                    rel_path = get_relative_path(file_path, base_path)
                    await ref_repo_learning.update_patterns_for_file(repo_id,
                        rel_path)
            except Exception as e:
                log(f'Error updating patterns for file {file_path}: {e}',
                    level='error')
        from ai_tools.graph_capabilities import graph_analysis
        await graph_analysis.analyze_code_structure(repo_id)


def start_file_watcher(path: str='.') ->None:
    """Start the file watcher in the current directory."""

    @handle_async_errors
    async def async_main():
        with AsyncErrorBoundary(operation_name='starting file watcher'):
            repo_name = os.path.basename(os.getcwd())
            repo_id = await get_or_create_repo(repo_name, repo_type='active')
            log(f'Starting file watcher for repository: {repo_name} (id: {repo_id})'
                )
            await watch_directory(path, repo_id, lambda file_path: asyncio.
                create_task(handle_file_change(file_path, repo_id)))
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        log('File watcher stopped by user', level='info')
