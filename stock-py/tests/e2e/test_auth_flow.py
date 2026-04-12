from __future__ import annotations

from domains.auth.schemas import AuthSessionResponse, AuthUserResponse, SendCodeResponse
from domains.auth.service import AuthService
from tests.helpers.app_client import PublicApiClient


def test_auth_flow(public_api_client: PublicApiClient, monkeypatch) -> None:
    calls: dict[str, object] = {}

    async def fake_send_code(self, email: str, ip: str | None = None) -> SendCodeResponse:
        calls["send_code"] = {"email": email, "ip": ip}
        return SendCodeResponse(
            message="Verification code generated (development mode)", dev_code="123456"
        )

    async def fake_verify_code(
        self,
        email: str,
        code: str,
        locale: str | None = None,
        timezone_name: str | None = None,
        device_info: dict | None = None,
    ) -> AuthSessionResponse:
        calls["verify_code"] = {
            "email": email,
            "code": code,
            "locale": locale,
            "timezone": timezone_name,
            "device_info": device_info,
        }
        return AuthSessionResponse(
            access_token="access-token-1",
            refresh_token="refresh-token-1",
            user=AuthUserResponse(
                id=42,
                email=email,
                name="QA User",
                plan="pro",
                locale=locale or "en-US",
                timezone=timezone_name or "UTC",
                is_new=True,
            ),
        )

    async def fake_refresh(self, refresh_token: str) -> AuthSessionResponse:
        calls["refresh"] = refresh_token
        return AuthSessionResponse(
            access_token="access-token-2",
            refresh_token="refresh-token-2",
            user=AuthUserResponse(
                id=42,
                email="user@example.com",
                name="QA User",
                plan="pro",
                locale="en-US",
                timezone="UTC",
                is_new=False,
            ),
        )

    async def fake_logout(self, access_token: str) -> None:
        calls["logout"] = access_token

    monkeypatch.setattr(AuthService, "send_code", fake_send_code)
    monkeypatch.setattr(AuthService, "verify_code", fake_verify_code)
    monkeypatch.setattr(AuthService, "refresh", fake_refresh)
    monkeypatch.setattr(AuthService, "logout", fake_logout)

    send_response = public_api_client.post(
        "/v1/auth/send-code",
        json={"email": "user@example.com"},
        headers={"X-Forwarded-For": "203.0.113.10"},
    )
    assert send_response.status_code == 200
    assert send_response.json() == {
        "message": "Verification code generated (development mode)",
        "dev_code": "123456",
    }

    verify_response = public_api_client.post(
        "/v1/auth/verify",
        json={
            "email": "user@example.com",
            "code": "123456",
            "locale": "en-US",
            "timezone": "UTC",
        },
        headers={"User-Agent": "pytest-e2e"},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["access_token"] == "access-token-1"
    assert verify_response.json()["refresh_token"] == "refresh-token-1"
    assert verify_response.json()["user"] == {
        "id": 42,
        "email": "user@example.com",
        "name": "QA User",
        "plan": "pro",
        "locale": "en-US",
        "timezone": "UTC",
        "is_new": True,
    }

    refresh_response = public_api_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": "refresh-token-1"},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"] == "access-token-2"
    assert refresh_response.json()["refresh_token"] == "refresh-token-2"

    logout_response = public_api_client.post(
        "/v1/auth/logout",
        headers={"Authorization": "Bearer access-token-2"},
    )
    assert logout_response.status_code == 200
    assert logout_response.json() == {"message": "Signed out successfully"}

    assert calls["send_code"] == {"email": "user@example.com", "ip": "203.0.113.10"}
    assert calls["verify_code"] == {
        "email": "user@example.com",
        "code": "123456",
        "locale": "en-US",
        "timezone": "UTC",
        "device_info": {"ip": "testclient", "user_agent": "pytest-e2e"},
    }
    assert calls["refresh"] == "refresh-token-1"
    assert calls["logout"] == "access-token-2"
