"""File watcher implementation."""

import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from utils.logger import log
from indexer.unified_indexer import ProcessingCoordinator
from indexer.clone_and_index import get_or_create_repo
from indexer.file_utils import is_binary_file, is_processable_file, get_relative_path
from parsers.models import FileType, FileClassification
from parsers.language_support import language_registry
from db.upsert_ops import UpsertCoordinator
from db.neo4j_ops import get_graph_sync
from utils.error_handling import (
    handle_async_errors, 
    AsyncErrorBoundary, 
    ErrorSeverity,
    ProcessingError
)
from utils.shutdown import register_shutdown_handler
from typing import Callable, Dict, Any, Optional, Set
import asyncio

# Initialize upsert coordinator
_upsert_coordinator = UpsertCoordinator()

# Initialize graph sync
_graph_sync = None

async def get_or_init_graph_sync():
    """Get or initialize the graph sync instance."""
    global _graph_sync
    if _graph_sync is None:
        _graph_sync = await get_graph_sync()
    return _graph_sync

class AsyncFileHandler(FileSystemEventHandler):
    """Asynchronous file event handler."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        super().__init__()
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self.on_change = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("AsyncFileHandler not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls, on_change: Callable[[str], None]) -> 'AsyncFileHandler':
        """Async factory method to create and initialize an AsyncFileHandler instance."""
        instance = cls()
        instance.on_change = on_change
        
        try:
            async with AsyncErrorBoundary(
                operation_name="file handler initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize required components
                if not _upsert_coordinator._initialized:
                    await _upsert_coordinator.initialize()
                
                # Initialize graph sync
                await get_or_init_graph_sync()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("file_handler")
                
                instance._initialized = True
                await log("File handler initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing file handler: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize file handler: {e}")
    
    def on_modified(self, event):
        """Handle file modification events."""
        if isinstance(event, FileModifiedEvent):
            # Create task for change handling
            task = asyncio.create_task(self._handle_change(event.src_path))
            self._pending_tasks.add(task)
            task.add_done_callback(lambda t: self._pending_tasks.remove(t) if t in self._pending_tasks else None)
    
    async def _handle_change(self, file_path: str):
        """Handle file change asynchronously."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("handle_file_change"):
            try:
                await self.on_change(file_path)
            except Exception as e:
                await log(f"Error handling file change: {e}", level="error")
    
    async def cleanup(self):
        """Clean up file handler resources."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up upsert coordinator
            if _upsert_coordinator._initialized:
                await _upsert_coordinator.cleanup()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("file_handler")
            
            self._initialized = False
            await log("File handler cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up file handler: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup file handler: {e}")

class DirectoryWatcher:
    """Directory watcher implementation."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._observer = None
        self._handler = None
        self._watched_paths: Set[str] = set()
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("DirectoryWatcher not initialized. Use create() to initialize.")
        if not self._observer:
            raise ProcessingError("Observer not initialized")
        return True
    
    @classmethod
    async def create(cls) -> 'DirectoryWatcher':
        """Async factory method to create and initialize a DirectoryWatcher instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="directory watcher initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize observer
                instance._observer = Observer()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("directory_watcher")
                
                instance._initialized = True
                await log("Directory watcher initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing directory watcher: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize directory watcher: {e}")
    
    async def watch_directory(self, path: str, repo_id: int, on_change: Callable[[str], None]) -> None:
        """Watch a directory for file changes."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("watch_directory"):
            try:
                # Create and initialize handler
                self._handler = await AsyncFileHandler.create(on_change)
                
                # Schedule and start observer
                self._observer.schedule(self._handler, path, recursive=True)
                self._watched_paths.add(path)
                
                if not self._observer.is_alive():
                    self._observer.start()
                
                try:
                    while True:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    await self._handler.cleanup()
                    self._observer.stop()
                    self._observer.join()
            except Exception as e:
                await log(f"Error watching directory: {e}", level="error")
                raise ProcessingError(f"Failed to watch directory: {e}")
    
    async def stop_watching(self, path: str) -> None:
        """Stop watching a specific directory."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("stop_watching"):
            try:
                if path in self._watched_paths:
                    # Remove the schedule for this path
                    for schedule in self._observer.schedules:
                        if schedule.path == path:
                            self._observer.unschedule(schedule)
                            break
                    self._watched_paths.remove(path)
                    
                    # If no more paths are being watched, stop the observer
                    if not self._watched_paths:
                        self._observer.stop()
                        self._observer.join()
            except Exception as e:
                await log(f"Error stopping directory watch: {e}", level="error")
                raise ProcessingError(f"Failed to stop watching directory: {e}")
    
    async def cleanup(self):
        """Clean up directory watcher resources."""
        try:
            if not self._initialized:
                return
                
            # Stop watching all directories
            for path in self._watched_paths.copy():
                await self.stop_watching(path)
            
            # Clean up handler if it exists
            if self._handler:
                await self._handler.cleanup()
            
            # Stop and join observer if it exists
            if self._observer:
                self._observer.stop()
                self._observer.join()
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("directory_watcher")
            
            self._initialized = False
            await log("Directory watcher cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up directory watcher: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup directory watcher: {e}")

# Global instance
_directory_watcher = None

async def get_directory_watcher() -> DirectoryWatcher:
    """Get the global directory watcher instance."""
    global _directory_watcher
    if not _directory_watcher:
        _directory_watcher = await DirectoryWatcher.create()
    return _directory_watcher

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
        
        # Process the changed file
        from indexer.unified_indexer import process_repository_indexing
        task = asyncio.create_task(process_repository_indexing(file_path, repo_id, single_file=True))
        try:
            await task
        except Exception as e:
            log(f"Error processing file {file_path}: {e}", level="error")
            return
        
        # Update repository patterns if the file is relevant
        if is_pattern_relevant_file(file_path):
            try:
                from ai_tools.reference_repository_learning import ReferenceRepositoryLearning
                from db.psql import query
                
                # Get the repository type
                task = asyncio.create_task(query("SELECT repo_type FROM repositories WHERE id = %s", (repo_id,)))
                try:
                    repo_result = await task
                except Exception as e:
                    log(f"Error getting repository type: {e}", level="error")
                    return
                
                # Only update patterns for reference repositories
                if repo_result and repo_result[0]['repo_type'] == 'reference':
                    ref_repo_learning = ReferenceRepositoryLearning()
                    log(f"Updating patterns for file: {file_path}", level="info")
                    
                    base_path = os.path.dirname(os.path.dirname(file_path))
                    rel_path = get_relative_path(file_path, base_path)
                    
                    # Update patterns
                    task = asyncio.create_task(ref_repo_learning.update_patterns_for_file(repo_id, rel_path))
                    try:
                        await task
                    except Exception as e:
                        log(f"Error updating patterns: {e}", level="error")
            except Exception as e:
                log(f"Error updating patterns for file {file_path}: {e}", level="error")
        
        # Update graph analysis using graph sync
        try:
            graph_sync = await get_or_init_graph_sync()
            await graph_sync.invalidate_projection(repo_id)
            await graph_sync.ensure_projection(repo_id)
            log(f"Updated graph projection for repository {repo_id}", level="info")
        except Exception as e:
            log(f"Error updating graph projection: {e}", level="error")

async def start_file_watcher(path: str = ".") -> None:
    """Start the file watcher in the current directory."""
    async with AsyncErrorBoundary("starting file watcher"):
        repo_name = os.path.basename(os.getcwd())
        
        # Get or create repo
        task = asyncio.create_task(get_or_create_repo(repo_name, repo_type="active"))
        try:
            repo_id = await task
        except Exception as e:
            log(f"Error getting/creating repository: {e}", level="error")
            return
            
        await log(f"Starting file watcher for repository: {repo_name} (id: {repo_id})")
        
        # Create a handler function that creates tasks
        def handle_change(file_path):
            return asyncio.create_task(handle_file_change(file_path, repo_id))
        
        # Get directory watcher instance and start watching
        watcher = await get_directory_watcher()
        await watcher.watch_directory(path, repo_id, handle_change)

# Export watch_directory as an alias for start_file_watcher
watch_directory = start_file_watcher

def main():
    """Main entry point for the file watcher."""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_file_watcher())
    except KeyboardInterrupt:
        log("File watcher stopped by user", level="info")
    finally:
        # Create and run cleanup task
        async def cleanup():
            watcher = await get_directory_watcher()
            if watcher:
                await watcher.cleanup()
        loop.run_until_complete(cleanup())

if __name__ == "__main__":
    main()