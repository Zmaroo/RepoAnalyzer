"""Test complete indexing pipeline with coverage reporting."""

import pytest
import asyncio
import os
from typing import Dict, Any
from pathlib import Path
import inspect
import pytest_asyncio

from index import main_async
from parsers.types import FileType, FeatureCategory, ParserResult
from parsers.unified_parser import unified_parser
from db.psql import query, close_db_pool
from db.transaction import transaction_scope
from db.schema import drop_all_tables, create_all_tables
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ErrorBoundary,
    DatabaseError,
    ProcessingError
)
from utils.logger import log

@handle_async_errors()
@pytest_asyncio.fixture(autouse=True, scope="function")
async def setup_cleanup():
    """Setup and cleanup for each test."""
    log("Setting up test environment", context={"phase": "setup"})
    
    try:
        async with AsyncErrorBoundary("test database setup", error_types=(DatabaseError,)):
            await drop_all_tables()
            await create_all_tables()
        
        yield  # Run test
        
    except Exception as e:
        log("Setup failed", level="error", context={"error": str(e)})
        raise
    finally:
        log("Running cleanup", context={"phase": "cleanup"})
        try:
            async with AsyncErrorBoundary("test cleanup", error_types=(DatabaseError,)):
                async with transaction_scope() as txn:
                    # Clean test data
                    await query("DELETE FROM code_snippets WHERE repo_id IN (SELECT id FROM repositories WHERE repo_type = 'active')")
                    await query("DELETE FROM repositories WHERE repo_type = 'active'")
                
                # Close connections
                await close_db_pool()
                
            log("Cleanup completed successfully", context={"phase": "cleanup_complete"})
            
        except Exception as e:
            log("Cleanup failed", level="error", context={
                "phase": "cleanup_error",
                "error": str(e)
            })
            raise

@pytest.fixture
async def test_repo_id():
    """Create and return a test repository ID."""
    async with AsyncErrorBoundary("test repo creation", error_types=(DatabaseError,)):
        async with transaction_scope() as txn:
            repos = await query(
                "INSERT INTO repositories (repo_name, repo_type) VALUES ($1, $2) RETURNING id",
                "test-repo",
                "active"
            )
            repo_id = repos[0]['id']
            log("Created test repository", context={"repo_id": repo_id})
            return repo_id

class Args:
    """Mock CLI arguments."""
    def __init__(self, **kwargs):
        self.clean = kwargs.get('clean', True)
        self.index = kwargs.get('index', os.getcwd())
        self.clone_ref = kwargs.get('clone_ref', None)
        self.share_docs = kwargs.get('share_docs', None)
        self.search_docs = kwargs.get('search_docs', None)
        self.watch = kwargs.get('watch', False)

@pytest.mark.asyncio
async def test_python_indexing_pipeline(mock_databases):
    """Test complete Python file indexing pipeline."""
    
    log("Starting Python indexing pipeline test", context={"test": "python_indexing"})
    
    # Setup
    args = Args(clean=True, index=os.getcwd())
    
    try:
        # 1. Test main indexing flow
        async with AsyncErrorBoundary("main indexing", error_types=(ProcessingError, DatabaseError)):
            # Check if main_async is awaitable directly or needs to be called first
            if inspect.iscoroutinefunction(main_async):
                await main_async(args)
            elif inspect.iscoroutine(main_async(args)):
                await main_async(args)
            else:
                main_async(args)
            
            log("Main indexing completed", context={"status": "success"})
            
        # 2. Verify database records
        async with AsyncErrorBoundary("verification", error_types=(DatabaseError,)):
            # Check if repositories were created
            repos = await query("SELECT * FROM repositories")
            assert len(repos) > 0, "No repositories were created"
            
            # Check if code snippets were created
            snippets = await query("SELECT * FROM code_snippets")
            assert len(snippets) > 0, "No code snippets were created"
            
            log("Database verification completed", context={
                "repositories": len(repos),
                "snippets": len(snippets)
            })
            
    except Exception as e:
        log("Test failed", level="error", context={"error": str(e)})
        raise
    
    log("Python indexing pipeline test completed successfully")

def check_pattern_coverage(result: ParserResult) -> Dict[str, Any]:
    """Check which patterns were matched in the file."""
    coverage = {}
    
    # Syntax patterns
    if 'function' in result.features['syntax']:
        coverage['functions'] = len(result.features['syntax']['function'])
    if 'class' in result.features['syntax']:
        coverage['classes'] = len(result.features['syntax']['class'])
        
    # Documentation patterns
    if 'docstring' in result.features['documentation']:
        coverage['docstrings'] = len(result.features['documentation']['docstring'])
    
    # Structure patterns
    if 'import' in result.features['structure']:
        coverage['imports'] = len(result.features['structure']['import'])
        
    # Semantics patterns
    if 'type' in result.features['semantics']:
        coverage['types'] = len(result.features['semantics']['type'])
        
    return coverage

if __name__ == "__main__":
    asyncio.run(test_python_indexing_pipeline()) 