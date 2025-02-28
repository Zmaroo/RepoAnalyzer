"""
Test configuration and fixtures for the RepoAnalyzer project.

This module provides common fixtures and configuration for tests.
"""

import sys
import os
import pytest
import logging
import faulthandler
from unittest.mock import patch
import pytest_asyncio

# Enable faulthandler for better error reporting
faulthandler.enable()

# Add repository root to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Import mock database layer
from tests.mocks.db_mock import mock_db_factory, patch_postgres, patch_neo4j, reset_mock_factory

@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Configure logging for tests."""
    logging.basicConfig(level=logging.DEBUG)
    yield
    logging.basicConfig(level=logging.INFO)

@pytest_asyncio.fixture
async def mock_databases():
    """Set up mock implementations of PostgreSQL and Neo4j databases.
    
    This fixture provides mock implementations of the database layer for testing.
    It patches the database connection functions and provides access to the mocks
    for configuring custom behaviors and verifying operations.
    
    Example:
        ```python
        @pytest.mark.asyncio
        async def test_database_operations(mock_databases):
            # Get the PostgreSQL mock
            pg_mock = mock_databases.get_postgres_mock()
            
            # Configure custom behavior
            pg_mock.add_query_handler(
                "SELECT * FROM users",
                lambda *args: [{"id": 1, "username": "testuser"}]
            )
            
            # Run code that uses the database
            result = await my_function()
            
            # Verify operations
            operations = pg_mock.get_operations()
            assert len(operations) == 1
        ```
    
    Returns:
        MockDatabaseFactory: Factory for accessing the database mocks
    """
    # Start patches
    postgres_patches = patch_postgres()
    neo4j_patches = patch_neo4j()
    
    # Start all patches
    for p in postgres_patches:
        p.start()
    
    for p in neo4j_patches:
        p.start()
    
    # Yield the mock factory for test use
    yield mock_db_factory
    
    # Stop all patches and reset the factory
    for p in postgres_patches:
        p.stop()
    
    for p in neo4j_patches:
        p.stop()
    
    # Reset the factory for the next test
    mock_db_factory.reset_all()

@pytest_asyncio.fixture
async def postgres_mock(mock_databases):
    """Convenience fixture to access the PostgreSQL mock directly."""
    return mock_databases.get_postgres_mock()

@pytest_asyncio.fixture
async def neo4j_mock(mock_databases):
    """Convenience fixture to access the Neo4j mock directly."""
    return mock_databases.get_neo4j_mock() 