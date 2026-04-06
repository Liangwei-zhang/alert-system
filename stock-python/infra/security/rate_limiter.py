"""
Enhanced rate limiting for authentication endpoints.
Provides granular rate limiting with different limits per endpoint type.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functools import wraps
from fastapi import Request, HTTPException, status, Depends
from starlette.middleware.base import BaseHTTPMiddleware

from infra.cache import cache
from infra.config import settings


# Rate limit configurations for different auth endpoints
RATE_LIMIT_CONFIGS = {
    # Auth endpoints
    "auth:login": {"limit": 5, "window": 60, "type": "ip"},  # 5 attempts per minute
    "auth:login_failed": {"limit": 10, "window": 300, "type": "ip"},  # After failed login
    "auth:register": {"limit": 3, "window": 3600, "type": "ip"},  # 3 registrations per hour
    "auth:password_reset_request": {"limit": 3, "window": 3600, "type": "email"},  # 3 reset requests per hour
    "auth:password_reset_verify": {"limit": 5, "window": 300, "type": "email"},  # 5 verify attempts per 5 min
    "auth:verification_code": {"limit": 5, "window": 300, "type": "email"},  # 5 codes per 5 min
    "auth:refresh": {"limit": 10, "window": 60, "type": "token"},  # 10 refreshes per minute
    "auth:2fa_verify": {"limit": 5, "window": 300, "type": "user_ip"},  # 5 2FA attempts per 5 min
    
    # General endpoints
    "default:ip": {"limit": 60, "window": 60, "type": "ip"},  # 60 req/min default
    "default:user": {"limit": 120, "window": 60, "type": "user"},  # 120 req/min for authenticated
}


class AuthRateLimiter:
    """Enhanced rate limiter for authentication endpoints."""

    def __init__(self, cache_client=None):
        self.cache = cache_client or cache

    def _get_identifier(
        self, request: Request, limit_type: str, user_id: Optional[int] = None
    ) -> str:
        """Get rate limit identifier based on type."""
        # Get base IP
        ip = self._get_client_ip(request)
        
        if limit_type == "ip":
            return f"ratelimit:ip:{ip}"
        elif limit_type == "user" and user_id:
            return f"ratelimit:user:{user_id}"
        elif limit_type == "user_ip" and user_id:
            return f"ratelimit:user_ip:{user_id}:{ip}"
        elif limit_type == "email":
            email = getattr(request.state, "email", None) or "unknown"
            return f"ratelimit:email:{email}"
        elif limit_type == "token":
            token = request.headers.get("authorization", "unknown")
            return f"ratelimit:token:{hash(token) % 1000000}"
        
        return f"ratelimit:ip:{ip}"

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def check_rate_limit(
        self,
        endpoint_key: str,
        request: Request,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
    ) -> bool:
        """
        Check rate limit for an endpoint.
        
        Args:
            endpoint_key: Key from RATE_LIMIT_CONFIGS
            request: FastAPI request object
            user_id: Optional user ID for user-based limits
            email: Optional email for email-based limits
        
        Returns:
            True if within limit, raises HTTPException if exceeded
        """
        config = RATE_LIMIT_CONFIGS.get(
            endpoint_key, RATE_LIMIT_CONFIGS["default:ip"]
        )
        
        # Set email in request state if provided
        if email:
            request.state.email = email
        
        identifier = self._get_identifier(request, config["type"], user_id)
        
        # Check using sliding window
        return await self._check_sliding_window(
            identifier=identifier,
            limit=config["limit"],
            window=config["window"],
        )

    async def _check_sliding_window(
        self, identifier: str, limit: int, window: int
    ) -> bool:
        """
        Check rate limit using sliding window algorithm.
        Uses Redis sorted set for accurate counting.
        """
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window)
        
        # Use Redis sorted set for sliding window
        key = f"sliding:{identifier}"
        
        # Add current request
        try:
            pipe = self.cache.client.pipeline()  # type: ignore
            pipe.zadd(key, {f"{now.timestamp()}": now.timestamp()})
            pipe.zremrangebyscore(key, 0, window_start.timestamp())
            pipe.zcard(key)
            pipe.expire(key, window)
            results = await pipe.execute()  # type: ignore
            
            current_count = results[2]
            
            if current_count > limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": limit,
                        "window_seconds": window,
                        "retry_after": window,
                    },
                )
            
            return True
        except HTTPException:
            raise
        except Exception:
            # Fallback to simple increment
            return await self._check_simple_increment(identifier, limit, window)

    async def _check_simple_increment(
        self, identifier: str, limit: int, window: int
    ) -> bool:
        """Fallback simple increment rate limiting."""
        key = f"ratelimit:{identifier}"
        current = await self.cache.incr(key)
        
        if current == 1:
            await self.cache.client.expire(key, window)  # type: ignore
        
        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "window_seconds": window,
                },
            )
        
        return True

    async def get_remaining(
        self,
        endpoint_key: str,
        request: Request,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get remaining requests for an endpoint."""
        config = RATE_LIMIT_CONFIGS.get(
            endpoint_key, RATE_LIMIT_CONFIGS["default:ip"]
        )
        
        identifier = self._get_identifier(request, config["type"], user_id)
        key = f"sliding:{identifier}"
        
        try:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=config["window"])
            
            # Get count in current window
            count = await self.cache.client.zcount(  # type: ignore
                key, window_start.timestamp(), now.timestamp()
            )
            
            return {
                "remaining": max(0, config["limit"] - count),
                "limit": config["limit"],
                "window_seconds": config["window"],
            }
        except Exception:
            return {
                "remaining": config["limit"],
                "limit": config["limit"],
                "window_seconds": config["window"],
            }

    async def reset_limit(
        self, endpoint_key: str, request: Request, user_id: Optional[int] = None
    ) -> bool:
        """Reset rate limit for an endpoint (admin action)."""
        config = RATE_LIMIT_CONFIGS.get(endpoint_key, RATE_LIMIT_CONFIGS["default:ip"])
        identifier = self._get_identifier(request, config["type"], user_id)
        
        await self.cache.delete(f"sliding:{identifier}")
        await self.cache.delete(f"ratelimit:{identifier}")
        
        return True


# Global instance
rate_limiter = AuthRateLimiter()


# Decorator for endpoints
def rate_limit(
    endpoint_key: str,
    user_id_param: Optional[str] = "user_id",
    email_param: Optional[str] = "email",
):
    """
    Decorator to apply rate limiting to an endpoint.
    
    Usage:
        @rate_limit("auth:login")
        async def login(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find request in args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                for val in kwargs.values():
                    if isinstance(val, Request):
                        request = val
                        break
            
            if not request:
                raise ValueError("Request object not found")
            
            # Get user_id and email from kwargs if available
            user_id = kwargs.get(user_id_param)
            email = kwargs.get(email_param)
            
            await rate_limiter.check_rate_limit(
                endpoint_key, request, user_id, email
            )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Dependency for FastAPI
async def check_auth_rate_limit(
    endpoint_key: str,
    request: Request,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
):
    """FastAPI dependency for rate limiting."""
    await rate_limiter.check_rate_limit(endpoint_key, request, user_id, email)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic rate limiting based on path patterns."""

    async def dispatch(self, request: Request, call_next):
        # Determine endpoint key from path
        path = request.url.path
        
        if path.startswith("/auth/login"):
            endpoint_key = "auth:login"
        elif path.startswith("/auth/register"):
            endpoint_key = "auth:register"
        elif path.startswith("/auth/password-reset"):
            endpoint_key = "auth:password_reset_request"
        elif path.startswith("/auth/2fa"):
            endpoint_key = "auth:2fa_verify"
        elif path.startswith("/auth/refresh"):
            endpoint_key = "auth:refresh"
        else:
            endpoint_key = "default:ip"
        
        # Check rate limit
        try:
            await rate_limiter.check_rate_limit(endpoint_key, request)
        except HTTPException as e:
            return e
        
        response = await call_next(request)
        
        # Add rate limit headers
        try:
            remaining = await rate_limiter.get_remaining(endpoint_key, request)
            response.headers["X-RateLimit-Limit"] = str(remaining["limit"])
            response.headers["X-RateLimit-Remaining"] = str(remaining["remaining"])
            response.headers["X-RateLimit-Window"] = str(remaining["window_seconds"])
        except Exception:
            pass
        
        return response