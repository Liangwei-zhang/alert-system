from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Mapping
from uuid import uuid4

from jose import JWTError, jwt

from infra.core.config import get_settings


class TokenSigner:
    def __init__(
        self,
        secret_key: str,
        algorithm: str,
        default_ttl_minutes: int,
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.default_ttl_minutes = default_ttl_minutes

    def sign(
        self,
        subject: str | int,
        claims: Mapping[str, Any] | None = None,
        expires_in: timedelta | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        ttl = expires_in or timedelta(minutes=self.default_ttl_minutes)
        payload = dict(claims or {})
        payload.setdefault("jti", uuid4().hex)
        payload.update(
            {
                "sub": str(subject),
                "iat": int(now.timestamp()),
                "exp": int((now + ttl).timestamp()),
            }
        )
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify(self, token: str) -> dict[str, Any]:
        payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        if not isinstance(payload, dict):
            raise JWTError("Invalid token payload")
        return payload


@lru_cache(maxsize=1)
def get_token_signer() -> TokenSigner:
    settings = get_settings()
    return TokenSigner(
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        default_ttl_minutes=settings.access_token_expire_minutes,
    )
