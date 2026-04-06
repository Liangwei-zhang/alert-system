from __future__ import annotations

from typing import Any

from infra.core.config import get_settings
from infra.core.errors import AppError
from infra.http.http_client import get_http_client_factory


class TelegramRelayService:
    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        disable_notification: bool = False,
    ) -> dict[str, Any]:
        settings = get_settings()
        bot_token = str(settings.telegram_bot_token or "").strip()
        if not bot_token:
            raise AppError(
                "telegram_not_configured",
                "Telegram relay bot token is not configured",
                status_code=503,
            )

        client = await get_http_client_factory().get_external_client()
        base_url = str(settings.telegram_api_base_url or "https://api.telegram.org").rstrip("/")
        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "text": str(text),
            "disable_notification": bool(disable_notification),
        }
        if parse_mode:
            payload["parse_mode"] = str(parse_mode)

        response = await client.post(f"{base_url}/bot{bot_token}/sendMessage", json=payload)
        if response.status_code >= 400:
            raise AppError(
                "telegram_relay_failed",
                f"Telegram relay failed with status {response.status_code}",
                status_code=502,
            )

        body = response.json()
        if not body.get("ok"):
            raise AppError(
                "telegram_relay_failed",
                "Telegram relay returned a non-ok response",
                status_code=502,
            )

        result = dict(body.get("result") or {})
        chat = result.get("chat") or {}
        return {
            "ok": True,
            "message_id": int(result.get("message_id") or 0),
            "chat_id": str(chat.get("id") or chat_id),
        }