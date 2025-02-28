import sys
import os
import pytest
import logging
import faulthandler
from unittest.mock import patch

# Import the mock database layer
from tests.mocks.db_mock import (
    mock_db_factory,
    patch_postgres,
    patch_neo4j
)

# Enable faulthandler for better error reporting
faulthandler.enable()

# Determine the repository root (assumes tests/ is in the repository root)
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Insert the repository root at the beginning of sys.path if it's not already there
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

@pytest.fixture(autouse=True)
def setup_logging():
    # Configure logging for tests
    logging.getLogger().setLevel(logging.DEBUG)
    return None

@pytest.fixture
def mock_databases():
    """Set up mock databases for testing.
    
    This fixture provides mock implementations of both PostgreSQL and Neo4j databases
    for consistent and reliable test execution without requiring actual database connections.
    
    Usage:
        def test_something(mock_databases):
            # Access the factory to customize behavior
            pg_pool = mock_databases.pg_pool
            neo4j_driver = mock_databases.neo4j_driver
            
            # Your test code here
            ...
    
    Returns:
        The mock_db_factory instance with initialized database mocks.
    """
    # Get mock patches
    pg_patches = patch_postgres()
    neo4j_patches = patch_neo4j()
    
    # Start all patches
    for p in pg_patches + neo4j_patches:
        p.start()
    
    # Configure the PostgreSQL mock with default test data
    pg_pool = mock_db_factory.create_postgres_pool()
    pg_pool.tables["repositories"] = mock_db_factory.get_data_fixture("repositories")
    pg_pool.tables["code_snippets"] = mock_db_factory.get_data_fixture("code_snippets")
    
    # Configure the Neo4j mock
    neo4j_driver = mock_db_factory.create_neo4j_driver()
    
    yield mock_db_factory
    
    # Stop all patches
    for p in pg_patches + neo4j_patches:
        p.stop()
    
    # Reset for next test
    mock_db_factory.reset_all()

@pytest.fixture
def postgres_mock(mock_databases):
    """Access only the PostgreSQL mock from the mock_databases fixture.
    
    This is a convenience fixture for tests that only need PostgreSQL mocking.
    
    Returns:
        The MockPostgresPool instance.
    """
    return mock_databases.pg_pool

@pytest.fixture
def neo4j_mock(mock_databases):
    """Access only the Neo4j mock from the mock_databases fixture.
    
    This is a convenience fixture for tests that only need Neo4j mocking.
    
    Returns:
        The MockNeo4jDriver instance.
    """
    return mock_databases.neo4j_driver 