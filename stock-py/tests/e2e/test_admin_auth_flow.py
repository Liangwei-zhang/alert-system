from __future__ import annotations

from domains.auth.schemas import (
    AdminAuthContextResponse,
    AdminAuthSessionResponse,
    AuthUserResponse,
    LogoutResponse,
    SendCodeResponse,
)
from domains.auth.service import AuthService
from tests.helpers.app_client import PublicApiClient


def test_admin_auth_flow(public_api_client: PublicApiClient, monkeypatch) -> None:
    calls: dict[str, object] = {}

    async def fake_send_admin_code(
        self,
        email: str,
        ip: str | None = None,
    ) -> SendCodeResponse:
        calls["send_admin_code"] = {"email": email, "ip": ip}
        return SendCodeResponse(
            message="Admin verification code generated (development mode)",
            dev_code="654321",
        )

    async def fake_verify_admin_code(
        self,
        email: str,
        code: str,
        locale: str | None = None,
        timezone_name: str | None = None,
        device_info: dict | None = None,
    ) -> AdminAuthSessionResponse:
        calls["verify_admin_code"] = {
            "email": email,
            "code": code,
            "locale": locale,
            "timezone": timezone_name,
            "device_info": device_info,
        }
        return AdminAuthSessionResponse(
            access_token="admin-access-token-1",
            refresh_token="admin-refresh-token-1",
            user=AuthUserResponse(
                id=7,
                email=email,
                name="Admin User",
                plan="enterprise",
                locale=locale or "en-US",
                timezone=timezone_name or "UTC",
                is_new=False,
            ),
            admin=AdminAuthContextResponse(role="admin", scopes=["runtime", "analytics"]),
        )

    async def fake_refresh_admin(self, refresh_token: str) -> AdminAuthSessionResponse:
        calls["refresh_admin"] = refresh_token
        return AdminAuthSessionResponse(
            access_token="admin-access-token-2",
            refresh_token="admin-refresh-token-2",
            user=AuthUserResponse(
                id=7,
                email="admin@example.com",
                name="Admin User",
                plan="enterprise",
                locale="en-US",
                timezone="UTC",
                is_new=False,
            ),
            admin=AdminAuthContextResponse(role="admin", scopes=["runtime", "analytics"]),
        )

    async def fake_logout_tokens(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        calls["logout_tokens"] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    monkeypatch.setattr(AuthService, "send_admin_code", fake_send_admin_code)
    monkeypatch.setattr(AuthService, "verify_admin_code", fake_verify_admin_code)
    monkeypatch.setattr(AuthService, "refresh_admin", fake_refresh_admin)
    monkeypatch.setattr(AuthService, "logout_tokens", fake_logout_tokens)

    send_response = public_api_client.post(
        "/v1/admin-auth/send-code",
        json={"email": "admin@example.com"},
        headers={"X-Forwarded-For": "203.0.113.10"},
    )
    assert send_response.status_code == 200
    assert send_response.json() == {
        "message": "Admin verification code generated (development mode)",
        "dev_code": "654321",
    }

    verify_response = public_api_client.post(
        "/v1/admin-auth/verify",
        json={
            "email": "admin@example.com",
            "code": "654321",
            "locale": "en-US",
            "timezone": "UTC",
        },
        headers={"User-Agent": "pytest-admin-e2e"},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["access_token"] == "admin-access-token-1"
    assert verify_response.json()["refresh_token"] == "admin-refresh-token-1"
    assert verify_response.json()["admin"] == {
        "role": "admin",
        "scopes": ["runtime", "analytics"],
    }

    refresh_response = public_api_client.post(
        "/v1/admin-auth/refresh",
        json={"refresh_token": "admin-refresh-token-1"},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"] == "admin-access-token-2"
    assert refresh_response.json()["refresh_token"] == "admin-refresh-token-2"

    logout_response = public_api_client.post(
        "/v1/admin-auth/logout",
        json={"refresh_token": "admin-refresh-token-2"},
        headers={"Authorization": "Bearer admin-access-token-2"},
    )
    assert logout_response.status_code == 200
    assert logout_response.json() == LogoutResponse(message="Signed out successfully").model_dump()

    assert calls["send_admin_code"] == {"email": "admin@example.com", "ip": "203.0.113.10"}
    assert calls["verify_admin_code"] == {
        "email": "admin@example.com",
        "code": "654321",
        "locale": "en-US",
        "timezone": "UTC",
        "device_info": {"ip": "testclient", "user_agent": "pytest-admin-e2e"},
    }
    assert calls["refresh_admin"] == "admin-refresh-token-1"
    assert calls["logout_tokens"] == {
        "access_token": "admin-access-token-2",
        "refresh_token": "admin-refresh-token-2",
    }