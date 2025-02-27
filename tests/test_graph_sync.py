"""Tests for graph synchronization functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from db.graph_sync import (
    GraphSyncCoordinator,
    ProjectionError,
    create_repository_projection,
    ensure_projection,
    invalidate_projection
)
from db.neo4j_ops import (
    auto_reinvoke_projection_once
)
from utils.error_handling import Neo4jError, DatabaseError

@pytest.fixture
def mock_driver():
    """Mock Neo4j driver."""
    with patch('db.graph_sync.driver') as mock:
        mock.session = AsyncMock()
        mock.run = AsyncMock()
        yield mock

@pytest.fixture
def mock_graph_cache():
    """Mock graph cache."""
    with patch('db.graph_sync.graph_cache') as mock:
        mock.get_async.return_value = None
        mock.set_async = AsyncMock()
        mock.clear_pattern_async = AsyncMock()
        yield mock

@pytest.fixture
def mock_run_query():
    """Mock run_query function."""
    with patch('db.graph_sync.run_query') as mock:
        # Use AsyncMock to ensure the mock returns an awaitable
        async_mock = AsyncMock()
        async_mock.return_value = [{"count": 10}]
        mock.side_effect = async_mock
        yield mock

@pytest.fixture
def graph_sync_coordinator(mock_driver, mock_graph_cache, mock_run_query):
    """Create GraphSyncCoordinator with mocked dependencies."""
    coordinator = GraphSyncCoordinator()
    return coordinator

@pytest.mark.asyncio
async def test_ensure_projection(graph_sync_coordinator, mock_run_query, mock_graph_cache):
    """Test ensure_projection method."""
    repo_id = 1
    
    # Test successful projection creation
    result = await graph_sync_coordinator.ensure_projection(repo_id)
    assert result is True
    
    # Verify the query was executed
    mock_run_query.assert_called()
    
    # Check that cache was updated
    mock_graph_cache.set_async.assert_called()

@pytest.mark.asyncio
async def test_invalidate_projection(graph_sync_coordinator, mock_graph_cache):
    """Test invalidate_projection method."""
    repo_id = 1
    projection_name = f"code-repo-{repo_id}"
    
    # Add projection to active set
    graph_sync_coordinator._active_projections.add(projection_name)
    
    # Test invalidation
    await graph_sync_coordinator.invalidate_projection(repo_id)
    
    # Verify projection was removed
    assert projection_name not in graph_sync_coordinator._active_projections
    
    # Check that cache was cleared
    mock_graph_cache.clear_pattern_async.assert_called_with(f"graph:{repo_id}:*")

@pytest.mark.asyncio
async def test_auto_reinvoke_projection_once(mock_run_query):
    """Test auto_reinvoke_projection_once function."""
    with patch('db.neo4j_ops.graph_sync') as mock_graph_sync:
        mock_graph_sync.ensure_projection = AsyncMock(return_value=True)
        
        # Test with repo_id
        repo_id = 1
        mock_run_query.return_value = [{"count": 10}]
        result = await auto_reinvoke_projection_once(repo_id)
        assert result is True
        mock_graph_sync.ensure_projection.assert_called_with(repo_id)
        
        # Test without repo_id
        mock_run_query.side_effect = [
            [{"count": 5}],  # First call for count query
            [{"repo_id": 1}, {"repo_id": 2}]  # Second call for distinct repo_ids
        ]
        mock_graph_sync.ensure_projection.reset_mock()  # Reset call history
        
        result = await auto_reinvoke_projection_once()
        assert result is True
        assert mock_graph_sync.ensure_projection.call_count == 2  # Called once for each repo
        
        # Test with no nodes
        mock_run_query.return_value = [{"count": 0}]
        mock_graph_sync.ensure_projection.reset_mock()
        
        result = await auto_reinvoke_projection_once()
        assert result is False
        mock_graph_sync.ensure_projection.assert_not_called()

@pytest.mark.asyncio
async def test_projection_error_handling(graph_sync_coordinator, mock_run_query):
    """Test error handling in projection methods."""
    repo_id = 1
    
    # Test with database error
    mock_run_query.side_effect = Neo4jError("Test database error")
    
    with pytest.raises(ProjectionError):
        await graph_sync_coordinator.ensure_projection(repo_id)
    
    # Test with transaction error during invalidation
    mock_run_query.side_effect = DatabaseError("Transaction error")
    
    # Should not raise since invalidation handles errors internally
    await graph_sync_coordinator.invalidate_projection(repo_id)
    
@pytest.mark.asyncio
async def test_projection_automatic_recreation(graph_sync_coordinator, mock_run_query, mock_graph_cache):
    """Test automatic recreation of projections."""
    repo_id = 1
    
    # First check if projection exists
    mock_graph_cache.get_async.return_value = None  # Not in cache
    mock_run_query.side_effect = [
        [],  # Empty result for exists query
        None  # Result for create query
    ]
    
    result = await graph_sync_coordinator.ensure_projection(repo_id)
    assert result is True
    
    # Verify projection was created
    mock_run_query.assert_called()
    mock_graph_cache.set_async.assert_called()

@pytest.mark.asyncio
async def test_multiple_projection_updates(graph_sync_coordinator):
    """Test handling multiple projection updates with queuing."""
    with patch.object(graph_sync_coordinator, 'ensure_projection', new_callable=AsyncMock) as mock_ensure:
        mock_ensure.return_value = True
        
        # Queue several updates
        repo_ids = [1, 2, 3]
        for repo_id in repo_ids:
            await graph_sync_coordinator.queue_projection_update(repo_id)
        
        # Wait for debouncing
        await asyncio.sleep(1.5)
        
        # Check all repos were processed
        assert mock_ensure.call_count == len(repo_ids)
        for repo_id in repo_ids:
            assert repo_id not in graph_sync_coordinator._pending_updates 