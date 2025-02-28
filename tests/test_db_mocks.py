"""
Tests demonstrating usage of the mock database layer.

This module shows how to:
1. Set up database mocks for PostgreSQL and Neo4j
2. Configure custom behaviors and responses
3. Verify queries and operations
4. Test error handling scenarios
5. Use fixtures for common patterns
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

# Import the database operations to test
from db.psql import query, execute, init_db_pool, close_db_pool
from db.neo4j_ops import run_query, run_query_with_retry
from db.upsert_ops import upsert_doc, upsert_code_snippet
from db.graph_sync import ensure_projection

# Import error types
from utils.error_handling import (
    DatabaseError, 
    PostgresError, 
    Neo4jError,
    RetryableNeo4jError,
    NonRetryableNeo4jError
)

# Import the mock database layer
from tests.mocks.db_mock import (
    mock_db_factory,
    patch_postgres,
    patch_neo4j
)

# Create a fixture for database mocking
@pytest.fixture
def mock_databases():
    """Set up mock databases for testing."""
    # Get mock patches
    pg_patches = patch_postgres()
    neo4j_patches = patch_neo4j()
    
    # Start all patches
    for p in pg_patches + neo4j_patches:
        p.start()
    
    # Configure the PostgreSQL mock with test data
    pg_pool = mock_db_factory.create_postgres_pool()
    pg_pool.tables["repositories"] = mock_db_factory.get_data_fixture("repositories")
    pg_pool.tables["code_snippets"] = mock_db_factory.get_data_fixture("code_snippets")
    
    # Configure the Neo4j mock with test data
    neo4j_driver = mock_db_factory.create_neo4j_driver()
    
    yield mock_db_factory
    
    # Stop all patches
    for p in pg_patches + neo4j_patches:
        p.stop()
    
    # Reset for next test
    mock_db_factory.reset_all()

# Test PostgreSQL operations
@pytest.mark.asyncio
async def test_postgres_query(mock_databases):
    """Test querying from PostgreSQL."""
    # Initialize the database pool
    await init_db_pool()
    
    # Run a query
    repositories = await query("SELECT * FROM repositories WHERE repo_type = $1", ["active"])
    
    # Check the results
    assert len(repositories) == 2
    assert repositories[0]["repo_name"] == "test-repo-1"
    assert repositories[1]["repo_name"] == "test-repo-2"
    
    # Close the pool
    await close_db_pool()

@pytest.mark.asyncio
async def test_postgres_custom_handler(mock_databases):
    """Test adding a custom query handler."""
    # Get the PostgreSQL pool
    pg_pool = mock_databases.pg_pool
    
    # Add a custom handler for a specific query
    pg_pool.register_query_handler(
        r"SELECT.*FROM\s+repositories\s+WHERE\s+id\s*=\s*\$1",
        lambda query, args: [{"id": args[0][0], "repo_name": f"Custom-Repo-{args[0][0]}"}]
    )
    
    # Initialize the database pool
    await init_db_pool()
    
    # Run the query that should use our custom handler
    repo = await query("SELECT * FROM repositories WHERE id = $1", [42])
    
    # Check the results
    assert len(repo) == 1
    assert repo[0]["repo_name"] == "Custom-Repo-42"
    
    # Close the pool
    await close_db_pool()

@pytest.mark.asyncio
async def test_postgres_insert(mock_databases):
    """Test inserting into PostgreSQL."""
    # Get the PostgreSQL pool
    pg_pool = mock_databases.pg_pool
    
    # Check initial state
    initial_count = len(pg_pool.tables["repositories"])
    
    # Initialize the database pool
    await init_db_pool()
    
    # Insert a new repository
    await execute(
        "INSERT INTO repositories (repo_name, repo_type, repo_url) VALUES ($1, $2, $3) RETURNING id", 
        ["new-test-repo", "active", "https://github.com/test/new-repo"]
    )
    
    # Query to verify insertion
    repositories = await query("SELECT * FROM repositories WHERE repo_name = $1", ["new-test-repo"])
    
    # Check the results
    assert len(repositories) == 1
    assert repositories[0]["repo_name"] == "new-test-repo"
    assert len(pg_pool.tables["repositories"]) == initial_count + 1
    
    # Close the pool
    await close_db_pool()

@pytest.mark.asyncio
async def test_postgres_error_handling(mock_databases):
    """Test error handling with PostgreSQL."""
    # Initialize the database pool
    await init_db_pool()
    
    # Create a failing transaction
    pg_pool = mock_databases.pg_pool
    connection = await pg_pool.acquire()
    
    # Configure the transaction to fail
    original_factory = connection.transaction_factory
    connection.transaction_factory = lambda conn: original_factory(
        conn, should_fail=True, failure_type=PostgresError, failure_message="Simulated database error"
    )
    
    # Attempt a transaction that should fail
    with pytest.raises(PostgresError) as exc_info:
        async with connection.transaction():
            await connection.execute("SELECT 1")
    
    assert "Simulated database error" in str(exc_info.value)
    
    # Release the connection
    await pg_pool.release(connection)
    
    # Close the pool
    await close_db_pool()

# Test Neo4j operations
@pytest.mark.asyncio
async def test_neo4j_query(mock_databases):
    """Test querying from Neo4j."""
    # Set up Neo4j mock data
    neo4j_driver = mock_databases.neo4j_driver
    
    # Add a custom handler for a specific query
    neo4j_driver.register_query_handler(
        r"MATCH\s+\(r:Repository\)",
        lambda query, params: [
            {"id": 1, "name": "test-repo-1"},
            {"id": 2, "name": "test-repo-2"}
        ]
    )
    
    # Run a Neo4j query
    result = await run_query("MATCH (r:Repository) RETURN r")
    
    # Check the results
    assert result is not None
    assert len(result) == 2
    assert result[0]["name"] == "test-repo-1"
    assert result[1]["name"] == "test-repo-2"

@pytest.mark.asyncio
async def test_neo4j_retry_mechanism(mock_databases):
    """Test the Neo4j retry mechanism with retryable errors."""
    # Set up Neo4j mock
    neo4j_driver = mock_databases.neo4j_driver
    
    # Create a query handler that fails with retryable error on first call, succeeds on second
    call_count = 0
    
    def failing_handler(query, params):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            raise RetryableNeo4jError("Connection reset by peer")
        
        return [{"success": True}]
    
    # Register the handler
    neo4j_driver.register_query_handler(
        r"MATCH\s+\(n:TestRetry\)",
        failing_handler
    )
    
    # Run the query with retry
    with patch('db.neo4j_ops.driver', neo4j_driver):
        result = await run_query_with_retry("MATCH (n:TestRetry) RETURN n")
    
    # Check that the query was retried and succeeded
    assert call_count == 2
    assert result[0]["success"] is True

@pytest.mark.asyncio
async def test_neo4j_non_retryable_error(mock_databases):
    """Test that non-retryable errors are not retried."""
    # Set up Neo4j mock
    neo4j_driver = mock_databases.neo4j_driver
    
    # Create a query handler that fails with non-retryable error
    def failing_handler(query, params):
        raise NonRetryableNeo4jError("Syntax error in query")
    
    # Register the handler
    neo4j_driver.register_query_handler(
        r"MATCH\s+\(n:TestNonRetry\)",
        failing_handler
    )
    
    # Run the query with retry and expect failure
    with pytest.raises(Neo4jError):
        with patch('db.neo4j_ops.driver', neo4j_driver):
            await run_query_with_retry("MATCH (n:TestNonRetry) RETURN n")

# Test integrated scenarios with both databases
@pytest.mark.asyncio
async def test_integrated_database_operations(mock_databases):
    """Test operations that span both PostgreSQL and Neo4j."""
    # Initialize the PostgreSQL pool
    await init_db_pool()
    
    # Configure mocks
    pg_pool = mock_databases.pg_pool
    neo4j_driver = mock_databases.neo4j_driver
    
    # Add custom handlers for Neo4j
    neo4j_driver.register_query_handler(
        r"CALL\s+gds\.graph\.project",
        lambda query, params: [{"graphName": f"code-repo-{params.get('graphName', '1')}"}]
    )
    
    # Enable projection
    repo_id = 1
    with patch('db.graph_sync.run_query', side_effect=lambda query, params=None, **kwargs: 
              neo4j_driver.handle_query(query, params)):
        # This calls Neo4j to create a graph projection
        projection_result = await ensure_projection(repo_id)
    
    # Check that the projection was created
    assert projection_result is True
    
    # Close the PostgreSQL pool
    await close_db_pool()

@pytest.mark.asyncio
async def test_operation_recording(mock_databases):
    """Test that operations are recorded in transactions."""
    # Initialize the PostgreSQL pool
    await init_db_pool()
    
    # Get a connection and start a transaction
    pg_pool = mock_databases.pg_pool
    connection = await pg_pool.acquire()
    
    # Execute operations in a transaction
    async with connection.transaction() as txn:
        await connection.fetch("SELECT * FROM repositories")
        await connection.execute("INSERT INTO repositories (repo_name) VALUES ($1)", "recorded-repo")
    
    # Check that operations were recorded
    assert len(txn.operations) == 2
    assert txn.operations[0]["type"] == "fetch"
    assert "SELECT * FROM repositories" in txn.operations[0]["args"]
    assert txn.operations[1]["type"] == "execute"
    assert "INSERT INTO repositories" in txn.operations[1]["args"]
    
    # Release the connection
    await pg_pool.release(connection)
    
    # Close the pool
    await close_db_pool()

@pytest.mark.asyncio
async def test_custom_data_fixtures(mock_databases):
    """Test using custom data fixtures."""
    # Create and register a custom fixture
    custom_repositories = [
        {"id": 101, "repo_name": "custom-repo-1", "features": ["feature1", "feature2"]},
        {"id": 102, "repo_name": "custom-repo-2", "features": ["feature3"]}
    ]
    mock_databases.register_data_fixture("custom_repositories", custom_repositories)
    
    # Load the fixture to the PostgreSQL table
    mock_databases.load_fixture_to_postgres("custom_repositories", "repositories")
    
    # Initialize the database pool
    await init_db_pool()
    
    # Query the custom data
    repositories = await query("SELECT * FROM repositories")
    
    # Verify the data
    assert len(repositories) == 2
    assert repositories[0]["id"] == 101
    assert repositories[0]["repo_name"] == "custom-repo-1"
    assert repositories[1]["id"] == 102
    
    # Close the pool
    await close_db_pool()

# Run the tests with pytest
if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 