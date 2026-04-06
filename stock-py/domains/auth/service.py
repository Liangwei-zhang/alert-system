from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.auth.policies import AuthPolicy
from domains.auth.repository import EmailCodeRepository, SessionRepository, UserRepository
from domains.auth.schemas import AuthSessionResponse, AuthUserResponse, SendCodeResponse
from infra.cache.account_dashboard_cache import schedule_invalidate_account_dashboard
from infra.cache.account_profile_cache import schedule_invalidate_account_profile
from infra.core.errors import AppError
from infra.security.token_signer import get_token_signer


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repository = UserRepository(session)
        self.email_code_repository = EmailCodeRepository(session)
        self.session_repository = SessionRepository(session)
        self.policy = AuthPolicy()
        self.token_signer = get_token_signer()

    async def send_code(self, email: str, ip: str | None = None) -> SendCodeResponse:
        normalized_email = email.strip().lower()
        await self.policy.validate_send_code_limit(normalized_email)
        await self.email_code_repository.delete_expired_if_due()

        code = f"{secrets.randbelow(900000) + 100000:06d}"
        await self.email_code_repository.create_code(
            email=normalized_email,
            code=code,
            ip=ip,
            expires_at=utcnow() + timedelta(minutes=5),
        )

        if self.policy.can_return_dev_code():
            return SendCodeResponse(
                message="Verification code generated (development mode)",
                dev_code=code,
            )

        return SendCodeResponse(message="Verification code sent. Please check your inbox.")

    async def verify_code(
        self,
        email: str,
        code: str,
        locale: str | None = None,
        timezone_name: str | None = None,
        device_info: dict[str, Any] | None = None,
    ) -> AuthSessionResponse:
        record = await self.email_code_repository.find_valid_code(email, code)
        if record is None:
            raise AppError(
                code="invalid_code",
                message="Invalid or expired verification code",
                status_code=400,
            )

        existing_user = await self.user_repository.get_by_email(email)
        await self.email_code_repository.mark_used(record.id)
        user = await self.user_repository.upsert_by_email(email, locale, timezone_name)

        if not user.is_active:
            raise AppError("user_disabled", "This account has been disabled", status_code=403)

        await self.user_repository.update_last_login(user.id, locale, timezone_name)
        if locale is not None or timezone_name is not None:
            schedule_invalidate_account_dashboard(self.session, user.id)
            schedule_invalidate_account_profile(self.session, user.id)

        access_token = self.token_signer.sign(
            user.id,
            claims={
                "type": "access",
                "plan": user.plan,
                "locale": user.locale,
                "timezone": user.timezone,
            },
            expires_in=timedelta(minutes=30),
        )
        refresh_token = self.token_signer.sign(
            user.id,
            claims={"type": "refresh", "plan": user.plan},
            expires_in=timedelta(days=30),
        )

        await self.session_repository.create_session(
            token_hash=hash_token(access_token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(minutes=30),
            device_info={**(device_info or {}), "kind": "access"},
        )
        await self.session_repository.create_session(
            token_hash=hash_token(refresh_token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=30),
            device_info={**(device_info or {}), "kind": "refresh"},
        )

        return AuthSessionResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=AuthUserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                plan=user.plan,
                locale=user.locale,
                timezone=user.timezone,
                is_new=existing_user is None or self.policy.is_new_user(user),
            ),
        )

    async def logout(self, access_token: str) -> None:
        try:
            payload = self.token_signer.verify(access_token)
        except Exception as exc:
            raise AppError("invalid_token", "Token validation failed", status_code=401) from exc

        user_id = int(payload.get("sub", 0))
        if user_id <= 0:
            raise AppError("invalid_token", "Token subject is missing", status_code=401)

        await self.session_repository.revoke_for_user(user_id)

    async def refresh(self, refresh_token: str) -> AuthSessionResponse:
        try:
            payload = self.token_signer.verify(refresh_token)
        except Exception as exc:
            raise AppError("invalid_token", "Token validation failed", status_code=401) from exc

        if payload.get("type") != "refresh":
            raise AppError("invalid_token", "Refresh token is required", status_code=401)

        refresh_hash = hash_token(refresh_token)
        subject_user_id = int(payload.get("sub", 0) or 0)
        if subject_user_id <= 0:
            raise AppError("invalid_token", "Token subject is missing", status_code=401)

        active_user_id = await self.session_repository.get_active_user_id_by_token_hash(
            refresh_hash
        )
        if active_user_id is None:
            raise AppError(
                "session_revoked", "Refresh session is no longer active", status_code=401
            )
        if active_user_id != subject_user_id:
            raise AppError("invalid_token", "Token subject mismatch", status_code=401)

        user = await self.user_repository.get_by_id(subject_user_id)
        if user is None or not user.is_active:
            raise AppError("invalid_user", "User not found or disabled", status_code=401)

        access_token = self.token_signer.sign(
            user.id,
            claims={
                "type": "access",
                "plan": user.plan,
                "locale": user.locale,
                "timezone": user.timezone,
            },
            expires_in=timedelta(minutes=30),
        )
        new_refresh_token = self.token_signer.sign(
            user.id,
            claims={"type": "refresh", "plan": user.plan},
            expires_in=timedelta(days=30),
        )

        await self.session_repository.create_session(
            token_hash=hash_token(access_token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(minutes=30),
            device_info={"kind": "access", "rotated_from": "refresh"},
        )
        await self.session_repository.rotate_refresh_session(
            old_token_hash=refresh_hash,
            new_token_hash=hash_token(new_refresh_token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=30),
            device_info={"kind": "refresh", "rotated": True},
        )

        return AuthSessionResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            user=AuthUserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                plan=user.plan,
                locale=user.locale,
                timezone=user.timezone,
                is_new=False,
            ),
        )
