#!/usr/bin/env python3
"""
Unit tests for database layer components.

This module tests the database functionality in the RepoAnalyzer project:
1. Database connections
2. Query building and execution
3. Repository storage and retrieval
4. Graph relationships and navigation
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import uuid

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database modules
from db.neo4j_ops import Neo4jConnection
from db.psql import PostgresConnection
from db import __init__ as db_init
from db.retry_utils import RetryManager, RetryClassification
from db.graph_sync import GraphSyncManager
from db.transaction import Transaction

# Import fixtures
import conftest

class TestDatabaseConnections:
    """Test database connection functionality."""
    
    @pytest.mark.asyncio
    async def test_neo4j_connection(self, neo4j_mock):
        """Test connecting to Neo4j database."""
        # Create a database instance with the mock
        config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password",
            "database": "neo4j"
        }
        
        db = Neo4jConnection(config)
        
        # Set up mock response
        neo4j_mock.connect.return_value = True
        
        # Test connection
        is_connected = await db.connect()
        assert is_connected is True
        
        # Verify the mock was called
        neo4j_mock.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_postgres_connection(self, postgres_mock):
        """Test connecting to PostgreSQL database."""
        # Create a database instance with the mock
        config = {
            "host": "localhost",
            "user": "postgres",
            "password": "password",
            "database": "repo_analyzer",
            "port": 5432
        }
        
        db = PostgresConnection(config)
        
        # Set up mock response
        postgres_mock.connect.return_value = True
        
        # Test connection
        is_connected = await db.connect()
        assert is_connected is True
        
        # Verify the mock was called
        postgres_mock.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connection_failure_handling(self):
        """Test handling of connection failures."""
        # Create a mock that fails to connect
        mock_driver = AsyncMock()
        mock_driver.connect = AsyncMock(side_effect=Exception("Connection failed"))
        
        with patch('db.neo4j_ops.Neo4jConnection._create_driver', return_value=mock_driver):
            config = {
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "password",
                "database": "neo4j"
            }
            
            db = Neo4jConnection(config)
            
            # Test connection should fail but not raise an exception
            is_connected = await db.connect()
            assert is_connected is False

class TestRepositoryOperations:
    """Test repository database operations."""
    
    @pytest.fixture
    async def repo_db(self, mock_databases):
        """Create a repository database with mock connections."""
        repos = db_init.get_repository_manager()
        await repos.initialize()
        return repos
    
    @pytest.mark.asyncio
    async def test_store_repository(self, repo_db, mock_databases):
        """Test storing a repository."""
        # Setup
        repo_url = "https://github.com/test/repo"
        repo_name = "repo"
        
        # Setup postgres mock to return a repository ID
        postgres_mock, neo4j_mock = mock_databases
        repo_id = str(uuid.uuid4())
        postgres_mock.execute.return_value = {"id": repo_id}
        
        # Store a repository
        result = await repo_db.store_repository(repo_url, repo_name)
        
        # Verify result
        assert result["id"] == repo_id
        
        # Verify postgres was called
        postgres_mock.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_repository(self, repo_db, mock_databases):
        """Test retrieving a repository."""
        # Setup
        repo_url = "https://github.com/test/repo"
        postgres_mock, _ = mock_databases
        
        # Setup postgres mock to return a repository
        repo_data = {
            "id": str(uuid.uuid4()),
            "url": repo_url,
            "name": "repo"
        }
        postgres_mock.fetch_one.return_value = repo_data
        
        # Get a repository
        result = await repo_db.get_repository_by_url(repo_url)
        
        # Verify result
        assert result["id"] == repo_data["id"]
        assert result["url"] == repo_url
        
        # Verify postgres was called
        postgres_mock.fetch_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_repository(self, repo_db, mock_databases):
        """Test deleting a repository."""
        # Setup
        repo_id = str(uuid.uuid4())
        postgres_mock, neo4j_mock = mock_databases
        
        # Delete a repository
        await repo_db.delete_repository(repo_id)
        
        # Verify both databases were called
        postgres_mock.execute.assert_called_once()
        neo4j_mock.execute.assert_called_once()

class TestGraphOperations:
    """Test graph operations and queries."""
    
    @pytest.mark.asyncio
    async def test_execute_query(self, neo4j_mock):
        """Test executing a graph query."""
        # Create a Neo4j connection with the mock
        config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password",
            "database": "neo4j"
        }
        
        db = Neo4jConnection(config)
        
        # Setup mock to return results
        expected_results = [{"n": {"name": "test"}}]
        neo4j_mock.execute.return_value = expected_results
        
        # Execute a query
        query = "MATCH (n:Node) WHERE n.name = $name RETURN n"
        params = {"name": "test"}
        results = await db.execute(query, params)
        
        # Verify results
        assert results == expected_results
        
        # Verify mock was called
        neo4j_mock.execute.assert_called_once_with(query, params)
    
    @pytest.mark.asyncio
    async def test_graph_sync(self, neo4j_mock):
        """Test graph synchronization operations."""
        # Create a graph sync manager
        sync_manager = GraphSyncManager(neo4j_connection=neo4j_mock)
        
        # Mock the execution response
        neo4j_mock.execute.return_value = [{"node_id": "123"}]
        
        # Execute a sync operation
        result = await sync_manager.sync_node(
            label="File",
            properties={"path": "/test/file.py", "language": "python"},
            key_properties=["path"]
        )
        
        # Verify result
        assert result == [{"node_id": "123"}]
        
        # Verify neo4j was called
        neo4j_mock.execute.assert_called_once()
        
        # Verify the query contains MERGE
        query = neo4j_mock.execute.call_args[0][0]
        assert "MERGE" in query

class TestTransactions:
    """Test transaction management."""
    
    @pytest.mark.asyncio
    async def test_transaction_context(self, neo4j_mock):
        """Test using a transaction as a context manager."""
        # Create a transaction
        transaction = Transaction(connection=neo4j_mock)
        
        # Set up mock responses
        neo4j_mock.begin_transaction.return_value = "tx-id-123"
        neo4j_mock.execute_in_transaction.return_value = [{"result": "success"}]
        
        # Use transaction as context manager
        async with transaction as tx:
            result = await tx.execute("MATCH (n) RETURN n", {})
            assert result == [{"result": "success"}]
        
        # Verify transaction was begun and committed
        neo4j_mock.begin_transaction.assert_called_once()
        neo4j_mock.commit_transaction.assert_called_once_with("tx-id-123")
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, neo4j_mock):
        """Test transaction rollback on error."""
        # Create a transaction
        transaction = Transaction(connection=neo4j_mock)
        
        # Set up mock responses
        neo4j_mock.begin_transaction.return_value = "tx-id-123"
        neo4j_mock.execute_in_transaction.side_effect = Exception("Query failed")
        
        # Use transaction with an error
        try:
            async with transaction as tx:
                await tx.execute("MATCH (n) RETURN n", {})
                assert False, "Should have raised an exception"
        except Exception:
            pass  # Expected exception
        
        # Verify transaction was begun and rolled back
        neo4j_mock.begin_transaction.assert_called_once()
        neo4j_mock.rollback_transaction.assert_called_once_with("tx-id-123")

class TestRetryManager:
    """Test the retry mechanism for database operations."""
    
    def test_error_classification(self):
        """Test error classification for different exceptions."""
        # Create a retry manager
        manager = RetryManager(max_retries=3, base_delay=0.1)
        
        # Test retryable errors
        retryable_errors = [
            ConnectionError("Connection refused"),
            TimeoutError("Query timed out"),
            Exception("Too many connections")
        ]
        
        for error in retryable_errors:
            classification = manager.classify_error(error)
            assert classification == RetryClassification.RETRYABLE
        
        # Test non-retryable errors
        non_retryable_errors = [
            ValueError("Invalid parameter"),
            TypeError("Invalid type"),
            Exception("Syntax error in query")
        ]
        
        for error in non_retryable_errors:
            classification = manager.classify_error(error)
            assert classification == RetryClassification.NON_RETRYABLE
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        """Test the retry mechanism with a failing operation."""
        # Create a retry manager
        manager = RetryManager(max_retries=3, base_delay=0.01)  # Small delay for testing
        
        # Create a mock function that fails twice then succeeds
        mock_operation = AsyncMock(side_effect=[
            ConnectionError("First failure"),
            ConnectionError("Second failure"),
            "Success"
        ])
        
        # Execute with retry
        result = await manager.execute_with_retry(mock_operation)
        
        # Verify result
        assert result == "Success"
        
        # Verify the operation was called 3 times
        assert mock_operation.call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test that retries are exhausted after max_retries."""
        # Create a retry manager with few retries
        manager = RetryManager(max_retries=2, base_delay=0.01)
        
        # Create a mock function that always fails
        error = ConnectionError("Persistent failure")
        mock_operation = AsyncMock(side_effect=error)
        
        # Execute with retry should eventually fail
        with pytest.raises(ConnectionError):
            await manager.execute_with_retry(mock_operation)
        
        # Verify the operation was called the maximum number of times
        assert mock_operation.call_count == 3  # Initial try + 2 retries 