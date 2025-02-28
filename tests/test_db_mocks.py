"""
Example tests demonstrating how to use the mock database layer.

This module shows how to:
1. Set up database mocks
2. Customize mock behavior
3. Verify database operations
4. Test error handling
5. Use fixtures for common patterns
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock

# Import database operations
from db.psql import query as pg_query, execute as pg_execute
from db.neo4j_ops import run_query as neo4j_query
from db.upsert_ops import upsert_repository
from db.graph_sync import ensure_projection, invalidate_projection

# Import error types
from utils.error_handling import (
    PostgresError, Neo4jError, DatabaseError,
    RetryableNeo4jError, NonRetryableNeo4jError
)

# Import mock database layer
from tests.mocks.db_mock import mock_db_factory

# PostgreSQL Tests
@pytest.mark.asyncio
async def test_postgres_query(mock_databases):
    """Test querying from PostgreSQL and verify results."""
    # Get the PostgreSQL mock
    pg_mock = mock_databases.get_postgres_mock()
    
    # Clear any previous operations
    pg_mock.clear_operations()
    
    # Execute a query
    results = await pg_query("SELECT * FROM repositories")
    
    # Debug
    print("Results:", results)
    print("Type of results:", type(results))
    if results:
        print("Type of first result:", type(results[0]))
        print("Keys in first result:", results[0].keys() if hasattr(results[0], 'keys') else "No keys method")
    
    # Verify results
    assert len(results) == 2
    assert results[0]["name"] == "test-repo"
    
    # Verify the operation was recorded
    operations = pg_mock.get_operations()
    assert len(operations) >= 2  # Should have at least 2 operations (acquire and query)
    
    # Check that the query operation exists
    query_ops = [op for op in operations if op["type"] == "query"]
    assert len(query_ops) == 1
    assert query_ops[0]["query"] == "SELECT * FROM repositories"

@pytest.mark.asyncio
async def test_postgres_custom_handler(mock_databases):
    """Test adding a custom query handler for PostgreSQL."""
    # Get the PostgreSQL mock
    pg_mock = mock_databases.get_postgres_mock()
    
    # Clear any operations
    pg_mock.clear_operations()
    
    # Create a custom result to return
    custom_result = [{"id": 1, "username": "testuser"}]
    
    # Add a custom handler
    pg_mock.add_query_handler(
        "SELECT * FROM custom_users",
        lambda *args: custom_result
    )
    
    # Execute the query
    results = await pg_query("SELECT * FROM custom_users")
    
    # Verify results
    assert len(results) == 1
    assert results[0]["username"] == "testuser"

@pytest.mark.asyncio
async def test_postgres_insert(mock_databases):
    """Test inserting a new repository into PostgreSQL."""
    # Get the PostgreSQL mock
    pg_mock = mock_databases.get_postgres_mock()
    
    # Clear operations
    pg_mock.clear_operations()
    
    # Add a handler for the insert operation
    pg_mock.add_query_handler(
        "INSERT INTO repositories",
        lambda *args: [{"id": 3, "name": args[0][0], "url": args[0][1]}]
    )
    
    # Execute the insert
    await pg_execute(
        "INSERT INTO repositories (name, url) VALUES ($1, $2)",
        ("new-repo", "https://github.com/test/new-repo")
    )
    
    # Verify the operation was recorded
    operations = pg_mock.get_operations()
    assert len(operations) >= 1
    
    # Check that there's at least one query operation
    query_ops = [op for op in operations if op["type"] == "query"]
    assert len(query_ops) >= 1

@pytest.mark.asyncio
async def test_postgres_error_handling(mock_databases):
    """Test error handling with PostgreSQL."""
    # Get the PostgreSQL mock
    pg_mock = mock_databases.get_postgres_mock()
    
    # Set up an error
    pg_mock.set_error_for_next_query(PostgresError("Connection refused"))
    
    # Execute a query directly on the mock that should fail
    with pytest.raises(PostgresError) as excinfo:
        await pg_mock.handle_query("SELECT * FROM repositories", None)
    
    # Verify the error
    assert "Connection refused" in str(excinfo.value)

# Neo4j Tests
@pytest.mark.asyncio
async def test_neo4j_query(mock_databases):
    """Test querying from Neo4j and verify results."""
    # Get the Neo4j mock
    neo4j_mock = mock_databases.get_neo4j_mock()
    
    # Execute a query
    results = await neo4j_query("MATCH (n) RETURN n")
    
    # Verify results
    assert len(results) == 2
    assert results[0]["n"]["labels"] == ["File"]
    
    # Verify the operation was recorded
    operations = neo4j_mock.get_operations()
    assert len(operations) == 1
    assert "MATCH (n) RETURN n" in operations[0]["query"]

@pytest.mark.asyncio
async def test_neo4j_retry_mechanism(mock_databases):
    """Test the retry mechanism for Neo4j with retryable errors."""
    # Get the Neo4j mock
    neo4j_mock = mock_databases.get_neo4j_mock()
    
    # Set up a retryable error that will succeed after 2 retries
    neo4j_mock.set_error_for_next_query(
        RetryableNeo4jError("Connection reset by peer"),
        retry_count=2
    )
    
    # Execute the query with retry logic
    with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
        results = await neo4j_query("MATCH (n) RETURN n")
    
    # Verify the sleep was called for retries
    assert mock_sleep.call_count >= 2
    
    # Verify we got results after retries
    assert len(results) == 2

@pytest.mark.asyncio
async def test_neo4j_non_retryable_error(mock_databases):
    """Test that non-retryable errors are not retried."""
    # Get the Neo4j mock
    neo4j_mock = mock_databases.get_neo4j_mock()
    
    # Set up a non-retryable error
    neo4j_mock.set_error_for_next_query(
        NonRetryableNeo4jError("syntax error in cypher query")
    )
    
    # Execute the query with retry logic
    with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
        with pytest.raises(DatabaseError) as excinfo:
            await neo4j_query("MATCH (n) RETURN n")
    
    # Verify no retries were attempted
    assert mock_sleep.call_count == 0
    
    # Verify the error
    assert "syntax error in cypher query" in str(excinfo.value)

# Integrated Tests
@pytest.mark.asyncio
async def test_integrated_database_operations(mock_databases):
    """Test operations spanning both PostgreSQL and Neo4j."""
    # Get both mocks
    pg_mock = mock_databases.get_postgres_mock()
    neo4j_mock = mock_databases.get_neo4j_mock()
    
    # Clear operations
    pg_mock.clear_operations()
    
    # Add custom handler for repository operations
    pg_mock.add_query_handler(
        "SELECT * FROM repositories WHERE id = $1",
        lambda *args: [{"id": args[0], "name": "test-repo", "url": "https://github.com/test/test-repo"}]
    )
    
    # Execute database operations
    repo_data = await pg_query("SELECT * FROM repositories WHERE id = $1", (1,))
    graph_data = await neo4j_query("MATCH (r:Repository {id: $id}) RETURN r", {"id": 1})
    
    # Verify results
    assert repo_data[0]["name"] == "test-repo"
    assert len(graph_data) > 0
    assert graph_data[0]["r"]["name"] == "test-repo"

@pytest.mark.asyncio
async def test_graph_projection_operations(mock_databases):
    """Test graph projection operations."""
    # Get the Neo4j mock
    neo4j_mock = mock_databases.get_neo4j_mock()
    
    # Add custom handlers for projection operations
    # First, handle the node count query
    neo4j_mock.add_query_handler(
        r"MATCH \(n:Code \{repo_id: \$repo_id\}\)\s+RETURN count\(n\)",
        lambda **kwargs: [{"count": 10}]  # Return node count > 0
    )
    
    # Then, handle the graph projection query
    neo4j_mock.add_query_handler(
        r"CALL gds.graph.project.cypher",
        lambda **kwargs: [{"graphName": f"code-repo-{kwargs.get('repo_id', 1)}", "nodeCount": 10, "relationshipCount": 5}]
    )
    
    # Test ensure_projection
    result = await ensure_projection(1)
    
    # Verify the result
    assert result is True
    
    # Verify operations were recorded
    operations = neo4j_mock.get_operations()
    assert len(operations) >= 2

@pytest.mark.asyncio
async def test_operation_recording(mock_databases):
    """Test that operations are recorded in transactions."""
    # Get the PostgreSQL mock
    pg_mock = mock_databases.get_postgres_mock()
    
    # Clear any previous operations
    pg_mock.clear_operations()
    
    # Execute multiple queries
    await pg_query("SELECT * FROM repositories")
    await pg_query("SELECT * FROM repositories WHERE id = $1", (1,))
    
    # Verify operations were recorded in order
    operations = pg_mock.get_operations()
    assert len(operations) >= 4  # Should have at least 4 operations (2 acquires and 2 queries)
    
    # Check that at least two query operations exist
    query_ops = [op for op in operations if op["type"] == "query"]
    assert len(query_ops) >= 2
    
    # Verify the order of operations
    assert query_ops[0]["query"] == "SELECT * FROM repositories"
    assert query_ops[1]["query"] == "SELECT * FROM repositories WHERE id = $1"

@pytest.mark.asyncio
async def test_custom_data_fixtures(mock_databases):
    """Test using custom data fixtures."""
    # Get the PostgreSQL mock
    pg_mock = mock_databases.get_postgres_mock()
    
    # Clear operations
    pg_mock.clear_operations()
    
    # Define custom data
    custom_users = [
        {"id": 1, "username": "admin", "is_active": True},
        {"id": 2, "username": "user", "is_active": False}
    ]
    
    # Add a handler for the custom data
    pg_mock.add_query_handler(
        "SELECT * FROM custom_users",
        lambda *args: custom_users
    )
    
    # Query the custom data
    results = await pg_query("SELECT * FROM custom_users")
    
    # Verify results
    assert len(results) == 2
    assert results[0]["username"] == "admin"
    assert results[1]["is_active"] is False 