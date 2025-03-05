"""[1.0] Unified repository indexing system.

Flow:
1. Entry Points:
   - index_active_project(): For current working directory
   - process_repository_indexing(): Core indexing pipeline
   - ProcessingCoordinator: Handles individual file processing

2. Processing Pipeline:
   - File Discovery: get_files() finds all processable files
   - Batch Processing: Files are processed in configurable batches
   - Graph Updates: Neo4j projections are updated after indexing

3. Integration Points:
   - FileProcessor: Handles parsing and storage
   - Language Registry: Determines file language and parser
   - File Utils: Handles file validation and path management
"""

import os
import asyncio
from indexer.async_utils import batch_process_files
from typing import Optional, Dict, List
from utils.logger import log
from indexer.async_utils import async_read_file
from indexer.file_utils import get_files, get_relative_path, is_processable_file
from parsers.types import ParserResult, FileType, ExtractedFeatures  # Lightweight DTO type
from parsers.models import FileClassification  # Domain models
from parsers.language_support import language_registry
from parsers.query_patterns import initialize_pattern_system
from db.neo4j_ops import auto_reinvoke_projection_once
from db.upsert_ops import upsert_code_snippet
from indexer.file_processor import FileProcessor
from semantic.search import search_code
from utils.error_handling import handle_async_errors, ErrorBoundary, ErrorSeverity
from utils.request_cache import request_cache_context, cached_in_request

# Ensure pattern system is initialized
initialize_pattern_system()

class ProcessingCoordinator:
    """[1.1] Central coordinator for file processing.
    
    Responsibilities:
    - Manages FileProcessor lifecycle
    - Tracks and handles async tasks
    - Provides cancellation support
    - Ensures proper cleanup
    """
    
    def __init__(self):
        self.file_processor = FileProcessor()  # Handles file processing
        self._tasks = set()  # Active task tracking
    
    @handle_async_errors
    async def process_file(self, file_path: str, repo_id: int, repo_path: str) -> Optional[Dict]:
        """[1.2] Single entry point for file processing.
        
        Flow:
        1. Validate file is processable
        2. Create and track async task
        3. Handle task completion/cleanup
        4. Support graceful cancellation
        """
        with ErrorBoundary(f"processing file {file_path}", severity=ErrorSeverity.ERROR):
            try:
                if not is_processable_file(file_path):
                    log(f"File not processable: {file_path}", level="debug")
                    return None
                    
                task = asyncio.create_task(
                    self.file_processor.process_file(file_path, repo_id, repo_path)
                )
                self._tasks.add(task)
                try:
                    return await task
                finally:
                    self._tasks.remove(task)
                    
            except asyncio.CancelledError:
                # Cancel all tracked tasks on interruption
                for task in self._tasks:
                    task.cancel()
                await asyncio.gather(*self._tasks, return_exceptions=True)
                raise

    def cleanup(self):
        """Cleanup all processing resources."""
        self.file_processor.clear_cache()

@handle_async_errors
async def process_repository_indexing(repo_path: str, repo_id: int, repo_type: str = "active", single_file: bool = False) -> None:
    """[1.3] Central repository indexing pipeline with request-level caching.
    
    This function discovers processable files under `repo_path`, processes them
    concurrently, updates the graph projection, and finally performs any necessary
    cleanup.
    
    Using request-level caching to avoid redundant work during a single indexing operation.
    """
    # Wrap the entire operation in a request cache context
    with request_cache_context(), ErrorBoundary(f"processing repository {repo_id} at {repo_path}", severity=ErrorSeverity.ERROR):
        coordinator = ProcessingCoordinator()
        tasks = set()
        
        try:
            log(f"Starting indexing for repository {repo_id} at {repo_path}")
            
            if single_file and os.path.isfile(repo_path):
                files = [repo_path]
            else:
                # Get processable files with FileType enum values - using cached version
                files = await get_processable_files(repo_path)
            
            # Process files in batches to avoid overwhelming system resources
            batch_size = 20  # Adjust based on your system's capability
            for i in range(0, len(files), batch_size):
                batch = files[i:i + batch_size]
                batch_tasks = []
                
                for file in batch:
                    if is_processable_file(file):
                        task = asyncio.create_task(coordinator.process_file(file, repo_id, repo_path))
                        batch_tasks.append(task)
                        tasks.add(task)
                        task.add_done_callback(lambda t: tasks.remove(t) if t in tasks else None)
                
                if batch_tasks:
                    # Wait for this batch to complete before starting the next
                    results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    # Check for errors but continue processing
                    for result in results:
                        if isinstance(result, Exception):
                            log(f"Error processing file batch: {result}", level="error")
                
                # Give other tasks a chance to run
                await asyncio.sleep(0)
                
            # Update the graph projection
            try:
                projection_result = await auto_reinvoke_projection_once(repo_id)
                log(f"Graph projection update result: {projection_result}", level="info")
            except Exception as e:
                log(f"Error updating graph projection: {e}", level="error")
            
            # Extract patterns if this is a reference repository
            if repo_type == "reference" and not single_file:
                try:
                    # Import here to avoid circular imports
                    from ai_tools.reference_repository_learning import ReferenceRepositoryLearning
                    ref_repo_learning = ReferenceRepositoryLearning()
                    log(f"Extracting patterns from reference repository {repo_id}", level="info")
                    await ref_repo_learning.learn_from_repository(repo_id)
                except Exception as e:
                    log(f"Error learning from reference repository: {e}", level="error")
                    
        except Exception as e:
            log(f"Error in repository indexing: {e}", level="error")
            raise
        finally:
            # Clean up resources
            coordinator.cleanup()
            log(f"Completed indexing for repository {repo_id}", level="info")

# Add utility functions with request-level caching

@cached_in_request
async def get_processable_files(repo_path: str) -> List[str]:
    """Get processable files from a repository path with caching."""
    return get_files(repo_path, {FileType.CODE, FileType.DOC})

async def index_active_project() -> None:
    """[2.5] Index the currently active project (working directory)."""
    repo_path = os.getcwd()
    repo_name = os.path.basename(os.path.abspath(repo_path))
    
    # Import locally to avoid circular imports
    from indexer.clone_and_index import get_or_create_repo
    
    # Example: Obtain (or create) a repository record.
    repo_id = await get_or_create_repo(repo_name, repo_type="active")
    log(f"Active project repo: {repo_name} (id: {repo_id}) at {repo_path}")
    await process_repository_indexing(repo_path, repo_id, repo_type="active")

def index_active_project_sync() -> None:
    """Synchronous wrapper for indexing the active project."""
    asyncio.run(index_active_project())

if __name__ == "__main__":
    index_active_project_sync() 