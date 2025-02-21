"""Unified repository indexing system."""

import os
import asyncio
from typing import Optional, Dict, List
from utils.logger import log
from indexer.async_utils import async_read_file
from indexer.file_utils import get_files, get_relative_path, is_processable_file
from parsers.file_classification import FileType, get_file_classification
from parsers.language_support import language_registry
from db.neo4j_ops import auto_reinvoke_projection_once
from db.upsert_ops import get_or_create_repo
from indexer.file_processor import FileProcessor
from semantic.search import search_code

class ProcessingCoordinator:
    """Coordinates all file processing activities."""
    
    def __init__(self):
        self.file_processor = FileProcessor()
        self._language_registry = language_registry
    
    async def process_file(self, file_path: str, repo_id: int, repo_path: str) -> Optional[Dict]:
        """Single entry point for file processing."""
        try:
            if not is_processable_file(file_path):
                log(f"File not processable: {file_path}", level="debug")
                return None
                
            return await self.file_processor.process_file(file_path, repo_id, repo_path)
            
        except Exception as e:
            log(f"Error in processing coordinator: {e}", level="error")
            return None
        
    def cleanup(self):
        """Cleanup all processing resources."""
        self.file_processor.clear_cache()

async def process_repository_indexing(repo_path: str, repo_id: int, repo_type: str = "active") -> None:
    """
    Central repository indexing pipeline.
    
    Pipeline stages:
    1. File Discovery & Classification
    2. Parsing & AST Extraction
    3. Feature Enrichment
    4. Storage
    """
    coordinator = ProcessingCoordinator()
    try:
        log(f"Starting indexing for repository {repo_id} at {repo_path}")
        
        # Get all processable files
        files = get_files(
            repo_path,
            file_types={FileType.CODE, FileType.DOC}
        )
        
        # Process files
        for file_path in files:
            await coordinator.process_file(file_path, repo_id, repo_path)
            
        # Update graph projections
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