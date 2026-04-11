from __future__ import annotations

import asyncio
import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.admin.repository import OperatorRepository
from domains.auth.policies import AuthPolicy
from domains.auth.repository import EmailCodeRepository, SessionRepository, UserRepository
from domains.auth.schemas import (
    AdminAuthContextResponse,
    AdminAuthSessionResponse,
    AuthSessionResponse,
    AuthUserResponse,
    SendCodeResponse,
)
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
        self.operator_repository = OperatorRepository(session)
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

            await self._deliver_auth_code_email(normalized_email, code, is_admin=False)

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
            user=self._build_auth_user_response(
                user,
                is_new=existing_user is None or self.policy.is_new_user(user),
            ),
        )

    async def send_admin_code(self, email: str, ip: str | None = None) -> SendCodeResponse:
        normalized_email = email.strip().lower()
        await self.policy.validate_send_code_limit(normalized_email)
        await self._require_active_admin_operator_by_email(normalized_email)
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
                message="Admin verification code generated (development mode)",
                dev_code=code,
            )

            await self._deliver_auth_code_email(normalized_email, code, is_admin=True)

        return SendCodeResponse(message="Admin verification code sent. Please check your inbox.")

    async def verify_admin_code(
        self,
        email: str,
        code: str,
        locale: str | None = None,
        timezone_name: str | None = None,
        device_info: dict[str, Any] | None = None,
    ) -> AdminAuthSessionResponse:
        normalized_email = email.strip().lower()
        record = await self.email_code_repository.find_valid_code(normalized_email, code)
        if record is None:
            raise AppError(
                code="invalid_code",
                message="Invalid or expired verification code",
                status_code=400,
            )

        user = await self.user_repository.get_by_email(normalized_email)
        await self.email_code_repository.mark_used(record.id)
        operator, user = await self._require_active_admin_operator_by_email(normalized_email, user=user)

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
                "is_admin": True,
                "scopes": list(getattr(operator, "scopes", []) or []),
            },
            expires_in=timedelta(minutes=30),
        )
        refresh_token = self.token_signer.sign(
            user.id,
            claims={
                "type": "refresh",
                "plan": user.plan,
                "is_admin": True,
                "scopes": list(getattr(operator, "scopes", []) or []),
            },
            expires_in=timedelta(days=30),
        )

        await self.session_repository.create_session(
            token_hash=hash_token(access_token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(minutes=30),
            device_info={**(device_info or {}), "kind": "admin_access"},
        )
        await self.session_repository.create_session(
            token_hash=hash_token(refresh_token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=30),
            device_info={**(device_info or {}), "kind": "admin_refresh"},
        )

        return AdminAuthSessionResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=self._build_auth_user_response(user, is_new=False),
            admin=AdminAuthContextResponse(
                role=str(getattr(getattr(operator, "role", None), "value", getattr(operator, "role", "operator"))),
                scopes=list(getattr(operator, "scopes", []) or []),
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
            user=self._build_auth_user_response(user, is_new=False),
        )

    async def refresh_admin(self, refresh_token: str) -> AdminAuthSessionResponse:
        try:
            payload = self.token_signer.verify(refresh_token)
        except Exception as exc:
            raise AppError("invalid_token", "Token validation failed", status_code=401) from exc

        if payload.get("type") != "refresh":
            raise AppError("invalid_token", "Refresh token is required", status_code=401)
        if not bool(payload.get("is_admin", False)):
            raise AppError("forbidden", "Admin refresh token is required", status_code=403)

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

        operator, user = await self._require_active_admin_operator(subject_user_id)

        access_token = self.token_signer.sign(
            user.id,
            claims={
                "type": "access",
                "plan": user.plan,
                "locale": user.locale,
                "timezone": user.timezone,
                "is_admin": True,
                "scopes": list(getattr(operator, "scopes", []) or []),
            },
            expires_in=timedelta(minutes=30),
        )
        new_refresh_token = self.token_signer.sign(
            user.id,
            claims={
                "type": "refresh",
                "plan": user.plan,
                "is_admin": True,
                "scopes": list(getattr(operator, "scopes", []) or []),
            },
            expires_in=timedelta(days=30),
        )

        await self.session_repository.create_session(
            token_hash=hash_token(access_token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(minutes=30),
            device_info={"kind": "admin_access", "rotated_from": "refresh"},
        )
        await self.session_repository.rotate_refresh_session(
            old_token_hash=refresh_hash,
            new_token_hash=hash_token(new_refresh_token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=30),
            device_info={"kind": "admin_refresh", "rotated": True},
        )

        return AdminAuthSessionResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            user=self._build_auth_user_response(user, is_new=False),
            admin=AdminAuthContextResponse(
                role=str(getattr(getattr(operator, "role", None), "value", getattr(operator, "role", "operator"))),
                scopes=list(getattr(operator, "scopes", []) or []),
            ),
        )

    async def logout_tokens(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        payloads: list[tuple[str, dict[str, Any]]] = []
        for token in (access_token, refresh_token):
            if not token:
                continue
            try:
                payload = self.token_signer.verify(token)
            except Exception as exc:
                raise AppError("invalid_token", "Token validation failed", status_code=401) from exc
            payloads.append((token, payload))

        if not payloads:
            return

        subject_user_id = int(payloads[0][1].get("sub", 0) or 0)
        if subject_user_id <= 0:
            raise AppError("invalid_token", "Token subject is missing", status_code=401)

        for _token, payload in payloads[1:]:
            if int(payload.get("sub", 0) or 0) != subject_user_id:
                raise AppError("invalid_token", "Token subject mismatch", status_code=401)

        for token, _payload in payloads:
            await self.session_repository.revoke_by_token_hash(hash_token(token))

    def _build_auth_user_response(self, user: Any, *, is_new: bool) -> AuthUserResponse:
        return AuthUserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            plan=user.plan,
            locale=user.locale,
            timezone=user.timezone,
            is_new=is_new,
        )

    async def _deliver_auth_code_email(
        self,
        recipient_email: str,
        code: str,
        *,
        is_admin: bool,
    ) -> None:
        from infra.core.config import get_settings

        settings = get_settings()
        if not settings.smtp_host:
            raise AppError(
                code="smtp_not_configured",
                message="Verification email delivery is not configured.",
                status_code=503,
            )

        account_label = "admin account" if is_admin else "account"
        subject = "StockPy admin verification code" if is_admin else "StockPy verification code"
        text_body = (
            f"Your StockPy {account_label} verification code is {code}. "
            "The code expires in 5 minutes."
        )
        html_body = (
            "<html><body>"
            f"<h2>{subject}</h2>"
            f"<p>Your StockPy {account_label} verification code is "
            f"<strong>{code}</strong>.</p>"
            "<p>The code expires in 5 minutes.</p>"
            "</body></html>"
        )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((settings.email_from_name, settings.email_from_address))
        message["To"] = recipient_email
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        def send_message() -> None:
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as client:
                if settings.smtp_use_tls:
                    client.starttls()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)

        try:
            await asyncio.to_thread(send_message)
        except Exception as exc:
            raise AppError(
                code="send_code_delivery_failed",
                message="Failed to deliver verification code email.",
                status_code=503,
                details={"reason": str(exc)},
            ) from exc

    async def _require_active_admin_operator_by_email(
        self,
        email: str,
        *,
        user: Any | None = None,
    ):
        user = user or await self.user_repository.get_by_email(email)
        if user is None or not user.is_active:
            raise AppError(
                "admin_access_not_granted",
                "This account does not have active admin access.",
                status_code=403,
            )
        return await self._require_active_admin_operator(user.id, user=user)

    async def _require_active_admin_operator(self, user_id: int, *, user: Any | None = None):
        operator, operator_user = await self.operator_repository.get_active_operator(user_id)
        resolved_user = user or operator_user
        if operator is None or resolved_user is None or not resolved_user.is_active:
            raise AppError(
                "admin_access_not_granted",
                "This account does not have active admin access.",
                status_code=403,
            )
        return operator, resolved_user
