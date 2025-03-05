"""Repository cloning and indexing coordination.

This module handles repository cloning and initial indexing setup,
coordinating with the database layer for repository management.
"""

import os
import tempfile
import subprocess
from typing import Optional, Set
from utils.logger import log
from db.upsert_ops import UpsertCoordinator
from db.transaction import transaction_scope
from indexer.unified_indexer import process_repository_indexing
from parsers.types import FileType
from parsers.models import FileClassification
from parsers.file_classification import classify_file
import asyncio
from contextlib import asynccontextmanager
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    ProcessingError,
    AsyncErrorBoundary,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler

# Initialize the upsert coordinator
_upsert_coordinator = UpsertCoordinator()

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

@handle_async_errors(error_types=ProcessingError)
async def get_or_create_repo(
    repo_name: str,
    source_url: Optional[str] = None,
    repo_type: str = "active",
    active_repo_id: Optional[int] = None
) -> int:
    """Retrieves or creates a repository using the centralized upsert operation."""
    async with AsyncErrorBoundary(
        operation_name=f"getting or creating repository '{repo_name}'",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        if not _upsert_coordinator._initialized:
            await _upsert_coordinator.initialize()
        return await _upsert_coordinator.upsert_repository({
            'repo_name': repo_name,
            'repo_type': repo_type,
            'source_url': source_url,
            'active_repo_id': active_repo_id
        })

@handle_async_errors(error_types=ProcessingError)
async def clone_repository(repo_url: str, target_dir: str) -> bool:
    """Clone a git repository to target directory."""
    async with AsyncErrorBoundary(
        operation_name=f"cloning repository from {repo_url}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
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

@handle_async_errors(error_types=ProcessingError)
async def clone_and_index_repo(
    repo_url: str,
    repo_name: Optional[str] = None,
    active_repo_id: Optional[int] = None
) -> None:
    """Clone and index a reference repository."""
    async with AsyncErrorBoundary(
        operation_name=f"cloning and indexing repository from {repo_url}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
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