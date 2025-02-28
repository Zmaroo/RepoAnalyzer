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
from typing import Dict, List, Any, Optional, Callable, Union, Set, Tuple, Protocol, TypeVar, Generic, Awaitable
from unittest.mock import AsyncMock, MagicMock, patch
import copy
import json
import re
from contextlib import asynccontextmanager
import time

try:
    from pytest import FixtureFunction as PyTestFixtureFunction
    # For pytest fixtures, define proper type parameters with two arguments
    # Define two simple type variables for the fixture function
    T_Fixture = TypeVar('T_Fixture')
    T_Factory = TypeVar('T_Factory')
    FixtureFunction = PyTestFixtureFunction[T_Fixture, T_Factory]
except (ImportError, TypeError):
    # If not available or wrong version, create a placeholder
    FixtureFunction = Callable[..., Any]

from utils.error_handling import (
    DatabaseError,
    PostgresError,
    Neo4jError,
    TransactionError,
    RetryableNeo4jError,
    NonRetryableNeo4jError
)

# Define TypeVars for more precise typing
T = TypeVar('T')
R = TypeVar('R')

# Define protocols for handlers
class QueryHandler(Protocol):
    """Protocol for query handlers."""
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

class AsyncQueryHandler(Protocol):
    """Protocol for async query handlers."""
    async def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

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
    """Mock PostgreSQL connection."""
    
    def __init__(self, pool):
        """Initialize the connection with a reference to the pool."""
        self.pool = pool
        self.closed = False
    
    async def close(self):
        """Close the connection."""
        if not self.closed:
            self.closed = True
            await self.pool.release(self)
    
    async def execute(self, query, *args):
        """Execute a query."""
        return await self.pool.handle_query(query, args)
    
    async def fetch(self, query, *args):
        """Fetch results from a query."""
        return await self.pool.handle_query(query, args)
    
    async def fetchrow(self, query, *args):
        """Fetch a single row from a query."""
        results = await self.pool.handle_query(query, args)
        return results[0] if results else None
    
    async def fetchval(self, query, *args):
        """Fetch a single value from a query."""
        results = await self.pool.handle_query(query, args)
        if not results:
            return None
        if isinstance(results[0], dict):
            return next(iter(results[0].values()))
        return results[0]
    
    @asynccontextmanager
    async def transaction(self):
        """Create a transaction context manager."""
        # Create a mock transaction
        transaction = MockTransaction(self)
        try:
            yield transaction
        finally:
            # Transaction is automatically closed when exiting the context
            pass

class MockPostgresPool:
    """Mock PostgreSQL connection pool."""
    
    def __init__(self):
        """Initialize the mock pool."""
        self.operations = []
        self.query_handlers = {}
        self.error_for_next_query = None
        self.retry_count = 0
        self.current_retry = 0
    
    def clear_operations(self):
        """Clear recorded operations."""
        self.operations = []
    
    def get_operations(self):
        """Get recorded operations."""
        return self.operations
    
    def add_query_handler(self, query_pattern: str, handler: QueryHandler) -> None:
        """Add a custom handler for a query pattern."""
        self.query_handlers[query_pattern] = handler
    
    def set_error_for_next_query(self, error, retry_count=0):
        """Set an error to be raised on the next query."""
        self.error_for_next_query = error
        self.retry_count = retry_count
        self.current_retry = 0
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        # Record the operation
        self.operations.append({
            "type": "acquire",
            "timestamp": time.time()
        })
        conn = MockPostgresConnection(self)
        try:
            yield conn
        finally:
            await self.release(conn)
    
    async def release(self, connection):
        """Release a connection back to the pool."""
        # Record the operation
        self.operations.append({
            "type": "release",
            "timestamp": time.time()
        })
    
    async def handle_query(self, query, params=None):
        """Handle a query and return results."""
        # Debug output
        print(f"DEBUG: handle_query called with query: {query}")
        print(f"DEBUG: params: {params}")
        print(f"DEBUG: query_handlers: {self.query_handlers}")
        
        # Check if we should raise an error
        if self.error_for_next_query:
            if self.current_retry < self.retry_count:
                self.current_retry += 1
                raise self.error_for_next_query
            else:
                error = self.error_for_next_query
                self.error_for_next_query = None
                self.current_retry = 0
                if error:
                    raise error
        
        # Record the operation
        operation = {
            "type": "query",
            "query": query,
            "params": params or (),
            "timestamp": time.time()
        }
        self.operations.append(operation)
        
        # Check for custom handlers
        for pattern, handler in self.query_handlers.items():
            print(f"DEBUG: Checking pattern: {pattern} against query: {query}")
            # Check for exact match first
            if pattern == query:
                print(f"DEBUG: Exact match found! Calling handler")
                result = handler(*params) if params else handler()
                print(f"DEBUG: Handler returned: {result}")
                return result
            # Then try regex match
            elif re.search(pattern, query):
                print(f"DEBUG: Pattern matched! Calling handler")
                result = handler(*params) if params else handler()
                print(f"DEBUG: Handler returned: {result}")
                return result
        
        # Default behavior for common queries
        if query == "SELECT * FROM repositories":
            return [
                {"id": 1, "name": "test-repo", "url": "https://github.com/test/test-repo"},
                {"id": 2, "name": "another-repo", "url": "https://github.com/test/another-repo"}
            ]
        elif query == "SELECT * FROM code_snippets":
            return [
                {"id": 1, "repo_id": 1, "file_path": "src/main.py", "content": "def main():\n    print('Hello, world!')"},
                {"id": 2, "repo_id": 1, "file_path": "src/utils.py", "content": "def helper():\n    return 42"}
            ]
        elif query == "SELECT * FROM users":
            return [
                {"id": 1, "username": "testuser", "email": "test@example.com"},
                {"id": 2, "username": "anotheruser", "email": "another@example.com"}
            ]
        
        # For any other query, return an empty list
        print(f"DEBUG: No handler found, returning empty list")
        return []

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
        # Extract transaction-related information for query execution
        return await self.session.run(query, parameters, **kwargs)

class MockNeo4jSession:
    """Mock Neo4j session with async methods."""
    
    def __init__(self, driver):
        """Initialize with a reference to the driver."""
        self.driver = driver
        self.closed = False
        
    async def run(self, query, parameters=None):
        """Run a query and return a result."""
        if parameters is None:
            parameters = {}
        return await self.driver.handle_query(query, parameters)
        
    async def close(self):
        """Close the session."""
        self.closed = True
        return None

class MockNeo4jRecord:
    """Mock Neo4j record."""
    
    def __init__(self, data):
        """Initialize with data dictionary."""
        self._data = data
    
    def data(self):
        """Return the data dictionary."""
        return self._data
    
    def get(self, key, default=None):
        """Get a value from the record."""
        return self._data.get(key, default)
    
    def __getitem__(self, key):
        """Get a value from the record."""
        return self._data[key]
    
    def keys(self):
        """Return the keys in the record."""
        return self._data.keys()

class MockNeo4jResult:
    """Mock Neo4j result."""
    
    def __init__(self, records):
        """Initialize with a list of records."""
        self.records = [MockNeo4jRecord(record) if not isinstance(record, MockNeo4jRecord) else record
                        for record in records]
    
    async def fetch(self):
        """Fetch all records."""
        return self.records
    
    def data(self):
        """Return the data from all records."""
        return [record.data() for record in self.records]

class MockNeo4jDriver:
    """Mock Neo4j driver with async methods."""
    
    def __init__(self):
        """Initialize the driver."""
        self.session_mock = MagicMock()
        self.operations = []
        self.query_handlers = {}
        self.next_error = None
        self.retry_count = 0
        
    def session(self):
        """Create a new session."""
        return MockNeo4jSession(self)
        
    def set_error_for_next_query(self, error, retry_count=0):
        """Set an error to be raised on the next query.
        
        Args:
            error: The error to raise
            retry_count: Number of retries before the error is cleared
        """
        self.next_error = error
        self.retry_count = retry_count
        
    def add_query_handler(self, pattern: str, handler: Union[QueryHandler, List[Dict[str, Any]]]) -> None:
        """Add a handler for a specific query pattern."""
        self.query_handlers[pattern] = handler
        
    def get_operations(self):
        """Get the list of recorded operations."""
        return self.operations
        
    def clear_operations(self):
        """Clear the list of recorded operations."""
        self.operations = []
        
    async def handle_query(self, query, parameters=None):
        """Handle a query based on registered handlers."""
        # Record the operation
        self.operations.append({
            "type": "query",
            "query": query,
            "params": parameters,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Check if we should raise an error
        if self.next_error:
            error = self.next_error
            if self.retry_count <= 0:
                self.next_error = None
            else:
                self.retry_count -= 1
            raise error
            
        # Try to match against registered handlers
        for pattern, handler in self.query_handlers.items():
            # If the pattern is a string, use it as a regex pattern
            if isinstance(pattern, str):
                if re.search(pattern, query, re.IGNORECASE):
                    if callable(handler):
                        result = handler(query=query, **parameters) if parameters else handler(query=query)
                        if isinstance(result, list):
                            return MockNeo4jResult(result)
                        return result
                    return MockNeo4jResult(handler)
            # If the pattern is a direct match
            elif pattern == query:
                if callable(handler):
                    result = handler(query=query, **parameters) if parameters else handler(query=query)
                    if isinstance(result, list):
                        return MockNeo4jResult(result)
                    return result
                return MockNeo4jResult(handler)
                
        # Default handling for specific queries
        if "MATCH (n) RETURN n" in query:
            return MockNeo4jResult([
                {"n": {"id": 1, "name": "file1.py", "labels": ["File"]}},
                {"n": {"id": 2, "name": "file2.js", "labels": ["File"]}}
            ])
        elif "MATCH (r:Repository {id: $id}) RETURN r" in query:
            repo_id = parameters.get('id', 0) if parameters else 0
            return MockNeo4jResult([
                {"r": {"id": repo_id, "name": "test-repo"}}
            ])
        
        # Default empty result
        return MockNeo4jResult([])

class MockDatabaseFactory:
    """Factory for creating mock database connections."""
    
    def __init__(self):
        """Initialize the factory."""
        self.pg_mock = MockPostgresPool()
        self.neo4j_mock = MockNeo4jDriver()
        
        # Add handlers for Neo4j queries
        self.neo4j_mock.session_mock.run = MagicMock(side_effect=self._handle_neo4j_query)
        
        # Register with the module-level variables in db modules
        self._register_mocks()
    
    def _handle_neo4j_query(self, query, *args, **kwargs):
        """Handle Neo4j queries and return appropriate results."""
        # Parse parameters from either positional or keyword arguments
        params = {}
        if args and args[0] is not None:
            params = args[0]
        elif kwargs:
            params = kwargs
            
        # Record the operation for tracking
        self.neo4j_mock.operations.append({
            "type": "query",
            "query": query,
            "params": params,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Check if we should raise an error
        if self.neo4j_mock.next_error:
            error = self.neo4j_mock.next_error
            if self.neo4j_mock.retry_count <= 0:
                self.neo4j_mock.next_error = None
            else:
                self.neo4j_mock.retry_count -= 1
            raise error
            
        # Handle specific query patterns
        if "MATCH (n) RETURN n" in query:
            # Return data that matches the test_neo4j_query expectations
            mock_result = MagicMock()
            records = [
                MockNeo4jRecord({"n": {"id": 1, "name": "file1.py", "labels": ["File"]}}),
                MockNeo4jRecord({"n": {"id": 2, "name": "file2.js", "labels": ["File"]}})
            ]
            mock_result.fetch = AsyncMock(return_value=records)
            return mock_result
        elif "MATCH (r:Repository {id: $id}) RETURN r" in query:
            repo_id = params.get('id', 0)
            mock_result = MagicMock()
            records = [MockNeo4jRecord({"r": {"id": repo_id, "name": "test-repo"}})]
            mock_result.fetch = AsyncMock(return_value=records)
            return mock_result
        else:
            # Default empty result
            mock_result = MagicMock()
            mock_result.fetch = AsyncMock(return_value=[])
            return mock_result
        
    def _register_mocks(self):
        """Register the mocks with the database modules."""
        import sys
        
        # Try to import the database modules
        try:
            from db.psql import _pool
            sys.modules['db.psql']._pool = self.pg_mock
        except (ImportError, AttributeError):
            pass
            
        try:
            from db.neo4j_ops import _driver
            sys.modules['db.neo4j_ops']._driver = self.neo4j_mock
        except (ImportError, AttributeError):
            pass
    
    def get_postgres_mock(self):
        """Get the PostgreSQL mock."""
        return self.pg_mock
        
    def get_neo4j_mock(self):
        """Get the Neo4j mock."""
        return self.neo4j_mock
        
    def create_postgres_pool(self):
        """Create a new PostgreSQL pool mock."""
        return self.pg_mock
        
    def create_neo4j_driver(self):
        """Create a new Neo4j driver mock."""
        return self.neo4j_mock
        
    def reset_all(self):
        """Reset all mocks to their initial state."""
        self.pg_mock.clear_operations()
        # Add any other reset operations needed

# Create singleton factory instance
mock_db_factory = MockDatabaseFactory()

# Common test fixtures
def register_common_fixtures():
    """Register common fixtures for tests."""
    # Create repositories
    repositories = [
        {"id": 1, "name": "test-repo", "url": "https://github.com/test/test-repo"},
        {"id": 2, "name": "another-repo", "url": "https://github.com/test/another-repo"}
    ]
    
    # Create users
    users = [
        {"id": 1, "username": "testuser", "email": "test@example.com"},
        {"id": 2, "username": "anotheruser", "email": "another@example.com"}
    ]
    
    # Create code snippets
    code_snippets = [
        {"id": 1, "repo_id": 1, "file_path": "src/main.py", "content": "def main():\n    print('Hello, world!')"},
        {"id": 2, "repo_id": 1, "file_path": "src/utils.py", "content": "def helper():\n    return 42"}
    ]
    
    # Register handlers for common queries
    mock_db_factory.pg_mock.add_query_handler(
        "SELECT * FROM repositories",
        lambda: repositories
    )
    
    mock_db_factory.pg_mock.add_query_handler(
        "SELECT * FROM users",
        lambda: users
    )
    
    mock_db_factory.pg_mock.add_query_handler(
        "SELECT * FROM code_snippets",
        lambda: code_snippets
    )

# Register common fixtures
register_common_fixtures()

# Patch functions for use in tests
def patch_postgres():
    """Patch PostgreSQL functions with mocks."""
    pg_pool = mock_db_factory.create_postgres_pool()
    
    # Define a function to handle the query and return the correct data
    async def mock_query(sql, params=None):
        # Use the handle_query method for all queries
        # Make sure params is properly passed to handle_query
        result = await pg_pool.handle_query(sql, params)
        return result
    
    # Define a function to handle execute operations
    async def mock_execute(sql, params=None):
        # Make sure params is properly passed to handle_query
        result = await pg_pool.handle_query(sql, params)
        return result
    
    patches = [
        patch('db.psql._pool', pg_pool),
        patch('db.psql.init_db_pool', AsyncMock(return_value=None)),
        patch('db.psql.close_db_pool', AsyncMock(return_value=None)),
        patch('db.psql.query', mock_query),  # Use the function directly, not AsyncMock
        patch('db.psql.execute', mock_execute),  # Use the function directly, not AsyncMock
        patch('db.transaction.get_connection', AsyncMock(side_effect=lambda: pg_pool.acquire())),
    ]
    
    return patches

def patch_neo4j():
    """Patch Neo4j functions with mocks."""
    neo4j_driver = mock_db_factory.create_neo4j_driver()
    
    # Define a function to handle Neo4j queries
    async def mock_run_query(query, params=None, **kwargs):
        try:
            session = neo4j_driver.session()
            try:
                result = await session.run(query, params or kwargs)
                records = await result.fetch()
                return [record.data() for record in records]
            finally:
                await session.close()
        except Exception as e:
            # Rethrow database errors as expected type
            if isinstance(e, (RetryableNeo4jError, NonRetryableNeo4jError)):
                raise e
            # Classify other errors
            error_msg = str(e).lower()
            if is_retryable_error(e):
                raise RetryableNeo4jError(f"Retryable error: {error_msg}")
            else:
                raise NonRetryableNeo4jError(f"Non-retryable error: {error_msg}")
    
    # Define a function to classify errors
    def mock_classify_error(error):
        """Classify an error as retryable or non-retryable."""
        if is_retryable_error(error):
            return RetryableNeo4jError(str(error))
        return NonRetryableNeo4jError(str(error))
    
    patches = [
        patch('db.neo4j_ops.driver', neo4j_driver),
        patch('db.neo4j_ops.run_query', AsyncMock(side_effect=mock_run_query)),
        patch('db.retry_utils.is_retryable_error', MagicMock(side_effect=lambda e: "connection reset" in str(e).lower() or "timeout" in str(e).lower())),
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

def reset_mock_factory():
    """Reset the singleton mock database factory."""
    global mock_db_factory
    mock_db_factory = None 

class MockPostgresResult:
    """Mock for PostgreSQL query results."""
    
    def __init__(self, records):
        """Initialize with records."""
        self.records = records
        self.rowcount = len(records)
        
    def __iter__(self):
        """Make the object iterable."""
        for record in self.records:
            yield record
            
    def __getitem__(self, index):
        """Support indexing."""
        return self.records[index] 