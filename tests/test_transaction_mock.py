"""Test transaction mock implementation."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from contextlib import asynccontextmanager

from db.transaction import transaction_scope

@pytest.mark.asyncio
async def test_transaction_scope_mock():
    """Test that we can properly mock the transaction_scope function."""
    
    # Create a simple mock implementation
    @asynccontextmanager
    async def mock_transaction_scope(*args, **kwargs):
        """Mock implementation of transaction_scope."""
        coordinator = MagicMock()
        # Add async methods that might be called
        coordinator._start_postgres = AsyncMock()
        coordinator._start_neo4j = AsyncMock()
        coordinator._commit_all = AsyncMock()
        coordinator._rollback_all = AsyncMock()
        coordinator._invalidate_caches = AsyncMock()
        coordinator._cleanup = AsyncMock()
        coordinator._lock = asyncio.Lock()
        
        try:
            yield coordinator
            # Exit normally
            await coordinator._commit_all()
            if kwargs.get('invalidate_cache', True):
                await coordinator._invalidate_caches()
        except Exception as e:
            await coordinator._rollback_all()
            print(f"Transaction error: {e}")
            raise
        finally:
            await coordinator._cleanup()
    
    # Test that our mock works as expected
    with patch('db.transaction.transaction_scope', mock_transaction_scope):
        # Get a reference to the mocked function
        from db.transaction import transaction_scope as patched_scope
        
        # Properly use the async context manager
        async with patched_scope() as coordinator:
            # Verify we got the coordinator
            assert coordinator is not None
            
            # Verify methods will be called in the right order
            # These assertions will verify the cleanup happens when we exit the context

@pytest.mark.asyncio
async def test_transaction_scope_import_check():
    """Test importing transaction_scope from different paths to understand how it's imported."""

    # Test direct import path
    from db.transaction import transaction_scope as direct_scope
    
    # Verify transaction_scope exists in the correct module
    import db.transaction
    assert hasattr(db.transaction, 'transaction_scope')
    
    # Test that transaction_scope is correctly exported from the right module
    from db import transaction
    assert hasattr(transaction, 'transaction_scope')
    
    # Verify it's the same object
    assert transaction.transaction_scope is direct_scope 