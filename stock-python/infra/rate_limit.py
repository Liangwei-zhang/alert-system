"""
Rate limiting using Redis.
"""
from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from infra.config import settings
from infra.cache import cache


def get_client_ip(request: Request) -> str:
    """Get client IP from request."""
    # Check for forwarded header (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_ip(request)


def get_remote_ip(request: Request) -> str:
    """Get remote IP."""
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=get_remote_ip)


async def check_rate_limit(key: str, limit: int = 60, window: int = 60) -> bool:
    """
    Check rate limit using Redis sliding window.
    
    Args:
        key: Unique key for rate limit (e.g., user_id or IP)
        limit: Maximum requests allowed in window
        window: Time window in seconds
    
    Returns:
        True if within limit, raises HTTPException if exceeded
    """
    current = await cache.incr(f"ratelimit:{key}")
    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {limit} requests per {window}s",
        )
    return True