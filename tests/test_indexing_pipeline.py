"""Test complete indexing pipeline with coverage reporting."""

import pytest
import asyncio
import os
from typing import Dict, Any
from pathlib import Path

from index import main_async
from parsers.models import FileType, FeatureCategory, ParserResult
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

@pytest.fixture(autouse=True)
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

@handle_async_errors(error_types=(ProcessingError, DatabaseError))
async def test_python_indexing_pipeline():
    """Test complete Python file indexing pipeline."""
    
    log("Starting Python indexing pipeline test", context={"test": "python_indexing"})
    
    # Setup
    args = Args(clean=True, index=os.getcwd())
    
    try:
        # 1. Test main indexing flow
        async with AsyncErrorBoundary("main indexing", error_types=(ProcessingError, DatabaseError)):
            await main_async(args)
            log("Main indexing completed", context={"phase": "indexing"})
        
        # 2. Verify database entries
        async with AsyncErrorBoundary("database verification", error_types=DatabaseError):
            repos = await query("SELECT * FROM repositories WHERE repo_type = 'active'")
            assert len(repos) > 0, "No repository entry created"
            repo_id = repos[0]['id']
            
            python_files = await query(
                "SELECT * FROM code_snippets WHERE repo_id = $1 AND file_path LIKE '%.py'",
                repo_id
            )
            assert len(python_files) > 0, "No Python files indexed"
            
            log("Database verification completed", context={
                "phase": "verification",
                "python_files": len(python_files)
            })
        
        # 3. Test pattern categories coverage
        async with AsyncErrorBoundary("pattern coverage", error_types=ProcessingError):
            for file_data in python_files:
                with ErrorBoundary(f"parsing {file_data['file_path']}", error_types=ProcessingError):
                    with open(file_data['file_path'], 'r') as f:
                        content = f.read()
                    
                    result = await unified_parser.parse_file(file_data['file_path'], content)
                    assert isinstance(result, ParserResult), "Parser failed to return result"
                    
                    # Log pattern coverage
                    coverage_stats = {}
                    for category in FeatureCategory:
                        features = result.features.get(category.value, {})
                        coverage_stats[category.value] = len(features)
                        
                    log(f"Pattern coverage for {file_data['file_path']}", context={
                        "phase": "pattern_analysis",
                        "coverage": coverage_stats
                    })
        
        # 4. Test specific Python patterns
        async with AsyncErrorBoundary("python pattern testing", error_types=ProcessingError):
            with open('index.py', 'r') as f:
                index_content = f.read()
            
            index_result = await unified_parser.parse_file('index.py', index_content)
            coverage = check_pattern_coverage(index_result)
            
            log("Pattern coverage results", context={
                "file": "index.py",
                "coverage": coverage
            })
            
            # Verify minimum pattern matches with detailed logging
            for pattern, min_count in {
                'functions': 3,
                'imports': 5,
                'docstrings': 1
            }.items():
                actual = coverage.get(pattern, 0)
                assert actual >= min_count, f"Missing {pattern} (found {actual}, expected {min_count})"
                log(f"Pattern check passed: {pattern}", context={
                    "expected": min_count,
                    "actual": actual
                })
                
    except Exception as e:
        log("Test failed", level="error", context={
            "error": str(e),
            "phase": "test_execution"
        })
        raise
    
    log("Python indexing pipeline test completed successfully", context={
        "test": "python_indexing",
        "status": "complete"
    })

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