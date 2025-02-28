"""
Mock Database Layer for Tests.

This module provides a comprehensive mocking system for database operations
to enable consistent and reliable test execution. It includes mocks for:

1. PostgreSQL connections and queries
2. Neo4j driver and sessions
3. Common mock data fixtures
4. Support for transaction simulation

Features:
- Record/replay capabilities to verify query patterns
- Simulated errors for testing error handling
- Configurable latency to test timeout scenarios
- Transaction simulation across mocked databases
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable, Union, Set, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
import copy
import json
import re
from contextlib import asynccontextmanager

from utils.error_handling import (
    DatabaseError,
    PostgresError,
    Neo4jError,
    TransactionError,
    RetryableNeo4jError,
    NonRetryableNeo4jError
)

class MockTransaction:
    """Mock transaction context manager for both PostgreSQL and Neo4j."""
    
    def __init__(self, parent_mock, transaction_id=None, should_fail=False,
                 failure_type=None, failure_message=None):
        """Initialize the mock transaction.
        
        Args:
            parent_mock: The parent mock connection or session
            transaction_id: Optional ID to track this transaction
            should_fail: Whether the transaction should fail
            failure_type: Type of exception to raise if failing
            failure_message: Message for the exception
        """
        self.parent_mock = parent_mock
        self.transaction_id = transaction_id or id(self)
        self.should_fail = should_fail
        self.failure_type = failure_type or DatabaseError
        self.failure_message = failure_message or "Mock transaction failed"
        self.is_active = False
        self.operations = []
        
    async def __aenter__(self):
        """Enter the transaction context."""
        self.is_active = True
        self.parent_mock.current_transaction = self
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the transaction context."""
        self.is_active = False
        self.parent_mock.current_transaction = None
        
        if self.should_fail and not exc_type:
            raise self.failure_type(self.failure_message)
        
        # If an exception was raised, don't suppress it
        return False
    
    def record_operation(self, operation_type, *args, **kwargs):
        """Record an operation in this transaction."""
        self.operations.append({
            "type": operation_type,
            "args": args,
            "kwargs": kwargs,
            "timestamp": asyncio.get_event_loop().time()
        })

class MockPostgresConnection:
    """Mock PostgreSQL connection with transaction support."""
    
    def __init__(self, pool, conn_id=None):
        """Initialize the connection."""
        self.pool = pool
        self.conn_id = conn_id or id(self)
        self.is_closed = False
        self.current_transaction = None
        self.transaction_factory = MockTransaction
    
    def transaction(self):
        """Create a new transaction."""
        return self.transaction_factory(self)
    
    async def fetch(self, query, *args):
        """Mock fetch operation."""
        if self.is_closed:
            raise PostgresError("Connection is closed")
        
        if self.current_transaction:
            self.current_transaction.record_operation("fetch", query, *args)
        
        return self.pool.handle_query(query, args)
    
    async def execute(self, query, *args):
        """Mock execute operation."""
        if self.is_closed:
            raise PostgresError("Connection is closed")
        
        if self.current_transaction:
            self.current_transaction.record_operation("execute", query, *args)
        
        return self.pool.handle_execute(query, args)
    
    async def executemany(self, query, args_list):
        """Mock executemany operation."""
        if self.is_closed:
            raise PostgresError("Connection is closed")
        
        if self.current_transaction:
            self.current_transaction.record_operation("executemany", query, args_list)
        
        results = []
        for args in args_list:
            result = await self.execute(query, *args)
            results.append(result)
        
        return results
    
    async def close(self):
        """Close the connection."""
        self.is_closed = True

class MockPostgresPool:
    """Mock PostgreSQL connection pool."""
    
    def __init__(self, database_name="mock_db"):
        """Initialize the pool with empty mock data."""
        self.database_name = database_name
        self.is_closed = False
        self.connections = {}
        self.active_connections = set()
        self.query_handlers = {}
        self.execute_handlers = {}
        
        # Default data structures
        self.tables = {
            "repositories": [],
            "code_snippets": [],
            "documents": [],
            "features": [],
            "patterns": []
        }
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default query handlers."""
        # SELECT handlers
        self.register_query_handler(
            r"SELECT.*FROM\s+repositories",
            lambda query, args: [dict(row) for row in self.tables["repositories"]]
        )
        self.register_query_handler(
            r"SELECT.*FROM\s+code_snippets",
            lambda query, args: [dict(row) for row in self.tables["code_snippets"]]
        )
        
        # INSERT handlers
        self.register_execute_handler(
            r"INSERT\s+INTO\s+repositories",
            self._handle_repository_insert
        )
        self.register_execute_handler(
            r"INSERT\s+INTO\s+code_snippets",
            self._handle_code_snippet_insert
        )
    
    def _handle_repository_insert(self, query, args):
        """Handle repository insert operation."""
        repo_id = len(self.tables["repositories"]) + 1
        repo = {"id": repo_id}
        
        # Try to extract column names and values
        columns_match = re.search(r"INSERT\s+INTO\s+repositories\s*\(([^)]+)\)", query)
        if columns_match:
            columns = [col.strip() for col in columns_match.group(1).split(",")]
            
            for i, col in enumerate(columns):
                if i < len(args[0]):
                    repo[col] = args[0][i]
        
        self.tables["repositories"].append(repo)
        return [repo]
    
    def _handle_code_snippet_insert(self, query, args):
        """Handle code snippet insert operation."""
        snippet_id = len(self.tables["code_snippets"]) + 1
        snippet = {"id": snippet_id}
        
        # Try to extract column names and values
        columns_match = re.search(r"INSERT\s+INTO\s+code_snippets\s*\(([^)]+)\)", query)
        if columns_match:
            columns = [col.strip() for col in columns_match.group(1).split(",")]
            
            for i, col in enumerate(columns):
                if i < len(args[0]):
                    snippet[col] = args[0][i]
        
        self.tables["code_snippets"].append(snippet)
        return [snippet]
    
    def register_query_handler(self, query_pattern, handler):
        """Register a custom query handler function.
        
        Args:
            query_pattern: Regex pattern to match the query
            handler: Function that takes (query, args) and returns results
        """
        self.query_handlers[query_pattern] = handler
    
    def register_execute_handler(self, query_pattern, handler):
        """Register a custom execute handler function.
        
        Args:
            query_pattern: Regex pattern to match the execute statement
            handler: Function that takes (query, args) and returns results
        """
        self.execute_handlers[query_pattern] = handler
    
    def get_size(self):
        """Get the mock pool size."""
        return len(self.connections)
    
    def handle_query(self, query, args):
        """Handle a query based on registered handlers."""
        # Check for matching handler
        for pattern, handler in self.query_handlers.items():
            if re.search(pattern, query, re.IGNORECASE):
                return handler(query, args)
        
        # Default empty response
        return []
    
    def handle_execute(self, query, args):
        """Handle an execute based on registered handlers."""
        # Check for matching handler
        for pattern, handler in self.execute_handlers.items():
            if re.search(pattern, query, re.IGNORECASE):
                return handler(query, args)
        
        # Default response
        return None
    
    async def create_pool(self, **kwargs):
        """Mock pool creation."""
        return self
    
    async def close(self):
        """Close the pool."""
        self.is_closed = True
        for conn_id in list(self.connections.keys()):
            await self.connections[conn_id].close()
        self.connections.clear()
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        if self.is_closed:
            raise PostgresError("Pool is closed")
        
        conn_id = id(object())
        connection = MockPostgresConnection(self, conn_id)
        self.connections[conn_id] = connection
        self.active_connections.add(conn_id)
        
        try:
            yield connection
        finally:
            self.active_connections.remove(conn_id)
    
    async def release(self, connection):
        """Release a connection back to the pool."""
        if connection.conn_id in self.connections:
            await connection.close()
            del self.connections[connection.conn_id]

class MockNeo4jTransaction:
    """Mock Neo4j transaction with operation recording."""
    
    def __init__(self, session, transaction_id=None, should_fail=False,
                failure_type=None, failure_message=None):
        """Initialize the mock transaction."""
        self.session = session
        self.transaction_id = transaction_id or id(self)
        self.should_fail = should_fail
        self.failure_type = failure_type or Neo4jError
        self.failure_message = failure_message or "Mock Neo4j transaction failed"
        self.is_active = False
        self.operations = []
    
    async def __aenter__(self):
        """Enter the transaction context."""
        self.is_active = True
        self.session.current_transaction = self
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the transaction context."""
        self.is_active = False
        self.session.current_transaction = None
        
        if self.should_fail and not exc_type:
            raise self.failure_type(self.failure_message)
        
        # If an exception was raised, don't suppress it
        return False
    
    def record_operation(self, operation_type, *args, **kwargs):
        """Record an operation in this transaction."""
        self.operations.append({
            "type": operation_type,
            "args": args,
            "kwargs": kwargs,
            "timestamp": asyncio.get_event_loop().time()
        })
    
    async def run(self, query, parameters=None, **kwargs):
        """Run a query within the transaction."""
        self.record_operation("run", query, parameters, **kwargs)
        return await self.session.run(query, parameters, **kwargs)

class MockNeo4jSession:
    """Mock Neo4j session."""
    
    def __init__(self, driver, database=None):
        """Initialize the session."""
        self.driver = driver
        self.database = database
        self.is_closed = False
        self.current_transaction = None
        self.transaction_factory = MockNeo4jTransaction
        self.has_active_result = False
    
    def transaction(self):
        """Create a new transaction."""
        return self.transaction_factory(self)
    
    async def __aenter__(self):
        """Enter the session context."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the session context."""
        await self.close()
        return False
    
    async def close(self):
        """Close the session."""
        self.is_closed = True
    
    async def run(self, query, parameters=None, **kwargs):
        """Run a Cypher query."""
        if self.is_closed:
            raise Neo4jError("Session is closed")
        
        if self.current_transaction:
            self.current_transaction.record_operation("run", query, parameters, **kwargs)
        
        self.has_active_result = True
        return await self.driver.handle_query(query, parameters)

class MockNeo4jResult:
    """Mock Neo4j query result."""
    
    def __init__(self, records, has_more=False):
        """Initialize with mock records."""
        self.records = records if records else []
        self._has_more = has_more
        self.current_index = 0
    
    async def __aenter__(self):
        """Enter the result context."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the result context."""
        await self.consume()
        return False
    
    def has_more(self):
        """Check if there are more records."""
        return self._has_more
    
    async def single(self):
        """Get a single record or None."""
        if not self.records:
            return None
        return self.records[0]
    
    async def peek(self):
        """Peek at the next record without consuming it."""
        if self.current_index >= len(self.records):
            return None
        return self.records[self.current_index]
    
    async def fetch(self, n=None):
        """Fetch n records, or all remaining if n is None."""
        if n is None:
            result = self.records[self.current_index:]
            self.current_index = len(self.records)
            return result
        
        result = self.records[self.current_index:self.current_index + n]
        self.current_index += min(n, len(self.records) - self.current_index)
        return result
    
    async def consume(self):
        """Consume all remaining records."""
        self.current_index = len(self.records)
        self._has_more = False
        
    async def __anext__(self):
        """Get the next record."""
        if self.current_index >= len(self.records):
            raise StopAsyncIteration
        
        record = self.records[self.current_index]
        self.current_index += 1
        return record
    
    def __aiter__(self):
        """Return the async iterator."""
        return self

class MockNeo4jDriver:
    """Mock Neo4j driver."""
    
    def __init__(self, uri="bolt://mock", auth=None):
        """Initialize the driver."""
        self.uri = uri
        self.auth = auth
        self.is_closed = False
        self.query_handlers = {}
        self.retryable_error_patterns = [
            "Connection refused",
            "Connection reset",
            "Connection timed out",
            "Server unavailable",
            "Deadlock detected",
            "Network unreachable"
        ]
        self.non_retryable_error_patterns = [
            "Syntax error",
            "Constraint violation",
            "Invalid argument",
            "Node not found"
        ]
        
        # Register default handlers
        self._register_default_handlers()
        
        # Mock data store
        self.nodes = {}
        self.relationships = {}
    
    def _register_default_handlers(self):
        """Register default query handlers."""
        # MATCH queries
        self.register_query_handler(
            r"MATCH\s+\(n\)",
            lambda query, params: self._handle_match_all_nodes(query, params)
        )
        
        # CREATE queries
        self.register_query_handler(
            r"CREATE\s+\(n:(\w+)",
            lambda query, params: self._handle_create_node(query, params)
        )
        
        # Graph projection queries
        self.register_query_handler(
            r"CALL\s+gds\.graph\.project",
            lambda query, params: [{"graphName": params.get("graphName", "mock-graph")}]
        )
    
    def _handle_match_all_nodes(self, query, params):
        """Handle a query that matches all nodes."""
        return [node for node in self.nodes.values()]
    
    def _handle_create_node(self, query, params):
        """Handle a query that creates a node."""
        label_match = re.search(r"CREATE\s+\(n:(\w+)", query)
        label = label_match.group(1) if label_match else "Node"
        
        node_id = len(self.nodes) + 1
        node = {
            "id": node_id,
            "labels": [label],
            "properties": params if params else {}
        }
        
        self.nodes[node_id] = node
        return [node]
    
    def register_query_handler(self, query_pattern, handler):
        """Register a custom query handler function.
        
        Args:
            query_pattern: Regex pattern to match the query
            handler: Function that takes (query, params) and returns results
        """
        self.query_handlers[query_pattern] = handler
    
    async def handle_query(self, query, parameters):
        """Handle a query based on registered handlers."""
        # Check for matching handler
        for pattern, handler in self.query_handlers.items():
            if re.search(pattern, query, re.IGNORECASE):
                records = handler(query, parameters)
                return MockNeo4jResult(records)
        
        # Default empty result
        return MockNeo4jResult([])
    
    async def verify_connectivity(self):
        """Verify driver connectivity."""
        if self.is_closed:
            raise Neo4jError("Driver is closed")
        return True
    
    async def close(self):
        """Close the driver."""
        self.is_closed = True
    
    def session(self, database=None, **kwargs):
        """Create a new session."""
        if self.is_closed:
            raise Neo4jError("Driver is closed")
        return MockNeo4jSession(self, database)
    
    def classify_error(self, error):
        """Classify an error as retryable or non-retryable."""
        error_message = str(error)
        
        # Check retryable patterns
        for pattern in self.retryable_error_patterns:
            if pattern.lower() in error_message.lower():
                return RetryableNeo4jError(error_message)
        
        # Check non-retryable patterns
        for pattern in self.non_retryable_error_patterns:
            if pattern.lower() in error_message.lower():
                return NonRetryableNeo4jError(error_message)
        
        # Default to retryable
        return RetryableNeo4jError(error_message)

class MockDatabaseFactory:
    """Factory for creating consistent mock database instances."""
    
    def __init__(self):
        """Initialize the factory."""
        self.pg_pool = None
        self.neo4j_driver = None
        self.data_fixtures = {}
    
    def create_postgres_pool(self):
        """Create a new PostgreSQL pool."""
        if not self.pg_pool:
            self.pg_pool = MockPostgresPool()
        return self.pg_pool
    
    def create_neo4j_driver(self, uri="bolt://mock", auth=None):
        """Create a new Neo4j driver."""
        if not self.neo4j_driver:
            self.neo4j_driver = MockNeo4jDriver(uri, auth)
        return self.neo4j_driver
    
    def register_data_fixture(self, name, data):
        """Register a data fixture for tests."""
        self.data_fixtures[name] = copy.deepcopy(data)
    
    def get_data_fixture(self, name):
        """Get a copy of a registered data fixture."""
        if name not in self.data_fixtures:
            raise ValueError(f"Data fixture '{name}' not found")
        return copy.deepcopy(self.data_fixtures[name])
    
    def load_fixture_to_postgres(self, fixture_name, table_name):
        """Load a fixture into a PostgreSQL table."""
        if not self.pg_pool:
            raise ValueError("PostgreSQL pool not initialized")
            
        fixture = self.get_data_fixture(fixture_name)
        self.pg_pool.tables[table_name] = fixture
    
    def reset_all(self):
        """Reset all mock databases to clean state."""
        if self.pg_pool:
            asyncio.run(self.pg_pool.close())
            self.pg_pool = MockPostgresPool()
        
        if self.neo4j_driver:
            asyncio.run(self.neo4j_driver.close())
            self.neo4j_driver = MockNeo4jDriver()

# Create singleton factory instance
mock_db_factory = MockDatabaseFactory()

# Common test fixtures
def register_common_fixtures():
    """Register common test fixtures."""
    # Repository fixture
    repositories = [
        {"id": 1, "repo_name": "test-repo-1", "repo_type": "active", "repo_url": "https://github.com/test/repo1"},
        {"id": 2, "repo_name": "test-repo-2", "repo_type": "active", "repo_url": "https://github.com/test/repo2"},
        {"id": 3, "repo_name": "test-repo-3", "repo_type": "archived", "repo_url": "https://github.com/test/repo3"},
    ]
    mock_db_factory.register_data_fixture("repositories", repositories)
    
    # Code snippets fixture
    code_snippets = [
        {"id": 1, "repo_id": 1, "file_path": "file1.py", "content": "def test(): pass", "language": "python"},
        {"id": 2, "repo_id": 1, "file_path": "file2.js", "content": "function test() {}", "language": "javascript"},
        {"id": 3, "repo_id": 2, "file_path": "file3.py", "content": "class Test:\n  pass", "language": "python"},
    ]
    mock_db_factory.register_data_fixture("code_snippets", code_snippets)
    
    # Neo4j nodes fixture
    nodes = [
        {"id": 1, "labels": ["Repository"], "properties": {"name": "test-repo-1", "id": 1}},
        {"id": 2, "labels": ["File"], "properties": {"path": "file1.py", "repo_id": 1}},
        {"id": 3, "labels": ["File"], "properties": {"path": "file2.js", "repo_id": 1}},
    ]
    mock_db_factory.register_data_fixture("nodes", nodes)
    
    # Relationships fixture
    relationships = [
        {"id": 1, "start_node": 1, "end_node": 2, "type": "CONTAINS"},
        {"id": 2, "start_node": 1, "end_node": 3, "type": "CONTAINS"},
    ]
    mock_db_factory.register_data_fixture("relationships", relationships)

# Register common fixtures
register_common_fixtures()

# Patch functions for use in tests
def patch_postgres():
    """Patch PostgreSQL functions with mocks."""
    pg_pool = mock_db_factory.create_postgres_pool()
    
    patches = [
        patch('db.psql._pool', pg_pool),
        patch('db.psql.init_db_pool', AsyncMock(return_value=None)),
        patch('db.psql.close_db_pool', AsyncMock(return_value=None)),
        patch('db.psql.query', side_effect=lambda sql, params=None: pg_pool.handle_query(sql, params)),
        patch('db.psql.execute', side_effect=lambda sql, params=None: pg_pool.handle_execute(sql, params)),
        patch('db.transaction.get_connection', side_effect=lambda: pg_pool.acquire()),
    ]
    
    return patches

def patch_neo4j():
    """Patch Neo4j functions with mocks."""
    neo4j_driver = mock_db_factory.create_neo4j_driver()
    
    patches = [
        patch('db.neo4j_ops.driver', neo4j_driver),
        patch('db.neo4j_ops.run_query', side_effect=lambda query, params=None, **kwargs: 
              neo4j_driver.handle_query(query, params)),
        patch('db.neo4j_ops.classify_error', side_effect=neo4j_driver.classify_error),
    ]
    
    return patches

# Example usage in tests:
# 
# @pytest.fixture
# def mock_databases():
#     # Get mock databases
#     pg_patches = patch_postgres()
#     neo4j_patches = patch_neo4j()
#     
#     # Start all patches
#     for p in pg_patches + neo4j_patches:
#         p.start()
#     
#     # Setup test data
#     pg_pool = mock_db_factory.pg_pool
#     pg_pool.tables["repositories"] = mock_db_factory.get_data_fixture("repositories")
#     
#     yield mock_db_factory
#     
#     # Stop all patches
#     for p in pg_patches + neo4j_patches:
#         p.stop()
#     
#     # Reset for next test
#     mock_db_factory.reset_all() 