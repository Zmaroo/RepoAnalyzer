"""Repository cloning and indexing coordination."""

import os
import tempfile
import subprocess
from typing import Optional
from utils.logger import log
from db.upsert_ops import upsert_repository
from indexer.unified_indexer import process_repository_indexing
from parsers.models import FileType, FileClassification  # Add imports from models
import asyncio
from contextlib import asynccontextmanager
from config import postgres_config, neo4j_config

@asynccontextmanager
async def repository_transaction():
    """
    Context manager for repository operations ensuring proper cleanup.
    """
    try:
        yield
    except Exception as e:
        log(f"Repository transaction failed: {e}", level="error")
        raise
    finally:
        # Ensure any temporary resources are cleaned up
        pass

async def get_or_create_repo(
    repo_name: str,
    source_url: Optional[str] = None,
    repo_type: str = "active",
    active_repo_id: Optional[int] = None
) -> int:
    """
    Retrieves or creates a repository using the centralized upsert operation.
    """
    async with repository_transaction():
        repo_data = {
            'repo_name': repo_name,
            'source_url': source_url,
            'repo_type': repo_type,
            'active_repo_id': active_repo_id
        }
        return await upsert_repository(repo_data)

async def clone_repository(repo_url: str, target_dir: str) -> bool:
    """Clone a git repository to target directory."""
    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, target_dir],
            capture_output=True,
            text=True,
            check=True
        )
        log(f"Successfully cloned {repo_url}", level="info")
        return True
        
    except subprocess.CalledProcessError as e:
        log(f"Git clone failed: {e.stderr}", level="error")
        return False
    except Exception as e:
        log(f"Error cloning repository: {e}", level="error")
        return False

async def clone_and_index_repo(
    repo_url: str,
    repo_name: Optional[str] = None,
    active_repo_id: Optional[int] = None
) -> None:
    """Clone and index a reference repository."""
    if not repo_name:
        repo_name = repo_url.split('/')[-1].replace('.git', '')
    
    async with repository_transaction():
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Clone repository
                await clone_repository(repo_url, temp_dir)
                
                # Create repository record
                repo_id = await get_or_create_repo(
                    repo_name,
                    source_url=repo_url,
                    repo_type="reference",
                    active_repo_id=active_repo_id
                )
                
                # Index repository using unified indexer
                await process_repository_indexing(temp_dir, repo_id, repo_type="reference")
                
            except Exception as e:
                log(f"Error processing reference repository: {e}", level="error")
                raise