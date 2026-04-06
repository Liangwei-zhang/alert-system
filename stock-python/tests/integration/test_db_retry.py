"""Database retry logic tests."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.exc import OperationalError

from infra.db.retry import (
    RetryConfig,
    retry_db_operation,
    with_db_retry,
    DatabaseRetryError,
    DatabaseConnectionPool,
    is_retryable_exception,
    RETRYABLE_EXCEPTIONS,
)


class TestRetryConfig:
    """Tests for RetryConfig."""
    
    def test_default_config(self):
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
    
    def test_custom_config(self):
        config = RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
        )
        assert config.max_attempts == 5
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
    
    def test_get_delay_exponential(self):
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        
        delay_0 = config.get_delay(0)
        delay_1 = config.get_delay(1)
        delay_2 = config.get_delay(2)
        
        assert delay_0 == 1.0
        assert delay_1 == 2.0
        assert delay_2 == 4.0
    
    def test_get_delay_max_cap(self):
        config = RetryConfig(base_delay=10.0, max_delay=5.0, jitter=False)
        
        delay = config.get_delay(10)
        assert delay <= 5.0
    
    def test_get_delay_jitter(self):
        config = RetryConfig(base_delay=1.0, jitter=True)
        
        delays = [config.get_delay(0) for _ in range(100)]
        # With jitter, delays should vary
        assert max(delays) > min(delays)


class TestIsRetryableException:
    """Tests for exception classification."""
    
    def test_operational_error_retryable(self):
        exc = OperationalError("test", "test", "test")
        assert is_retryable_exception(exc) is True
    
    def test_connection_error_retryable(self):
        assert is_retryable_exception(ConnectionRefusedError()) is True
        assert is_retryable_exception(ConnectionResetError()) is True
    
    def test_timeout_retryable(self):
        assert is_retryable_exception(asyncio.TimeoutError()) is True
    
    def test_os_error_retryable(self):
        assert is_retryable_exception(OSError("test")) is True
    
    def test_non_retryable_exception(self):
        assert is_retryable_exception(ValueError("test")) is False
        assert is_retryable_exception(TypeError("test")) is False


class TestRetryDbOperation:
    """Tests for retry_db_operation function."""
    
    @pytest.mark.asyncio
    async def test_successful_operation_no_retry(self):
        """Test that successful operation completes without retries."""
        async def success_operation():
            return "success"
        
        result = await retry_db_operation(success_operation)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self):
        """Test retry after transient database failure."""
        call_count = 0
        
        async def transient_failure():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("test", "test", "test")
            return "success"
        
        config = RetryConfig(max_attempts=5, base_delay=0.01)
        result = await retry_db_operation(transient_failure, config=config)
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_exhaust_all_retries(self):
        """Test that all retries are exhausted on persistent failure."""
        async def always_fail():
            raise OperationalError("test", "test", "test")
        
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        
        with pytest.raises(DatabaseRetryError):
            await retry_db_operation(always_fail, config=config)
    
    @pytest.mark.asyncio
    async def test_non_retryable_exception_raises_immediately(self):
        """Test that non-retryable exceptions are raised immediately."""
        async def bad_operation():
            raise ValueError("not retryable")
        
        config = RetryConfig(max_attempts=3)
        
        with pytest.raises(ValueError):
            await retry_db_operation(bad_operation, config=config)
    
    @pytest.mark.asyncio
    async def test_operation_with_args(self):
        """Test operation that takes arguments."""
        async def add(a, b):
            return a + b
        
        result = await retry_db_operation(add, 1, 2)
        assert result == 3
    
    @pytest.mark.asyncio
    async def test_operation_with_kwargs(self):
        """Test operation that takes keyword arguments."""
        async def greet(name, greeting="hello"):
            return f"{greeting}, {name}!"
        
        result = await retry_db_operation(greet, "world", greeting="hi")
        assert result == "hi, world!"


class TestWithDbRetryDecorator:
    """Tests for with_db_retry decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator with successful operation."""
        @with_db_retry()
        async def my_operation():
            return "success"
        
        result = await my_operation()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_decorator_with_custom_config(self):
        """Test decorator with custom config."""
        @with_db_retry(RetryConfig(max_attempts=5, base_delay=0.01))
        async def my_operation():
            return "success"
        
        result = await my_operation()
        assert result == "success"


class TestDatabaseConnectionPool:
    """Tests for DatabaseConnectionPool."""
    
    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting a session from pool."""
        mock_maker = AsyncMock()
        mock_session = MagicMock()
        mock_maker.return_value = mock_session
        
        pool = DatabaseConnectionPool(mock_maker)
        session = await pool.get_session()
        
        assert session == mock_session
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self):
        """Test execute_with_retry successful execution."""
        mock_maker = AsyncMock()
        mock_session = AsyncMock()
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=None)
        
        async def operation(s):
            return "result"
        
        pool = DatabaseConnectionPool(mock_maker)
        result = await pool.execute_with_retry(operation)
        
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_rollback_on_error(self):
        """Test that rollback occurs on error."""
        mock_maker = AsyncMock()
        mock_session = AsyncMock()
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=None)
        
        async def operation(s):
            raise OperationalError("test", "test", "test")
        
        pool = DatabaseConnectionPool(mock_maker, RetryConfig(max_attempts=2, base_delay=0.01))
        
        with pytest.raises(DatabaseRetryError):
            await pool.execute_with_retry(operation)
        
        mock_session.rollback.assert_called()


class TestIntegration:
    """Integration-style tests for real-world scenarios."""
    
    @pytest.mark.asyncio
    async def test_connection_timeout_scenario(self):
        """Test handling of connection timeout scenarios."""
        call_count = 0
        
        async def flaky_connection():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise asyncio.TimeoutError("connection timeout")
            return "connected"
        
        result = await retry_db_operation(
            flaky_connection,
            config=RetryConfig(max_attempts=3, base_delay=0.01),
        )
        
        assert result == "connected"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_multiple_error_types(self):
        """Test handling of different error types in sequence."""
        errors = [
            ConnectionRefusedError(),
            OperationalError("test", "test", "test"),
            asyncio.TimeoutError(),
            None,  # Success
        ]
        
        async def error_sequence():
            error = errors.pop(0)
            if error:
                raise error
            return "success"
        
        result = await retry_db_operation(
            error_sequence,
            config=RetryConfig(max_attempts=5, base_delay=0.01),
        )
        
        assert result == "success"
