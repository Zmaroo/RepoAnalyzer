"""[4.0] Repository cloning and indexing coordination.

This module handles repository cloning and initial indexing setup,
coordinating with the database layer for repository management.

Flow:
1. Repository Management:
   - Clone repository
   - Create/update repository records
   - Track repository changes

2. Transaction Handling:
   - Atomic operations
   - Error recovery
   - Resource cleanup

3. Indexing Integration:
   - File discovery
   - Batch processing
   - Graph projection
"""

import os
import tempfile
import subprocess
from typing import Optional, Set, Dict, Any, Tuple
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
from indexer.file_utils import get_files
from indexer.common import async_read_file

# Initialize the upsert coordinator
_upsert_coordinator = UpsertCoordinator()

@asynccontextmanager
async def repository_transaction():
    """[4.1] Context manager for repository operations.
    
    Flow:
    1. Begin transaction
    2. Execute operation
    3. Commit or rollback
    4. Clean up resources
    
    Yields:
        Transaction context for repository operations
    """
    temp_files = set()  # Track temporary files
    temp_dirs = set()   # Track temporary directories
    
    try:
        async with transaction_scope() as txn:
            try:
                # Create context with resource tracking
                context = {
                    'transaction': txn,
                    'temp_files': temp_files,
                    'temp_dirs': temp_dirs,
                    'create_temp_file': lambda: tempfile.mktemp(),
                    'create_temp_dir': lambda: tempfile.mkdtemp()
                }
                yield context
            except Exception as e:
                log(f"Repository transaction failed: {e}", level="error")
                raise
    finally:
        # Clean up temporary resources
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                log(f"Error cleaning up temporary file {file_path}: {e}", level="warning")
        
        for dir_path in temp_dirs:
            try:
                if os.path.exists(dir_path):
                    import shutil
                    shutil.rmtree(dir_path)
            except Exception as e:
                log(f"Error cleaning up temporary directory {dir_path}: {e}", level="warning")

@handle_async_errors(error_types=ProcessingError)
async def get_or_create_repo(
    repo_name: str,
    source_url: Optional[str] = None,
    repo_type: str = "active",
    active_repo_id: Optional[int] = None
) -> int:
    """[4.2] Retrieve or create a repository record.
    
    Flow:
    1. Initialize coordinator
    2. Upsert repository
    3. Return repository ID
    
    Args:
        repo_name: Name of the repository
        source_url: Optional source URL
        repo_type: Type of repository (active/reference)
        active_repo_id: Optional ID of active repository
        
    Returns:
        int: Repository identifier
        
    Raises:
        ProcessingError: If repository operation fails
    """
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
    """[4.3] Clone a git repository.
    
    Flow:
    1. Execute git clone
    2. Handle process output
    3. Verify clone success
    
    Args:
        repo_url: URL of repository to clone
        target_dir: Directory to clone into
        
    Returns:
        bool: True if clone successful, False otherwise
        
    Raises:
        ProcessingError: If clone operation fails
    """
    async with AsyncErrorBoundary(
        operation_name=f"cloning repository from {repo_url}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        try:
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
    """[4.4] Clone and index a reference repository.
    
    Flow:
    1. Clone repository
    2. Create repository record
    3. Process repository files
    4. Update graph projection
    
    Args:
        repo_url: URL of repository to clone
        repo_name: Optional repository name
        active_repo_id: Optional ID of active repository
        
    Raises:
        ProcessingError: If clone or indexing fails
    """
    async with AsyncErrorBoundary(
        operation_name=f"cloning and indexing repository from {repo_url}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        if not repo_name:
            repo_name = repo_url.split('/')[-1].replace('.git', '')
        
        async with repository_transaction() as context:
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
                await context['transaction'].track_repo_change(repo_id)
                
                # Index repository using unified indexer
                files = await get_files(temp_dir)
                await process_repository_indexing(temp_dir, repo_id, files=files)