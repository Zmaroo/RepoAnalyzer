"""Test to verify database mocks are working correctly."""

import pytest
import pytest_asyncio
import inspect
from unittest.mock import patch, MagicMock, AsyncMock
import logging
import db.psql
import db.transaction
import db.schema
from utils.error_handling import AsyncErrorBoundary, DatabaseError
from utils.logger import log

@pytest.mark.asyncio
async def test_verify_mocks(mock_databases):
    """Verify that database mocks are working correctly."""
    
    # Test 1: Verify query function is properly mocked
    log("Testing query function")
    result = await db.psql.query("SELECT * FROM test_table")
    # The result should be a list after awaiting
    assert result is not None, "Query result should not be None"
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    
    # Test 2: Verify transaction_scope is properly mocked
    log("Testing transaction_scope")
    async with db.transaction.transaction_scope() as txn:
        assert txn is not None, "Transaction coordinator should not be None"
        
    # Test 3: Verify drop_all_tables is working
    log("Testing drop_all_tables")
    await db.schema.drop_all_tables()
    
    # Test 4: Verify individual table creation functions instead of create_all_tables
    log("Testing individual table creation functions")
    await db.schema.create_repositories_table()
    await db.schema.create_code_snippets_table()
    log("✅ Individual table creation functions work correctly")
    
    # Test 5: Verify AsyncErrorBoundary with transaction_scope
    log("Testing AsyncErrorBoundary with transaction_scope")
    async with AsyncErrorBoundary("test boundary"):
        async with db.transaction.transaction_scope() as txn:
            assert txn is not None, "Transaction coordinator should not be None"
    log("✅ All tests passed!") 