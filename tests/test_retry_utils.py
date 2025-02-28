"""
Unit tests for database retry utilities.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from db.retry_utils import (
    with_retry, 
    RetryableNeo4jError, 
    NonRetryableNeo4jError,
    is_retryable_error,
    classify_error,
    RetryConfig,
    DatabaseRetryManager
)
from utils.error_handling import DatabaseError, Neo4jError

@pytest.fixture
def retry_manager():
    """Create a retry manager with a small retry delay for testing."""
    return DatabaseRetryManager(
        RetryConfig(max_retries=3, base_delay=0.01, max_delay=0.1, jitter_factor=0.0)
    )

class TestRetryClassification:
    """Tests for error classification functionality."""
    
    def test_is_retryable_error_with_retryable_patterns(self):
        """Test that errors with retryable patterns are classified correctly."""
        retryable_errors = [
            Exception("Connection refused"),
            Exception("Operation timed out"),
            Exception("Database is temporarily unavailable"),
            Exception("Deadlock detected"),
            Exception("The connection was reset"),
            Exception("Broken pipe error occurred")
        ]
        
        for error in retryable_errors:
            assert is_retryable_error(error), f"Error '{error}' should be retryable"
    
    def test_is_retryable_error_with_non_retryable_patterns(self):
        """Test that errors with non-retryable patterns are classified correctly."""
        non_retryable_errors = [
            Exception("Syntax error in query"),
            Exception("Constraint violation"),
            Exception("Invalid argument"),
            Exception("Node not found"),
            Exception("Object already exists"),
            Exception("Permission denied")
        ]
        
        for error in non_retryable_errors:
            assert not is_retryable_error(error), f"Error '{error}' should not be retryable"
    
    def test_is_retryable_error_with_error_types(self):
        """Test that errors are classified correctly based on their type."""
        # RetryableError should always be retryable
        assert is_retryable_error(RetryableNeo4jError("Error"))
        
        # NonRetryableError should never be retryable
        assert not is_retryable_error(NonRetryableNeo4jError("Error"))
        
        # Neo4jError should be retryable by default
        assert is_retryable_error(Neo4jError("Generic Neo4j error"))
        
        # But Neo4jError with non-retryable pattern should not be retryable
        assert not is_retryable_error(Neo4jError("Syntax error"))
    
    def test_classify_error(self):
        """Test that errors are correctly classified as retryable or non-retryable."""
        # Retryable errors
        assert isinstance(classify_error(Exception("Connection refused")), RetryableNeo4jError)
        assert isinstance(classify_error(Neo4jError("Timeout error")), RetryableNeo4jError)
        
        # Non-retryable errors
        assert isinstance(classify_error(Exception("Syntax error")), NonRetryableNeo4jError)
        assert isinstance(classify_error(Neo4jError("Constraint violation")), NonRetryableNeo4jError)

class TestRetryConfig:
    """Tests for retry configuration."""
    
    def test_calculate_delay(self):
        """Test delay calculation with exponential backoff."""
        config = RetryConfig(base_delay=1.0, max_delay=10.0, jitter_factor=0.0)
        
        # With jitter_factor=0, we should get exact exponential backoff
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0
        
        # Test max delay cap
        config = RetryConfig(base_delay=1.0, max_delay=5.0, jitter_factor=0.0)
        assert config.calculate_delay(3) == 5.0  # Would be 8.0 but capped at 5.0
    
    def test_calculate_delay_with_jitter(self):
        """Test that jitter adds randomness to the delay."""
        config = RetryConfig(base_delay=1.0, jitter_factor=0.5)
        
        # With jitter, we should get different delays on multiple calls
        delays = [config.calculate_delay(1) for _ in range(10)]
        assert len(set(delays)) > 1, "Jitter should produce different delays"
        
        # All delays should be within the jitter range
        for delay in delays:
            assert 1.0 <= delay <= 3.0, f"Delay {delay} should be between 1.0 and 3.0"

class TestDatabaseRetryManager:
    """Tests for the DatabaseRetryManager class."""
    
    async def test_execute_with_retry_success_first_attempt(self, retry_manager):
        """Test that a successful operation on the first attempt returns the correct result."""
        mock_func = AsyncMock(return_value="success")
        
        result = await retry_manager.execute_with_retry(mock_func, "arg1", arg2="value")
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", arg2="value")
    
    async def test_execute_with_retry_success_after_retries(self, retry_manager):
        """Test that a successful operation after some retries returns the correct result."""
        # Mock function that fails twice then succeeds
        mock_func = AsyncMock(side_effect=[
            RetryableNeo4jError("Error 1"),
            RetryableNeo4jError("Error 2"),
            "success"
        ])
        
        result = await retry_manager.execute_with_retry(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    async def test_execute_with_retry_non_retryable_error(self, retry_manager):
        """Test that a non-retryable error is raised immediately."""
        mock_func = AsyncMock(side_effect=NonRetryableNeo4jError("Non-retryable error"))
        
        with pytest.raises(DatabaseError):
            await retry_manager.execute_with_retry(mock_func)
        
        # Should only be called once since the error is non-retryable
        mock_func.assert_called_once()
    
    async def test_execute_with_retry_max_retries_exceeded(self, retry_manager):
        """Test that exceeding max retries raises a DatabaseError."""
        # Mock function that always fails with a retryable error
        mock_func = AsyncMock(side_effect=RetryableNeo4jError("Retryable error"))
        
        with pytest.raises(DatabaseError):
            await retry_manager.execute_with_retry(mock_func)
        
        # Should be called max_retries + 1 times (initial + retries)
        assert mock_func.call_count == retry_manager.config.max_retries + 1
    
    async def test_execute_with_retry_custom_config(self):
        """Test that a custom config is respected."""
        # Create a manager with 1 retry
        retry_manager = DatabaseRetryManager(
            RetryConfig(max_retries=1, base_delay=0.01)
        )
        
        # Mock function that always fails with a retryable error
        mock_func = AsyncMock(side_effect=RetryableNeo4jError("Retryable error"))
        
        with pytest.raises(DatabaseError):
            await retry_manager.execute_with_retry(mock_func)
        
        # Should be called max_retries + 1 times (initial + retries)
        assert mock_func.call_count == 2

class TestWithRetryDecorator:
    """Tests for the with_retry decorator."""
    
    async def test_with_retry_decorator(self):
        """Test that the with_retry decorator properly applies retry logic."""
        mock_func = AsyncMock(side_effect=[
            RetryableNeo4jError("Error 1"),
            "success"
        ])
        
        @with_retry(max_retries=3, base_delay=0.01)
        async def func_with_retry(*args, **kwargs):
            return await mock_func(*args, **kwargs)
        
        result = await func_with_retry("arg1", arg2="value")
        
        assert result == "success"
        assert mock_func.call_count == 2
        mock_func.assert_called_with("arg1", arg2="value")
    
    async def test_with_retry_decorator_non_retryable_error(self):
        """Test that a non-retryable error is raised immediately with the decorator."""
        mock_func = AsyncMock(side_effect=NonRetryableNeo4jError("Non-retryable error"))
        
        @with_retry()
        async def func_with_retry():
            return await mock_func()
        
        with pytest.raises(DatabaseError):
            await func_with_retry()
        
        # Should only be called once since the error is non-retryable
        mock_func.assert_called_once()

@pytest.mark.asyncio
async def test_integration_with_real_code():
    """
    Integration test simulating a real database operation with retries.
    
    This test simulates:
    1. A function that succeeds after several retries
    2. A function that fails with a non-retryable error
    3. A function that exceeds max retries
    """
    
    # Counter to track calls
    call_count = 0
    
    @with_retry(max_retries=3, base_delay=0.01)
    async def operation_with_retry(succeed_after=2, raise_non_retryable=False):
        """Simulated database operation that can be configured to succeed or fail."""
        nonlocal call_count
        call_count += 1
        
        if raise_non_retryable:
            raise NonRetryableNeo4jError("Non-retryable operation error")
        
        if call_count < succeed_after:
            raise RetryableNeo4jError(f"Temporary error on attempt {call_count}")
        
        return "Operation succeeded"
    
    # Test case 1: Operation succeeds after retries
    call_count = 0
    result = await operation_with_retry(succeed_after=3)
    assert result == "Operation succeeded"
    assert call_count == 3
    
    # Test case 2: Non-retryable error
    call_count = 0
    with pytest.raises(DatabaseError):
        await operation_with_retry(raise_non_retryable=True)
    assert call_count == 1
    
    # Test case 3: Exceeds max retries
    call_count = 0
    with pytest.raises(DatabaseError):
        await operation_with_retry(succeed_after=10)  # Will never succeed
    assert call_count == 4  # Initial + 3 retries 