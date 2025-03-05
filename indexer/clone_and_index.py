"""Repository cloning and indexing coordination.

This module handles repository cloning and initial indexing setup,
coordinating with the database layer for repository management.
"""

import os
import tempfile
import subprocess
from typing import Optional, Set
from utils.logger import log
from db.upsert_ops import upsert_repository
from db.transaction import transaction_scope
from indexer.unified_indexer import process_repository_indexing
from parsers.types import FileType
from parsers.models import FileClassification
from parsers.file_classification import classify_file
import asyncio
from contextlib import asynccontextmanager
from utils.error_handling import (
    handle_async_errors,
    ErrorBoundary,
    ErrorSeverity,
    ProcessingError,
    DatabaseError
)
from utils.async_runner import submit_async_task, get_loop

@asynccontextmanager
async def repository_transaction():
    """Context manager for repository operations ensuring proper cleanup."""
    async with transaction_scope() as txn:
        try:
            yield txn
        except Exception as e:
            log(f"Repository transaction failed: {e}", level="error")
            raise
        finally:
            # Ensure any temporary resources are cleaned up
            pass

@handle_async_errors(error_types=(ProcessingError, DatabaseError))
async def get_or_create_repo(
    repo_name: str,
    source_url: Optional[str] = None,
    repo_type: str = "active",
    active_repo_id: Optional[int] = None
) -> int:
    """Retrieves or creates a repository using the centralized upsert operation."""
    async with ErrorBoundary(f"getting or creating repository '{repo_name}'", severity=ErrorSeverity.ERROR):
        async with repository_transaction() as txn:
            repo_data = {
                'repo_name': repo_name,
                'source_url': source_url,
                'repo_type': repo_type,
                'active_repo_id': active_repo_id
            }
            repo_id = await upsert_repository(repo_data)
            await txn.track_repo_change(repo_id)
            return repo_id

@handle_async_errors(error_types=(ProcessingError, DatabaseError))
async def clone_repository(repo_url: str, target_dir: str) -> bool:
    """Clone a git repository to target directory."""
    async with ErrorBoundary(f"cloning repository from {repo_url}", severity=ErrorSeverity.ERROR):
        try:
            # Run git clone in a way that doesn't block the event loop
            proc = await asyncio.create_subprocess_exec(
                'git', 'clone', '--depth', '1', repo_url, target_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                log(f"Git clone failed: {stderr.decode()}", level="error")
                return False
                
            log(f"Successfully cloned {repo_url}", level="info")
            return True
            
        except Exception as e:
            log(f"Error cloning repository: {e}", level="error")
            return False

@handle_async_errors(error_types=(ProcessingError, DatabaseError))
async def clone_and_index_repo(
    repo_url: str,
    repo_name: Optional[str] = None,
    active_repo_id: Optional[int] = None
) -> None:
    """Clone and index a reference repository."""
    async with ErrorBoundary(f"cloning and indexing repository from {repo_url}", severity=ErrorSeverity.ERROR):
        if not repo_name:
            repo_name = repo_url.split('/')[-1].replace('.git', '')
        
        async with repository_transaction() as txn:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Clone repository
                if not await clone_repository(repo_url, temp_dir):
                    raise ProcessingError(f"Failed to clone repository: {repo_url}")
                
                # Create repository record
                repo_id = await get_or_create_repo(
                    repo_name,
                    source_url=repo_url,
                    repo_type="reference",
                    active_repo_id=active_repo_id
                )
                
                # Track repository change
                await txn.track_repo_change(repo_id)
                
                # Index repository using unified indexer
                await process_repository_indexing(temp_dir, repo_id, repo_type="reference")