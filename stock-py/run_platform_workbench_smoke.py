from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Sequence

import httpx
from sqlalchemy import select

from infra.cache.redis_client import close_redis, get_redis
from infra.db.models.admin import AdminOperatorModel
from infra.db.models.auth import EmailCodeModel, UserModel
from infra.db.session import get_session_factory


PLATFORM_TEXT_CHECKS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "platform_html",
        "/platform/",
        (
            "Desktop Access",
            "Desktop Launchpad",
            "Market Workbench",
            "桌面端验证码登录",
            "Execution Relay",
            "Research Relay",
                "Strategy Breakdown",
                "Equity Curve",
                "Calibration Proposal",
                "退出位读模型",
                "Client vs Server Exits",
                "应用建议校准",
        ),
    ),
    (
        "workspace_script",
        "/platform/js/platform-deck-workspace.js",
        (
            "workspaceLaunchpadCards()",
            "runDeskAction(actionId)",
            "applyWorkspaceFirstScreenState(options = {})",
        ),
    ),
    (
        "platform_script",
        "/platform/js/platform-deck.js",
        (
            "sendAdminCode()",
            "verifyAdminCode()",
            "refreshAdminSession(options = {})",
        ),
    ),
    (
        "market_script",
        "/platform/js/platform-deck-market.js",
        (
            "searchMarketSymbols()",
            "loadSelectedMarketChart(options = {})",
            "pinSelectedSymbolToDeskWatchlist()",
        ),
    ),
)

READ_ONLY_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("summary", "/v1/admin/signal-stats/summary?window_hours=168"),
    ("signal_stats", "/v1/admin/signal-stats?limit=5"),
    ("scanner", "/v1/admin/scanner/observability?limit=4&decision_limit=8"),
    ("rankings", "/v1/admin/backtests/rankings/latest?timeframe=1d&limit=4"),
    ("health", "/v1/admin/analytics/strategy-health?window_hours=168"),
    ("exit_quality", "/v1/admin/analytics/exit-quality?window_hours=168"),
    ("active_calibration", "/v1/admin/calibrations/active"),
    ("proposal", "/v1/admin/calibrations/proposal?signal_window_hours=24&ranking_window_hours=168"),
    ("runs", "/v1/admin/backtests/runs?limit=5&timeframe=1d"),
    ("analyses", "/v1/admin/tradingagents/analyses?limit=5"),
)


async def resolve_default_operator_email() -> str:
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(UserModel.email)
            .join(AdminOperatorModel, AdminOperatorModel.user_id == UserModel.id)
            .where(AdminOperatorModel.is_active.is_(True), UserModel.is_active.is_(True))
            .order_by(AdminOperatorModel.user_id.asc())
            .limit(1)
        )
        email = result.scalar_one_or_none()
        if email is None:
            raise RuntimeError("No active admin operator found")
        return str(email)


async def resolve_latest_email_code(email: str) -> str | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(EmailCodeModel.code)
            .where(
                EmailCodeModel.email == email.strip().lower(),
                EmailCodeModel.used_at.is_(None),
            )
            .order_by(EmailCodeModel.created_at.desc())
            .limit(1)
        )
        code = result.scalar_one_or_none()
        return str(code) if code is not None else None


async def clear_send_code_rate_limit(email: str) -> int:
    client = await get_redis()
    deleted = await client.delete(f"rate-limit:auth:send-code:{email.strip().lower()}")
    await close_redis()
    return int(deleted or 0)


def summarize_payload(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if name == "summary":
        return {
            "active_signals": payload.get("active_signals"),
            "triggered_signals": payload.get("triggered_signals"),
            "avg_confidence": payload.get("avg_confidence"),
        }
    if name == "signal_stats":
        return {"count": len(payload.get("data", []))}
    if name == "scanner":
        summary = payload.get("summary") or {}
        return {
            "recent_decisions": len(payload.get("recent_decisions", [])),
            "total_decisions": summary.get("total_decisions"),
            "emitted_decisions": summary.get("emitted_decisions"),
        }
    if name == "rankings":
        return {"count": len(payload.get("data", []))}
    if name == "health":
        return {"count": len(payload.get("strategies", []))}
    if name == "exit_quality":
        return {
            "total_signals": payload.get("total_signals"),
            "exits_available": payload.get("exits_available"),
            "avg_atr_multiplier": payload.get("avg_atr_multiplier"),
        }
    if name == "active_calibration":
        data = payload.get("data") or {}
        return {
            "version": data.get("version"),
            "effective_from": data.get("effective_from") or data.get("effective_at"),
        }
    if name == "proposal":
        return {
            "current_version": payload.get("current_version"),
            "proposed_version": payload.get("proposed_version"),
            "strategy_adjustments": len(payload.get("strategy_weights") or []),
            "atr_adjustments": len(payload.get("atr_multipliers") or []),
        }
    if name == "runs":
        return {"count": len(payload.get("data", []))}
    if name == "analyses":
        return {"count": len(payload.get("data", []))}
    return payload


def summarize_text_markers(required_markers: Sequence[str], text: str) -> dict[str, Any]:
    missing = [marker for marker in required_markers if marker not in text]
    return {
        "required": len(required_markers),
        "matched": len(required_markers) - len(missing),
        "missing": missing,
    }


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def read_json_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {"raw": response.text}
    if isinstance(payload, dict):
        return payload
    return {"data": payload}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke-test the platform workbench UI shell, dynamic admin-auth lifecycle, and read-only data flow.",
    )
    parser.add_argument("--email", help="Admin operator email to use for admin-auth")
    parser.add_argument(
        "--public-base-url",
        default="http://127.0.0.1:8000",
        help="Public API base URL",
    )
    parser.add_argument(
        "--admin-base-url",
        default="http://127.0.0.1:8001",
        help="Admin API base URL",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--no-reset-rate-limit",
        action="store_true",
        help="Do not clear the local send-code rate-limit key before the smoke run",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    public_base_url = args.public_base_url.rstrip("/")
    admin_base_url = args.admin_base_url.rstrip("/")

    with asyncio.Runner() as runner:
        email = args.email or runner.run(resolve_default_operator_email())
        if not args.no_reset_rate_limit:
            print(
                json.dumps(
                    {
                        "step": "reset_rate_limit",
                        "status": "ok",
                        "email": email,
                        "deleted": runner.run(clear_send_code_rate_limit(email)),
                    },
                    ensure_ascii=False,
                )
            )

        with httpx.Client(timeout=args.timeout) as client:
            for step_name, path, required_markers in PLATFORM_TEXT_CHECKS:
                response = client.get(f"{public_base_url}{path}")
                if response.status_code != 200:
                    emit(
                        {
                            "step": step_name,
                            "status": response.status_code,
                            "body": response.text[:500],
                        }
                    )
                    return 1

                summary = summarize_text_markers(required_markers, response.text)
                if summary["missing"]:
                    emit(
                        {
                            "step": step_name,
                            "status": response.status_code,
                            "summary": summary,
                        }
                    )
                    return 1

                emit(
                    {
                        "step": step_name,
                        "status": response.status_code,
                        "summary": summary,
                    }
                )

            send_code_response = client.post(
                f"{public_base_url}/v1/admin-auth/send-code",
                json={"email": email},
            )
            send_code_payload = read_json_payload(send_code_response)
            if send_code_response.status_code not in {200, 429}:
                emit(
                    {
                        "step": "send_code",
                        "status": send_code_response.status_code,
                        "body": send_code_payload,
                    }
                )
                return 1

            code = send_code_payload.get("dev_code") or runner.run(resolve_latest_email_code(email))
            if not code:
                emit(
                    {
                        "step": "resolve_code",
                        "status": "failed",
                        "email": email,
                    }
                )
                return 1

            emit(
                {
                    "step": "send_code",
                    "status": send_code_response.status_code,
                    "email": email,
                    "dev_code_available": bool(send_code_payload.get("dev_code")),
                }
            )

            verify_response = client.post(
                f"{public_base_url}/v1/admin-auth/verify",
                json={
                    "email": email,
                    "code": code,
                    "locale": "en-US",
                    "timezone": "UTC",
                },
                headers={"User-Agent": "platform-workbench-smoke"},
            )
            verify_payload = read_json_payload(verify_response)
            if verify_response.status_code != 200:
                emit(
                    {
                        "step": "verify",
                        "status": verify_response.status_code,
                        "body": verify_payload,
                    }
                )
                return 1

            access_token = verify_payload["access_token"]
            refresh_token = verify_payload["refresh_token"]
            headers = {"Authorization": f"Bearer {access_token}"}
            emit(
                {
                    "step": "verify",
                    "status": verify_response.status_code,
                    "email": email,
                    "role": verify_payload.get("admin", {}).get("role"),
                    "scopes": verify_payload.get("admin", {}).get("scopes"),
                }
            )

            for name, path in READ_ONLY_ENDPOINTS:
                response = client.get(f"{admin_base_url}{path}", headers=headers)
                payload = read_json_payload(response)

                if response.status_code != 200:
                    emit(
                        {
                            "step": name,
                            "status": response.status_code,
                            "body": payload,
                        }
                    )
                    return 1

                emit(
                    {
                        "step": name,
                        "status": response.status_code,
                        "summary": summarize_payload(name, payload),
                    }
                )

            refresh_response = client.post(
                f"{public_base_url}/v1/admin-auth/refresh",
                json={"refresh_token": refresh_token},
                headers={"User-Agent": "platform-workbench-smoke"},
            )
            refresh_payload = read_json_payload(refresh_response)
            if refresh_response.status_code != 200:
                emit(
                    {
                        "step": "refresh",
                        "status": refresh_response.status_code,
                        "body": refresh_payload,
                    }
                )
                return 1

            refreshed_access_token = refresh_payload["access_token"]
            refreshed_refresh_token = refresh_payload.get("refresh_token") or refresh_token
            refreshed_headers = {"Authorization": f"Bearer {refreshed_access_token}"}
            emit(
                {
                    "step": "refresh",
                    "status": refresh_response.status_code,
                    "email": refresh_payload.get("user", {}).get("email"),
                    "role": refresh_payload.get("admin", {}).get("role"),
                }
            )

            refresh_probe_response = client.get(
                f"{admin_base_url}/v1/admin/signal-stats/summary?window_hours=168",
                headers=refreshed_headers,
            )
            refresh_probe_payload = read_json_payload(refresh_probe_response)
            if refresh_probe_response.status_code != 200:
                emit(
                    {
                        "step": "summary_after_refresh",
                        "status": refresh_probe_response.status_code,
                        "body": refresh_probe_payload,
                    }
                )
                return 1

            emit(
                {
                    "step": "summary_after_refresh",
                    "status": refresh_probe_response.status_code,
                    "summary": summarize_payload("summary", refresh_probe_payload),
                }
            )

            logout_response = client.post(
                f"{public_base_url}/v1/admin-auth/logout",
                json={"refresh_token": refreshed_refresh_token},
                headers={
                    "Authorization": f"Bearer {refreshed_access_token}",
                    "User-Agent": "platform-workbench-smoke",
                },
            )
            logout_payload = read_json_payload(logout_response)
            if logout_response.status_code != 200:
                emit(
                    {
                        "step": "logout",
                        "status": logout_response.status_code,
                        "body": logout_payload,
                    }
                )
                return 1

            emit(
                {
                    "step": "logout",
                    "status": logout_response.status_code,
                    "body": logout_payload,
                }
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())