"""File watcher implementation."""

import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from utils.logger import log
from indexer.unified_indexer import ProcessingCoordinator
from indexer.clone_and_index import get_or_create_repo
from indexer.file_utils import is_binary_file, is_processable_file, get_relative_path, get_file_classification
from parsers.models import FileType, FileClassification
from parsers.language_support import language_registry
from db.upsert_ops import upsert_code_snippet, upsert_doc
from db.neo4j_ops import auto_reinvoke_projection_once
from utils.async_runner import submit_async_task, get_loop
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorBoundary, ErrorSeverity
from utils.app_init import register_shutdown_handler
from typing import Callable, Dict, Any, Optional, Set
import asyncio

class AsyncFileHandler(FileSystemEventHandler):
    """Asynchronous file event handler."""
    
    def __init__(self, on_change: Callable[[str], None]):
        self.on_change = on_change
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """Initialize file handler resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("file_handler_initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    log("File handler initialized", level="info")
            except Exception as e:
                log(f"Error initializing file handler: {e}", level="error")
                raise
    
    def on_modified(self, event):
        """Handle file modification events."""
        if isinstance(event, FileModifiedEvent):
            # Submit change handling task using async_runner
            future = submit_async_task(self._handle_change(event.src_path))
            self._pending_tasks.add(future)
            future.add_done_callback(lambda f: self._pending_tasks.remove(f) if f in self._pending_tasks else None)
    
    @handle_async_errors(error_types=(Exception,))
    async def _handle_change(self, file_path: str):
        """Handle file change asynchronously."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("handle_file_change"):
            try:
                await self.on_change(file_path)
            except Exception as e:
                log(f"Error handling file change: {e}", level="error")
    
    async def cleanup(self):
        """Clean up file handler resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("File handler cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up file handler: {e}", level="error")

class DirectoryWatcher:
    """Directory watcher implementation."""
    
    def __init__(self):
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        self._observer = None
        self._handler = None
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """Initialize directory watcher resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("directory_watcher_initialization"):
                    self._observer = Observer()
                    self._initialized = True
                    log("Directory watcher initialized", level="info")
            except Exception as e:
                log(f"Error initializing directory watcher: {e}", level="error")
                raise
    
    @handle_async_errors(error_types=(Exception,))
    async def watch_directory(self, path: str, repo_id: int, on_change: Callable[[str], None]) -> None:
        """Watch a directory for file changes."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("watch_directory"):
            try:
                self._handler = AsyncFileHandler(on_change)
                await self._handler.initialize()
                
                self._observer.schedule(self._handler, path, recursive=True)
                self._observer.start()
                
                try:
                    while True:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    await self._handler.cleanup()
                    self._observer.stop()
                    self._observer.join()
            except Exception as e:
                log(f"Error watching directory: {e}", level="error")
    
    async def cleanup(self):
        """Clean up directory watcher resources."""
        try:
            # Clean up handler if it exists
            if self._handler:
                await self._handler.cleanup()
            
            # Stop and join observer if it exists
            if self._observer:
                self._observer.stop()
                self._observer.join()
            
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("Directory watcher cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up directory watcher: {e}", level="error")

# Global instance
directory_watcher = DirectoryWatcher()

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

@handle_async_errors(error_types=(Exception,))
async def handle_file_change(file_path: str, repo_id: int):
    """Handle file changes by reprocessing the file and updating patterns."""
    async with AsyncErrorBoundary(f"handling file change for {file_path}"):
        log(f"File changed: {file_path}", level="info")
        
        # Process the changed file using async_runner
        from indexer.unified_indexer import process_repository_indexing
        future = submit_async_task(process_repository_indexing(file_path, repo_id, single_file=True))
        try:
            await asyncio.wrap_future(future)
        except Exception as e:
            log(f"Error processing file {file_path}: {e}", level="error")
            return
        
        # Update repository patterns if the file is relevant
        if is_pattern_relevant_file(file_path):
            try:
                from ai_tools.reference_repository_learning import ReferenceRepositoryLearning
                from db.psql import query
                
                # Get the repository type
                future = submit_async_task(query("SELECT repo_type FROM repositories WHERE id = %s", (repo_id,)))
                try:
                    repo_result = await asyncio.wrap_future(future)
                except Exception as e:
                    log(f"Error getting repository type: {e}", level="error")
                    return
                
                # Only update patterns for reference repositories
                if repo_result and repo_result[0]['repo_type'] == 'reference':
                    ref_repo_learning = ReferenceRepositoryLearning()
                    log(f"Updating patterns for file: {file_path}", level="info")
                    
                    base_path = os.path.dirname(os.path.dirname(file_path))
                    rel_path = get_relative_path(file_path, base_path)
                    
                    # Update patterns using async_runner
                    future = submit_async_task(ref_repo_learning.update_patterns_for_file(repo_id, rel_path))
                    try:
                        await asyncio.wrap_future(future)
                    except Exception as e:
                        log(f"Error updating patterns: {e}", level="error")
            except Exception as e:
                log(f"Error updating patterns for file {file_path}: {e}", level="error")
        
        # Update graph analysis using async_runner
        from ai_tools.graph_capabilities import graph_analysis
        future = submit_async_task(graph_analysis.analyze_code_structure(repo_id))
        try:
            await asyncio.wrap_future(future)
        except Exception as e:
            log(f"Error updating graph analysis: {e}", level="error")

async def start_file_watcher(path: str = ".") -> None:
    """Start the file watcher in the current directory."""
    async with AsyncErrorBoundary("starting file watcher"):
        repo_name = os.path.basename(os.getcwd())
        
        # Get or create repo using async_runner
        future = submit_async_task(get_or_create_repo(repo_name, repo_type="active"))
        try:
            repo_id = await asyncio.wrap_future(future)
        except Exception as e:
            log(f"Error getting/creating repository: {e}", level="error")
            return
            
        log(f"Starting file watcher for repository: {repo_name} (id: {repo_id})")
        
        # Create a handler function that uses submit_async_task
        def handle_change(file_path):
            return submit_async_task(handle_file_change(file_path, repo_id))
        
        await directory_watcher.watch_directory(path, repo_id, handle_change)

def main():
    """Main entry point for the file watcher."""
    loop = get_loop()
    try:
        loop.run_until_complete(start_file_watcher())
    except KeyboardInterrupt:
        log("File watcher stopped by user", level="info")
    finally:
        loop.run_until_complete(directory_watcher.cleanup())

if __name__ == "__main__":
    main()