from __future__ import annotations

from infra.core.errors import AppError


class AuthPolicy:
    def __init__(self, rate_limiter=None) -> None:
        self.rate_limiter = rate_limiter

    def can_return_dev_code(self) -> bool:
        from infra.core.config import get_settings

        return get_settings().environment.lower() != "production"

    def is_new_user(self, user) -> bool:
        if user.last_login_at is None:
            return True
        return abs((user.last_login_at - user.created_at).total_seconds()) < 5

    async def validate_send_code_limit(self, email: str) -> None:
        if self.rate_limiter is None:
            from infra.cache.rate_limit import RedisRateLimiter

            self.rate_limiter = RedisRateLimiter()

        allowed = await self.rate_limiter.hit(
            key=f"auth:send-code:{email.strip().lower()}",
            limit=1,
            window_seconds=60,
        )
        if not allowed:
            raise AppError(
                code="send_code_rate_limited",
                message="A code was already sent. Please wait 60 seconds before trying again.",
                status_code=429,
            )
