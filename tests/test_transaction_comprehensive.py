"""
Comprehensive Transaction Testing

This file contains more thorough tests for the transaction system, 
covering various success and failure scenarios with detailed assertions.

The tests in this file verify the transaction coordination system that manages
transactions across both PostgreSQL and Neo4j databases. This is a critical component
of the application as it ensures data consistency across different storage systems.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import sys
from contextlib import asynccontextmanager

# Import the required modules for testing
from db.transaction import transaction_scope, TransactionCoordinator
from utils.error_handling import PostgresError, Neo4jError, TransactionError, CacheError

@pytest.fixture
def mock_database_connections():
    """
    Set up comprehensive mocks for database connections.
    
    This fixture creates mock objects for all database-related components:
    - PostgreSQL connection pool, connection, and transaction
    - Neo4j driver, session, and transaction
    - Cache coordinator for cache invalidation
    
    Returns a dictionary of all mock objects for easy access in tests.
    """
    # PostgreSQL mocks
    mock_pg_transaction = MagicMock()
    mock_pg_transaction.start = AsyncMock()
    mock_pg_transaction.commit = AsyncMock()
    mock_pg_transaction.rollback = AsyncMock()
    
    mock_pg_conn = MagicMock()
    mock_pg_conn.transaction = MagicMock(return_value=mock_pg_transaction)
    
    mock_pool = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_pg_conn)
    mock_pool.release = AsyncMock()
    
    # Neo4j mocks
    mock_neo4j_transaction = MagicMock()
    mock_neo4j_transaction.commit = AsyncMock()
    mock_neo4j_transaction.rollback = AsyncMock()
    
    mock_neo4j_session = MagicMock()
    mock_neo4j_session.begin_transaction = MagicMock(return_value=mock_neo4j_transaction)
    mock_neo4j_session.close = MagicMock()
    
    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_neo4j_session)
    
    # Cache coordinator mock
    mock_cache_coordinator = MagicMock()
    mock_cache_coordinator.invalidate_pattern = AsyncMock()
    
    # Create a dictionary of all mocks for easy access
    mocks = {
        'pg_transaction': mock_pg_transaction,
        'pg_conn': mock_pg_conn,
        'pool': mock_pool,
        'neo4j_transaction': mock_neo4j_transaction,
        'neo4j_session': mock_neo4j_session,
        'driver': mock_driver,
        'cache_coordinator': mock_cache_coordinator
    }
    
    # Apply all patches
    with patch('db.transaction._pool', mock_pool), \
         patch('db.transaction.get_connection', AsyncMock(return_value=mock_pg_conn)), \
         patch('db.transaction.driver', mock_driver), \
         patch('db.transaction.cache_coordinator', mock_cache_coordinator):
        yield mocks

@pytest.mark.asyncio
async def test_transaction_scope_success_path(mock_database_connections):
    """
    Test the happy path of transaction_scope.
    
    This test verifies that when everything works correctly:
    1. Both PostgreSQL and Neo4j transactions are started
    2. Both transactions are committed
    3. Connections are properly cleaned up
    4. Cache invalidation is performed
    
    This is the most common scenario and must work flawlessly.
    """
    # Arrange
    mocks = mock_database_connections
    
    # Act
    async with transaction_scope() as coordinator:
        # Perform some operations
        await coordinator.track_repo_change(123)
        await coordinator.track_cache_invalidation("repo_cache")
    
    # Assert
    # Verify PostgreSQL transaction started and committed
    mocks['pg_transaction'].start.assert_called_once()
    mocks['pg_transaction'].commit.assert_called_once()
    mocks['pg_transaction'].rollback.assert_not_called()
    
    # Verify Neo4j transaction started and committed
    assert mocks['neo4j_session'].begin_transaction.called
    mocks['neo4j_transaction'].commit.assert_called_once()
    mocks['neo4j_transaction'].rollback.assert_not_called()
    
    # Verify connection cleanup
    mocks['pool'].release.assert_called_once_with(mocks['pg_conn'])
    mocks['neo4j_session'].close.assert_called_once()
    
    # Verify cache invalidation
    assert mocks['cache_coordinator'].invalidate_pattern.called
    pattern_calls = mocks['cache_coordinator'].invalidate_pattern.call_args_list
    assert any(call.args[0].startswith("repo:123:") for call in pattern_calls)

@pytest.mark.asyncio
async def test_transaction_scope_with_postgres_failure(mock_database_connections):
    """
    Test transaction rollback when PostgreSQL operations fail.
    
    This test verifies the error handling behavior when PostgreSQL commit fails:
    1. The failed PostgreSQL transaction should attempt to roll back
    2. The Neo4j transaction should also roll back (to maintain consistency)
    3. Resources should be properly cleaned up
    4. No cache invalidation should occur
    5. A TransactionError should be raised
    
    This ensures data consistency across databases even during failures.
    """
    # Arrange
    mocks = mock_database_connections
    mocks['pg_transaction'].commit.side_effect = PostgresError("Commit failed")
    
    # Act & Assert
    with pytest.raises(TransactionError):
        async with transaction_scope() as coordinator:
            await coordinator.track_repo_change(456)
    
    # Verify both transactions were rolled back
    mocks['pg_transaction'].rollback.assert_called_once()
    mocks['neo4j_transaction'].rollback.assert_called_once()
    
    # Verify connections were cleaned up
    mocks['pool'].release.assert_called_once_with(mocks['pg_conn'])
    mocks['neo4j_session'].close.assert_called_once()
    
    # Verify cache was not invalidated (since transaction failed)
    mocks['cache_coordinator'].invalidate_pattern.assert_not_called()

@pytest.mark.asyncio
async def test_transaction_scope_with_neo4j_failure(mock_database_connections):
    """
    Test transaction rollback when Neo4j operations fail.
    
    This test verifies the error handling behavior when Neo4j commit fails:
    1. The failed Neo4j transaction should attempt to roll back
    2. The PostgreSQL transaction should also roll back (to maintain consistency)
    3. Resources should be properly cleaned up
    4. A TransactionError should be raised
    
    This ensures data consistency when the graph database operations fail.
    """
    # Arrange
    mocks = mock_database_connections
    mocks['neo4j_transaction'].commit.side_effect = Neo4jError("Neo4j commit failed")
    
    # Act & Assert
    with pytest.raises(TransactionError):
        async with transaction_scope() as coordinator:
            await coordinator.track_repo_change(789)
    
    # Verify both transactions were rolled back
    mocks['pg_transaction'].rollback.assert_called_once()
    mocks['neo4j_transaction'].rollback.assert_called_once()
    
    # Verify connections were cleaned up
    mocks['pool'].release.assert_called_once_with(mocks['pg_conn'])
    mocks['neo4j_session'].close.assert_called_once()

@pytest.mark.asyncio
async def test_transaction_scope_with_exception_in_body(mock_database_connections):
    """
    Test transaction rollback when an exception occurs in the transaction body.
    
    This test verifies the transaction scope's error handling when an exception
    occurs within the transaction body (user code):
    1. Both transactions should be rolled back
    2. Resources should be properly cleaned up
    3. The original exception should be wrapped in a TransactionError
    
    This is critical for protecting database consistency when application code fails.
    """
    # Arrange
    mocks = mock_database_connections
    
    # Act & Assert
    with pytest.raises(TransactionError):
        async with transaction_scope() as coordinator:
            await coordinator.track_repo_change(101)
            raise ValueError("Simulated error in transaction body")
    
    # Verify transactions were rolled back
    mocks['pg_transaction'].rollback.assert_called_once()
    mocks['neo4j_transaction'].rollback.assert_called_once()
    
    # Verify connections were cleaned up
    mocks['pool'].release.assert_called_once_with(mocks['pg_conn'])
    mocks['neo4j_session'].close.assert_called_once()

@pytest.mark.asyncio
async def test_transaction_scope_without_cache_invalidation(mock_database_connections):
    """
    Test transaction_scope with cache invalidation disabled.
    
    This test verifies that when cache invalidation is explicitly disabled:
    1. Transactions still commit correctly
    2. Resources are properly cleaned up
    3. No cache invalidation calls are made
    
    This is important for transactions that don't need cache invalidation
    or when invalidation should be handled separately.
    """
    # Arrange
    mocks = mock_database_connections
    
    # Act
    async with transaction_scope(invalidate_cache=False) as coordinator:
        await coordinator.track_repo_change(202)
    
    # Assert
    # Verify transactions were committed
    mocks['pg_transaction'].commit.assert_called_once()
    mocks['neo4j_transaction'].commit.assert_called_once()
    
    # Verify cache invalidation was NOT called
    mocks['cache_coordinator'].invalidate_pattern.assert_not_called()

@pytest.mark.asyncio
async def test_transaction_coordinator_lock_behavior():
    """
    Test that the TransactionCoordinator properly uses locks.
    
    This test verifies the locking mechanism of the TransactionCoordinator:
    1. Operations within a lock are executed sequentially, not concurrently
    2. The lock properly prevents race conditions between concurrent tasks
    
    This is important for thread safety in asynchronous applications,
    especially when multiple operations might be modifying the same data.
    """
    # Create a real coordinator to test the lock behavior
    coordinator = TransactionCoordinator()
    
    # Create a flag to track execution order
    order = []
    
    async def task1():
        async with coordinator._lock:
            order.append(1)
            # Simulate some work
            await asyncio.sleep(0.1)
            order.append(3)
    
    async def task2():
        # This should run after task1 releases the lock
        async with coordinator._lock:
            order.append(2)
    
    # Define a delayed task launcher
    async def delayed_launcher():
        # Start task2 after a short delay
        await asyncio.sleep(0.05)
        return await task2()
    
    # Run the tasks concurrently
    await asyncio.gather(
        task1(),
        delayed_launcher()
    )
    
    # Verify execution order due to lock
    # If the lock works correctly, the order should be [1, 3, 2]
    # If not, it might be [1, 2, 3] due to the delay in task1
    assert order == [1, 3, 2]

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 