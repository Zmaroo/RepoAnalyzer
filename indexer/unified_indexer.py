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
from async_utils import batch_process_files
from typing import Optional, Dict, List
from utils.logger import log
from indexer.async_utils import async_read_file
from indexer.file_utils import get_files, get_relative_path, is_processable_file
from parsers.models import (
    FileType,
    FileClassification,
    ParserResult,
    ExtractedFeatures
)

from parsers.language_support import language_registry
from db.neo4j_ops import auto_reinvoke_projection_once
from db.upsert_ops import get_or_create_repo
from indexer.file_processor import FileProcessor
from semantic.search import search_code

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
        self._language_registry = language_registry  # Language detection
        self._tasks = set()  # Active task tracking
    
    async def process_file(self, file_path: str, repo_id: int, repo_path: str) -> Optional[Dict]:
        """[1.2] Single entry point for file processing.
        
        Flow:
        1. Validate file is processable
        2. Create and track async task
        3. Handle task completion/cleanup
        4. Support graceful cancellation
        """
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

async def process_repository_indexing(repo_path: str, repo_id: int, repo_type: str = "active") -> None:
    """[1.3] Central repository indexing pipeline.
    
    Flow:
    1. Initialize coordinator
    2. Discover processable files
    3. Process files in batches
    4. Update graph projections
    5. Ensure cleanup
    """
    
    coordinator = ProcessingCoordinator()
    try:
        log(f"Starting indexing for repository {repo_id} at {repo_path}")
        
        files = get_files(
            repo_path,
            file_types={FileType.CODE, FileType.DOC}
        )
        
        await batch_process_files(
            files=files,
            base_path=repo_path,
            repo_id=repo_id,
            batch_size=10
        )
            
        await auto_reinvoke_projection_once()
        
        log(f"Completed indexing for repository {repo_id}")

    except Exception as e:
        log(f"Error during repository indexing: {e}", level="error")
        raise
    finally:
        coordinator.cleanup()

async def index_active_project() -> None:
    """
    Starts asynchronous indexing for the active project.
    """
    repo_path = os.getcwd()
    repo_name = os.path.basename(repo_path)
    
    try:
        repo_id = await get_or_create_repo(
            repo_name, 
            source_url=None, 
            repo_type="active"
        )
        
        log(f"Active project repo: {repo_name} (id: {repo_id}) at {repo_path}")
        await process_repository_indexing(repo_path, repo_id, repo_type="active")
        
    except Exception as e:
        log(f"Error indexing active project: {e}", level="error")

def index_active_project_sync() -> None:
    """Synchronous wrapper for index_active_project"""
    asyncio.run(index_active_project())

if __name__ == "__main__":
    index_active_project_sync() 