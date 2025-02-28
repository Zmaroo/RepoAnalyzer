# Mock Database Layer Guide

This guide explains how to effectively use the mock database layer for testing in the RepoAnalyzer project. The mock database layer provides consistent and reliable database mocking for both PostgreSQL and Neo4j operations, allowing tests to run without requiring actual database connections.

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Core Concepts](#core-concepts)
4. [PostgreSQL Mocking](#postgresql-mocking)
5. [Neo4j Mocking](#neo4j-mocking)
6. [Advanced Use Cases](#advanced-use-cases)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Introduction

The mock database layer provides:

- Mocks for PostgreSQL and Neo4j databases that mimic their respective APIs
- Support for transactions with proper operation recording
- Configurable query handlers for dynamic test responses
- Error simulation capabilities
- Fixture management for test data consistency

This implementation allows tests to verify database operations without requiring actual database servers, ensuring tests are fast, reliable, and can run in any environment.

## Getting Started

### Basic Setup

The simplest way to use the mock database layer is through the provided fixtures in `conftest.py`:

```python
@pytest.mark.asyncio
async def test_my_database_function(mock_databases):
    # Mock databases are already set up and patched
    
    # Your test code here...
    result = await query("SELECT * FROM repositories")
    assert len(result) > 0
```

### Available Fixtures

- `mock_databases`: Provides access to both PostgreSQL and Neo4j mocks
- `postgres_mock`: Convenience fixture for PostgreSQL-only tests
- `neo4j_mock`: Convenience fixture for Neo4j-only tests

## Core Concepts

### Mock Database Factory

The `mock_db_factory` is a singleton instance that manages mock database instances. It provides methods to:

- Create database mocks
- Register and retrieve data fixtures
- Reset all mocks between tests

### Patching Functions

The mock database layer includes functions to patch database-related functions:

- `patch_postgres()`: Returns a list of patches for PostgreSQL functions
- `patch_neo4j()`: Returns a list of patches for Neo4j functions

### Mock Transactions

Both PostgreSQL and Neo4j mocks support transactions with proper context managers, allowing you to test transaction-based code and verify operations performed within transactions.

## PostgreSQL Mocking

### Basic Query Mocking

The PostgreSQL mock automatically handles common queries based on registered handlers. By default, it can handle basic SELECT and INSERT queries for common tables.

### Custom Query Handlers

You can register custom handlers for specific query patterns:

```python
def test_custom_query_handler(postgres_mock):
    # Register a custom handler for a specific query pattern
    postgres_mock.register_query_handler(
        r"SELECT.*FROM\s+users\s+WHERE\s+id\s*=\s*\$1",
        lambda query, args: [{"id": args[0][0], "username": f"user-{args[0][0]}"}]
    )
    
    # Now queries matching this pattern will use your handler
    result = await query("SELECT * FROM users WHERE id = $1", [42])
    assert result[0]["username"] == "user-42"
```

### Simulating Errors

You can configure transactions to fail for testing error handling:

```python
@pytest.mark.asyncio
async def test_error_handling(postgres_mock):
    # Get a connection
    connection = await postgres_mock.acquire()
    
    # Configure the transaction to fail
    original_factory = connection.transaction_factory
    connection.transaction_factory = lambda conn: original_factory(
        conn, should_fail=True, 
        failure_type=PostgresError, 
        failure_message="Simulated database error"
    )
    
    # This transaction will fail
    with pytest.raises(PostgresError):
        async with connection.transaction():
            await connection.execute("SELECT 1")
```

## Neo4j Mocking

### Basic Query Mocking

The Neo4j mock handles Cypher queries through registered handlers:

```python
def test_neo4j_query(neo4j_mock):
    # Add a custom handler
    neo4j_mock.register_query_handler(
        r"MATCH\s+\(r:Repository\)",
        lambda query, params: [
            {"id": 1, "name": "repo-1"},
            {"id": 2, "name": "repo-2"}
        ]
    )
    
    # Run a query
    result = await run_query("MATCH (r:Repository) RETURN r")
    assert len(result) == 2
```

### Testing Retry Mechanisms

The Neo4j mock includes support for simulating retryable and non-retryable errors:

```python
@pytest.mark.asyncio
async def test_retry_mechanism(neo4j_mock):
    # Create a counter to track calls
    call_count = 0
    
    def failing_handler(query, params):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # Fail on first call with a retryable error
            raise RetryableNeo4jError("Connection reset")
        
        # Succeed on second call
        return [{"success": True}]
    
    # Register the handler
    neo4j_mock.register_query_handler(
        r"MATCH\s+\(n:TestRetry\)",
        failing_handler
    )
    
    # Run the query with retry
    result = await run_query_with_retry("MATCH (n:TestRetry) RETURN n")
    
    # Verify it was retried and succeeded
    assert call_count == 2
    assert result[0]["success"] is True
```

## Advanced Use Cases

### Custom Data Fixtures

You can create and use custom data fixtures for tests:

```python
def test_with_custom_data(mock_databases):
    # Create a custom fixture
    custom_data = [
        {"id": 1, "name": "Custom 1"},
        {"id": 2, "name": "Custom 2"}
    ]
    
    # Register and load it
    mock_databases.register_data_fixture("custom_data", custom_data)
    mock_databases.load_fixture_to_postgres("custom_data", "my_table")
    
    # Use it in your test
    result = await query("SELECT * FROM my_table")
    assert len(result) == 2
```

### Operation Recording and Verification

You can verify what operations were performed within a transaction:

```python
@pytest.mark.asyncio
async def test_operations(postgres_mock):
    # Get a connection and start a transaction
    connection = await postgres_mock.acquire()
    
    async with connection.transaction() as txn:
        await connection.execute("INSERT INTO repositories (name) VALUES ($1)", "test-repo")
    
    # Verify operations
    assert len(txn.operations) == 1
    assert txn.operations[0]["type"] == "execute"
    assert "INSERT INTO repositories" in txn.operations[0]["args"]
```

### Testing Integrated Database Operations

You can test code that uses both PostgreSQL and Neo4j:

```python
@pytest.mark.asyncio
async def test_integrated_operations(mock_databases):
    # Configure both mocks
    pg_pool = mock_databases.pg_pool
    neo4j_driver = mock_databases.neo4j_driver
    
    # Add custom handlers for both
    pg_pool.register_query_handler(...)
    neo4j_driver.register_query_handler(...)
    
    # Test integrated functions
    result = await your_function_that_uses_both_databases()
```

## Best Practices

1. **Reset Between Tests**: Always use the fixture system to ensure mocks are reset between tests.

2. **Use Specific Fixtures**: For clarity, use `postgres_mock` or `neo4j_mock` if your test only needs one database.

3. **Custom Handlers**: Register custom handlers for specific queries rather than trying to patch the generic handlers.

4. **Verify Operations**: Use transaction operation recording to verify that the right operations were performed.

5. **Data Fixtures**: Use the data fixture system to maintain consistent test data.

6. **Simulate Latency**: For testing timeouts, you can add asyncio sleep calls in your custom handlers.

7. **Mock Consistency**: Ensure your mock responses are consistent with the real database schema.

## Troubleshooting

### Mock Not Applied

If your code is still hitting the real database:

- Ensure you're using the fixture in your test
- Check that the function you're calling is properly patched
- Verify no direct imports of connection objects bypass the patching

### Unexpected Query Results

If your mock returns unexpected results:

- Check the query pattern in your custom handler
- Ensure the mock data is properly loaded
- Verify the query parameters are correctly handled

### Missing Tables

If your code expects a table that doesn't exist in the mock:

```python
def test_with_missing_table(postgres_mock):
    # Add a missing table
    postgres_mock.tables["my_new_table"] = []
    
    # Now you can use it
    await query("SELECT * FROM my_new_table")
```

## Example Use Cases

### Testing Repository Query Function

```python
@pytest.mark.asyncio
async def test_get_repository_by_name(mock_databases):
    # Setup test data
    mock_databases.pg_pool.tables["repositories"] = [
        {"id": 1, "repo_name": "test-repo", "repo_type": "active"}
    ]
    
    # Test the function
    repo = await get_repository_by_name("test-repo")
    
    # Verify result
    assert repo is not None
    assert repo["id"] == 1
    assert repo["repo_name"] == "test-repo"
```

### Testing Graph Projection

```python
@pytest.mark.asyncio
async def test_graph_projection(mock_databases):
    # Setup Neo4j mock
    neo4j_driver = mock_databases.neo4j_driver
    neo4j_driver.register_query_handler(
        r"CALL\s+gds\.graph\.project",
        lambda query, params: [
            {"graphName": params.get("graphName", "default-graph")}
        ]
    )
    
    # Test projection creation
    result = await create_repository_projection(1)
    
    # Verify result
    assert result is True
```

### Testing Error Recovery

```python
@pytest.mark.asyncio
async def test_error_recovery(mock_databases):
    # Configure Neo4j to fail with retryable error
    neo4j_driver = mock_databases.neo4j_driver
    call_count = 0
    
    def failing_handler(query, params):
        nonlocal call_count
        call_count += 1
        
        if call_count <= 2:  # Fail twice
            raise RetryableNeo4jError("Connection reset")
        return [{"success": True}]
    
    neo4j_driver.register_query_handler(
        r"MATCH\s+\(n\)",
        failing_handler
    )
    
    # Test the function with retry
    result = await run_query_with_retry("MATCH (n) RETURN n")
    
    # Verify retry behavior
    assert call_count == 3  # Initial + 2 retries
    assert result[0]["success"] is True
```

This mock database layer should significantly improve the consistency and reliability of your tests while making them faster and more predictable.
