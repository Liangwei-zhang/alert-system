"""Database connection retry logic with exponential backoff."""
import asyncio
import logging
from functools import wraps
from typing import Callable, Optional, Type, Tuple, Any

from sqlalchemy.exc import OperationalError, InterfaceError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DatabaseRetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


class RetryConfig:
    """Configuration for database retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt using exponential backoff."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            import random
            delay *= (0.5 + random.random())
        
        return delay


# Default retry configuration
default_retry_config = RetryConfig()


# Retryable database exceptions
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    OperationalError,
    InterfaceError,
    ConnectionRefusedError,
    ConnectionResetError,
    asyncio.TimeoutError,
    OSError,
)


def is_retryable_exception(exc: Exception) -> bool:
    """Check if the exception is retryable."""
    return isinstance(exc, RETRYABLE_EXCEPTIONS)


async def retry_db_operation(
    operation: Callable,
    *args: Any,
    config: Optional[RetryConfig] = None,
    **kwargs: Any,
) -> Any:
    """Retry a database operation with exponential backoff.
    
    Args:
        operation: Async function to execute
        *args: Positional arguments for the operation
        config: Retry configuration (uses default if not provided)
        **kwargs: Keyword arguments for the operation
        
    Returns:
        Result of the operation
        
    Raises:
        DatabaseRetryError: If all retry attempts fail
        exc: The last exception if all retries are exhausted
    """
    config = config or default_retry_config
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return await operation(*args, **kwargs)
        except Exception as exc:
            if not is_retryable_exception(exc):
                logger.error(f"Non-retryable exception: {exc}")
                raise
            
            last_exception = exc
            
            if attempt < config.max_attempts - 1:
                delay = config.get_delay(attempt)
                logger.warning(
                    f"Database operation failed (attempt {attempt + 1}/{config.max_attempts}). "
                    f"Retrying in {delay:.2f}s... Error: {exc}"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"Database operation failed after {config.max_attempts} attempts. "
                    f"Last error: {exc}"
                )
    
    raise DatabaseRetryError(
        f"Operation failed after {config.max_attempts} attempts"
    ) from last_exception


def with_db_retry(config: Optional[RetryConfig] = None):
    """Decorator to add retry logic to async database functions.
    
    Usage:
        @with_db_retry()
        async def my_db_function(session: AsyncSession):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            return await retry_db_operation(
                func,
                *args,
                config=config,
                **kwargs,
            )
        return wrapper
    return decorator


class DatabaseConnectionPool:
    """Database connection pool with retry logic."""
    
    def __init__(
        self,
        session_maker: Any,
        config: Optional[RetryConfig] = None,
    ):
        self.session_maker = session_maker
        self.config = config or default_retry_config
    
    async def get_session(self) -> AsyncSession:
        """Get a session from the pool with retry logic."""
        async def _create_session():
            return self.session_maker()
        
        return await retry_db_operation(
            _create_session,
            config=self.config,
        )
    
    async def execute_with_retry(
        self,
        operation: Callable[[AsyncSession], Any],
        config: Optional[RetryConfig] = None,
    ) -> Any:
        """Execute an operation within a session with retry logic."""
        config = config or self.config
        
        async def _execute():
            async with self.session_maker() as session:
                try:
                    result = await operation(session)
                    await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise
        
        return await retry_db_operation(_execute, config=config)


# Convenience function for common retry scenarios
async def execute_with_retry(
    session: AsyncSession,
    operation: Callable,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a database operation with default retry behavior.
    
    Args:
        session: Database session
        operation: Async operation to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Result of the operation
    """
    return await retry_db_operation(
        operation,
        *args,
        config=default_retry_config,
        **kwargs,
    )
