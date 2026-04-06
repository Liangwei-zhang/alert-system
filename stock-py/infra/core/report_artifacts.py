from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

DEFAULT_LOAD_SCENARIOS = (
    "auth_read",
    "dashboard_read",
    "notification_read",
    "trade_action",
    "tradingagents_submit",
)

DEFAULT_LOAD_FIXTURES = (
    "LOAD_TEST_ACCESS_TOKEN",
    "LOAD_TEST_REFRESH_TOKEN",
    "LOAD_TEST_TRADE_ID",
    "LOAD_TEST_TRADE_TOKEN",
)

LOAD_SCENARIO_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "auth_read": ("auth.send_code", "auth.refresh"),
    "dashboard_read": ("account.dashboard", "account.profile"),
    "notification_read": ("notifications.list", "notifications.push_devices"),
    "trade_action": ("trades.app_info", "trades.public_info"),
    "tradingagents_submit": ("tradingagents.submit",),
}

ENV_PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")
REVIEW_PLACEHOLDER_PATTERN = re.compile(r"<(fill|assign|record|planned|set)[^>]*>", re.IGNORECASE)
IGNORED_PAYLOAD = object()
POSTGRES_DUMP_CANDIDATES = ("stock_py.dump", "stock.dump")


@dataclass(frozen=True)
class ShadowReadScenario:
    name: str
    scope: str
    method: str
    primary_url: str
    shadow_url: str
    primary_headers: dict[str, str]
    shadow_headers: dict[str, str]
    primary_params: dict[str, Any]
    shadow_params: dict[str, Any]
    primary_json: Any | None
    shadow_json: Any | None
    ignore_json_paths: tuple[str, ...]


@dataclass(frozen=True)
class DualWriteScenario:
    name: str
    scope: str
    write_method: str
    primary_write_url: str
    shadow_write_url: str | None
    primary_write_headers: dict[str, str]
    shadow_write_headers: dict[str, str]
    primary_write_params: dict[str, Any]
    shadow_write_params: dict[str, Any]
    primary_write_json: Any | None
    shadow_write_json: Any | None
    verify_method: str
    primary_verify_url: str
    shadow_verify_url: str
    primary_verify_headers: dict[str, str]
    shadow_verify_headers: dict[str, str]
    primary_verify_params: dict[str, Any]
    shadow_verify_params: dict[str, Any]
    primary_verify_json: Any | None
    shadow_verify_json: Any | None
    ignore_json_paths: tuple[str, ...]
    settle_seconds: float
    containment_decision: str


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_json_if_missing(path: Path, payload: dict[str, Any]) -> bool:
    if path.exists():
        return False
    _write_json(path, payload)
    return True


def _capture_http_payload(
    *,
    url: str,
    destination: Path,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    request_headers = {key: value for key, value in (headers or {}).items() if value}
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(url, headers=request_headers)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" in content_type or destination.suffix == ".json":
            _write_json(destination, response.json())
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(response.text, encoding="utf-8")
        return {
            "url": url,
            "path": str(destination),
            "status_code": response.status_code,
            "content_type": content_type,
        }


def _locate_backup_postgres_dump(backup_dir: Path) -> Path:
    postgres_dir = backup_dir / "postgres"
    for dump_name in POSTGRES_DUMP_CANDIDATES:
        candidate = postgres_dir / dump_name
        if candidate.exists():
            return candidate
    return postgres_dir / POSTGRES_DUMP_CANDIDATES[0]


def _capture_http_evidence(
    *,
    url: str,
    destination: Path,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    normalized_url = url.strip()
    if not normalized_url:
        return {
            "url": "",
            "path": str(destination),
            "status_code": None,
            "content_type": "",
            "error": "skipped: missing url",
            "skipped": True,
        }

    try:
        result = _capture_http_payload(
            url=normalized_url,
            destination=destination,
            headers=headers,
            timeout_seconds=timeout_seconds,
        )
        result["error"] = ""
        result["skipped"] = False
        return result
    except Exception as exc:
        destination.parent.mkdir(parents=True, exist_ok=True)
        failure_payload = {
            "url": normalized_url,
            "path": str(destination),
            "captured_at": _utc_timestamp(),
            "error": str(exc),
        }
        if destination.suffix == ".json":
            _write_json(destination, failure_payload)
        else:
            destination.write_text(str(exc) + "\n", encoding="utf-8")
        return {
            "url": normalized_url,
            "path": str(destination),
            "status_code": None,
            "content_type": "",
            "error": str(exc),
            "skipped": False,
        }


def _display(value: str | None, placeholder: str) -> str:
    normalized = (value or "").strip()
    return normalized or placeholder


def _is_truthy(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _replace_markdown_field(template: str, label: str, value: str) -> str:
    target_prefix = f"- {label}:"
    replacement = f"{target_prefix} {value}"
    lines = template.splitlines()
    replaced = False

    for index, line in enumerate(lines):
        if line.startswith(target_prefix):
            lines[index] = replacement
            replaced = True
            break

    if not replaced:
        raise ValueError(f"Template field not found: {label}")

    return "\n".join(lines) + "\n"


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _parse_int(value: Any) -> int:
    try:
        return int(float(str(value or "0").strip() or "0"))
    except (TypeError, ValueError):
        return 0


def _parse_float(value: Any) -> float:
    raw = str(value or "").strip()
    if not raw or raw.upper() == "N/A":
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _format_ms(value: float) -> str:
    if math.isclose(value, round(value), rel_tol=0.0, abs_tol=0.05):
        return f"{int(round(value))} ms"
    if value >= 100:
        return f"{value:.1f} ms"
    return f"{value:.2f} ms"


def _format_rate(value: float, suffix: str) -> str:
    return f"{value:.2f} {suffix}"


def _format_percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.00% (0/0)"
    return f"{(numerator / denominator) * 100:.2f}% ({numerator}/{denominator})"


def _replace_markdown_table_row(content: str, row_name: str, cells: list[str]) -> str:
    prefix = f"| {row_name} |"
    replacement = "| " + " | ".join([row_name, *cells]) + " |"
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            return "\n".join(lines) + "\n"
    raise ValueError(f"Markdown table row not found: {row_name}")


def _decode_failure_error(error_text: str) -> tuple[str, str]:
    normalized = error_text.replace('""', '"')
    status_match = re.search(r"unexpected status\s+(\d+)", normalized)
    code_match = re.search(r'"code"\s*:\s*"([^"]+)"', normalized)
    status = status_match.group(1) if status_match else ""
    code = code_match.group(1) if code_match else ""
    return status, code


def _build_load_failure_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    issue_counts: Counter[str] = Counter()
    expected_limits: Counter[str] = Counter()
    follow_up_actions: list[str] = []

    for row in rows:
        name = str(row.get("Name") or "").strip()
        if not name:
            continue
        occurrences = _parse_int(row.get("Occurrences"))
        if occurrences <= 0:
            continue

        status, code = _decode_failure_error(str(row.get("Error") or ""))
        label_parts = [name]
        if status:
            label_parts.append(status)
        if code:
            label_parts.append(code)
        issue_counts[" ".join(label_parts)] += occurrences

        if status == "429" or "rate_limit" in code:
            expected_limits[f"{name} rate limit"] += occurrences

    if any(label.startswith("auth.send_code") for label in issue_counts):
        follow_up_actions.append("rotate disposable auth fixtures or cool down send-code between runs")
    if any(label.startswith("auth.refresh") for label in issue_counts):
        follow_up_actions.append("refresh access tokens from live sessions instead of reusing revoked fixtures")
    if any(label.startswith("tradingagents.submit") for label in issue_counts):
        follow_up_actions.append("align TradingAgents load payload with accepted trigger_type values")

    return {
        "issue_counts": issue_counts,
        "expected_limits": expected_limits,
        "follow_up_actions": follow_up_actions,
    }


def _build_load_report_backfill(report_prefix: str) -> dict[str, Any]:
    report_prefix_path = Path(report_prefix)
    stats_rows = _read_csv_rows(Path(f"{report_prefix}_stats.csv"))
    history_rows = _read_csv_rows(Path(f"{report_prefix}_stats_history.csv"))
    failure_rows = _read_csv_rows(Path(f"{report_prefix}_failures.csv"))

    aggregated_row = next(
        (row for row in stats_rows if str(row.get("Name") or "").strip() == "Aggregated"),
        {},
    )
    scenario_rows = {
        str(row.get("Name") or "").strip(): row
        for row in stats_rows
        if str(row.get("Name") or "").strip() and str(row.get("Name") or "").strip() != "Aggregated"
    }

    total_requests = _parse_int(aggregated_row.get("Request Count"))
    total_failures = _parse_int(aggregated_row.get("Failure Count"))
    peak_rps = max(
        (
            _parse_float(row.get("Requests/s"))
            for row in history_rows
            if str(row.get("Name") or "").strip() == "Aggregated"
        ),
        default=_parse_float(aggregated_row.get("Requests/s")),
    )
    peak_failures_per_second = max(
        (
            _parse_float(row.get("Failures/s"))
            for row in history_rows
            if str(row.get("Name") or "").strip() == "Aggregated"
        ),
        default=_parse_float(aggregated_row.get("Failures/s")),
    )
    failure_summary = _build_load_failure_summary(failure_rows)
    top_issues = [
        f"{label} x{count}"
        for label, count in failure_summary["issue_counts"].most_common(3)
    ]

    scenario_summaries: dict[str, dict[str, str]] = {}
    for scenario_name, endpoint_names in LOAD_SCENARIO_ENDPOINTS.items():
        rows = [scenario_rows[name] for name in endpoint_names if name in scenario_rows]
        request_count = sum(_parse_int(row.get("Request Count")) for row in rows)
        failure_count = sum(_parse_int(row.get("Failure Count")) for row in rows)
        share = (request_count / total_requests * 100.0) if total_requests else 0.0
        p95 = max((_parse_float(row.get("95%")) for row in rows), default=0.0)
        issue_notes = [
            f"{label} x{count}"
            for label, count in failure_summary["issue_counts"].items()
            if label.split(" ", 1)[0] in endpoint_names
        ]
        if rows:
            notes = (
                f"{request_count} req, {failure_count} fail ({_format_percent(failure_count, request_count)}); "
                f"worst P95 {_format_ms(p95)}"
            )
            if issue_notes:
                notes += "; issues: " + ", ".join(issue_notes[:2])
            else:
                notes += "; all sampled requests passed"
        else:
            notes = "No matching endpoints found in Locust CSV"

        scenario_summaries[scenario_name] = {
            "weight": f"{share:.1f}% request share",
            "notes": notes,
        }

    expected_limits = [
        f"{label} x{count}"
        for label, count in failure_summary["expected_limits"].most_common(3)
    ]
    findings = {
        "regressions": ", ".join(top_issues) if top_issues else "none observed",
        "expected_limits": ", ".join(expected_limits) if expected_limits else "none observed",
        "follow_up": "; ".join(failure_summary["follow_up_actions"]) if failure_summary["follow_up_actions"] else "none",
    }

    saturation_parts = []
    if total_failures:
        saturation_parts.append(f"error rate {_format_percent(total_failures, total_requests)}")
    if peak_failures_per_second > 0:
        saturation_parts.append(f"peak failures {_format_rate(peak_failures_per_second, 'fail/s')}")
    if top_issues:
        saturation_parts.append("top issues: " + ", ".join(top_issues))

    return {
        "summary_path": str(report_prefix_path.parent / "baseline-summary.md"),
        "csv_path": str(Path(f"{report_prefix}_stats.csv")),
        "history_path": str(Path(f"{report_prefix}_stats_history.csv")),
        "failures_path": str(Path(f"{report_prefix}_failures.csv")),
        "total_requests": total_requests,
        "total_failures": total_failures,
        "error_rate": _format_percent(total_failures, total_requests),
        "p50_latency": _format_ms(_parse_float(aggregated_row.get("50%"))),
        "p95_latency": _format_ms(_parse_float(aggregated_row.get("95%"))),
        "p99_latency": _format_ms(_parse_float(aggregated_row.get("99%"))),
        "peak_rps": _format_rate(peak_rps, "req/s"),
        "saturation_signals": "; ".join(saturation_parts) if saturation_parts else "none observed",
        "scenario_summaries": scenario_summaries,
        "findings": findings,
        "top_issues": top_issues,
    }


def _backfill_load_summary(report_prefix: str) -> dict[str, Any] | None:
    summary_path = Path(report_prefix).parent / "baseline-summary.md"
    if not summary_path.exists():
        return None

    backfill = _build_load_report_backfill(report_prefix)
    if backfill["total_requests"] <= 0:
        return None

    content = summary_path.read_text(encoding="utf-8")
    content = _replace_markdown_table_row(content, "Total requests", [str(backfill["total_requests"])])
    content = _replace_markdown_table_row(content, "Error rate", [backfill["error_rate"]])
    content = _replace_markdown_table_row(content, "P50 latency", [backfill["p50_latency"]])
    content = _replace_markdown_table_row(content, "P95 latency", [backfill["p95_latency"]])
    content = _replace_markdown_table_row(content, "P99 latency", [backfill["p99_latency"]])
    content = _replace_markdown_table_row(content, "Peak RPS", [backfill["peak_rps"]])
    content = _replace_markdown_table_row(content, "Saturation signals", [backfill["saturation_signals"]])
    for scenario_name, scenario_summary in backfill["scenario_summaries"].items():
        content = _replace_markdown_table_row(
            content,
            scenario_name,
            [scenario_summary["weight"], scenario_summary["notes"]],
        )
    content = _replace_markdown_field(content, "Regressions found", backfill["findings"]["regressions"])
    content = _replace_markdown_field(content, "Expected limits hit", backfill["findings"]["expected_limits"])
    content = _replace_markdown_field(content, "Follow-up ticket(s)", backfill["findings"]["follow_up"])
    summary_path.write_text(content, encoding="utf-8")
    return backfill


def _shadow_read_config_path(report_dir: str, config_path: str = "") -> Path:
    if config_path.strip():
        return Path(config_path)
    return Path(report_dir) / "shadow-read-scenarios.json"


def _dual_write_config_path(report_dir: str, config_path: str = "") -> Path:
    if config_path.strip():
        return Path(config_path)
    return Path(report_dir) / "dual-write-scenarios.json"


def _build_shadow_read_config_template() -> dict[str, Any]:
    return {
        "owner": "<assign owner>",
        "scope": "account dashboard/profile, notification list/push-device, trade info",
        "primary_label": "legacy",
        "shadow_label": "python",
        "notes": "Fill exact primary/shadow URLs before running. Traffic mirroring or routing flags remain deployment-owned.",
        "scenarios": [
            {
                "name": "account-dashboard",
                "scope": "account",
                "method": "GET",
                "primary_url": "<set legacy account dashboard url>",
                "shadow_url": "${SHADOW_READ_SHADOW_BASE_URL}/v1/account/dashboard",
                "headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "ignore_json_paths": [],
            },
            {
                "name": "account-profile",
                "scope": "account",
                "method": "GET",
                "primary_url": "<set legacy account profile url>",
                "shadow_url": "${SHADOW_READ_SHADOW_BASE_URL}/v1/account/profile",
                "headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "ignore_json_paths": [],
            },
            {
                "name": "notifications-list",
                "scope": "notifications",
                "method": "GET",
                "primary_url": "<set legacy notifications list url>",
                "shadow_url": "${SHADOW_READ_SHADOW_BASE_URL}/v1/notifications",
                "headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "params": {"limit": 20},
                "ignore_json_paths": [],
            },
            {
                "name": "push-devices",
                "scope": "notifications",
                "method": "GET",
                "primary_url": "<set legacy push devices url>",
                "shadow_url": "${SHADOW_READ_SHADOW_BASE_URL}/v1/notifications/push-devices",
                "headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "ignore_json_paths": [],
            },
            {
                "name": "trade-info",
                "scope": "trades",
                "method": "GET",
                "primary_url": "<set legacy trade app-info url>",
                "shadow_url": "${SHADOW_READ_SHADOW_BASE_URL}/v1/trades/${LOAD_TEST_TRADE_ID}/app-info",
                "headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "ignore_json_paths": [],
            },
        ],
    }


def _build_dual_write_config_template() -> dict[str, Any]:
    return {
        "owner": "<assign owner>",
        "scope": "subscription state, notification receipt/ack, trade confirm/ignore/adjust, TradingAgents submit/terminal",
        "containment_decision": "<fill after review>",
        "primary_label": "legacy",
        "shadow_label": "python",
        "notes": "Writes are destructive unless you use disposable fixtures. This tool refuses to run without DUAL_WRITE_ALLOW_MUTATIONS=true.",
        "scenarios": [
            {
                "name": "subscription-start",
                "scope": "subscription",
                "write_method": "POST",
                "primary_write_url": "<set primary subscription write url>",
                "primary_write_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "primary_write_json": {
                    "allow_empty_portfolio": True,
                    "account": {"total_capital": 100000, "currency": "USD"},
                    "watchlist": [{"symbol": "AAPL", "min_score": 70, "notify": True}],
                },
                "primary_verify_url": "<set primary subscription read url>",
                "shadow_verify_url": "${DUAL_WRITE_SHADOW_BASE_URL}/v1/account/profile",
                "verify_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "ignore_json_paths": [],
                "containment_decision": "<fill after review>",
            },
            {
                "name": "notification-ack",
                "scope": "notifications",
                "write_method": "PUT",
                "primary_write_url": "<set primary notification ack url>",
                "primary_write_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "primary_verify_url": "<set primary notification readback url>",
                "shadow_verify_url": "${DUAL_WRITE_SHADOW_BASE_URL}/v1/notifications",
                "verify_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "ignore_json_paths": [],
                "containment_decision": "<fill after review>",
            },
            {
                "name": "trade-app-confirm",
                "scope": "trades",
                "write_method": "POST",
                "primary_write_url": "<set primary trade app-confirm url>",
                "primary_write_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "primary_verify_url": "<set primary trade readback url>",
                "shadow_verify_url": "${DUAL_WRITE_SHADOW_BASE_URL}/v1/trades/${LOAD_TEST_TRADE_ID}/app-info",
                "verify_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "ignore_json_paths": [],
                "containment_decision": "<fill after review>",
            },
            {
                "name": "trade-app-ignore",
                "scope": "trades",
                "write_method": "POST",
                "primary_write_url": "<set primary trade app-ignore url>",
                "primary_write_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "primary_verify_url": "<set primary trade readback url>",
                "shadow_verify_url": "${DUAL_WRITE_SHADOW_BASE_URL}/v1/trades/${LOAD_TEST_TRADE_ID}/app-info",
                "verify_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "ignore_json_paths": [],
                "containment_decision": "<fill after review>",
            },
            {
                "name": "trade-app-adjust",
                "scope": "trades",
                "write_method": "POST",
                "primary_write_url": "<set primary trade app-adjust url>",
                "primary_write_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "primary_write_json": {"actual_shares": 12, "actual_price": 101.5},
                "primary_verify_url": "<set primary trade readback url>",
                "shadow_verify_url": "${DUAL_WRITE_SHADOW_BASE_URL}/v1/trades/${LOAD_TEST_TRADE_ID}/app-info",
                "verify_headers": {"Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"},
                "ignore_json_paths": [],
                "containment_decision": "<fill after review>",
            },
            {
                "name": "tradingagents-submit",
                "scope": "tradingagents",
                "write_method": "POST",
                "primary_write_url": "<set primary TradingAgents submit url>",
                "primary_write_json": {
                    "request_id": "${DUAL_WRITE_TRADINGAGENTS_REQUEST_ID}",
                    "ticker": "AAPL",
                    "analysis_date": "2026-04-06T00:00:00Z",
                    "selected_analysts": ["fundamental", "sentiment"],
                    "trigger_type": "manual",
                    "trigger_context": {"source": "dual-write-rehearsal"},
                },
                "primary_verify_url": "<set primary TradingAgents analysis read url>",
                "shadow_verify_url": "${ADMIN_RUNTIME_URL}/v1/admin/tradingagents/analyses/${DUAL_WRITE_TRADINGAGENTS_REQUEST_ID}",
                "verify_headers": {"Authorization": "Bearer ${ADMIN_RUNTIME_TOKEN}"},
                "settle_seconds": 5,
                "ignore_json_paths": [],
                "containment_decision": "<fill after review>",
            },
            {
                "name": "tradingagents-terminal",
                "scope": "tradingagents",
                "write_method": "POST",
                "primary_write_url": "<set primary TradingAgents terminal webhook url>",
                "primary_write_headers": {"X-Webhook-Signature": "${DUAL_WRITE_WEBHOOK_SIGNATURE}"},
                "primary_write_json": {
                    "request_id": "${DUAL_WRITE_TRADINGAGENTS_REQUEST_ID}",
                    "job_id": "${DUAL_WRITE_TRADINGAGENTS_JOB_ID}",
                    "status": "completed",
                    "final_action": "hold",
                    "decision_summary": "dual-write terminal rehearsal",
                    "result_payload": {"source": "dual-write-rehearsal"},
                    "timestamp": "2026-04-06T00:05:00Z",
                },
                "primary_verify_url": "<set primary TradingAgents analysis read url>",
                "shadow_verify_url": "${ADMIN_RUNTIME_URL}/v1/admin/tradingagents/analyses/${DUAL_WRITE_TRADINGAGENTS_REQUEST_ID}",
                "verify_headers": {"Authorization": "Bearer ${ADMIN_RUNTIME_TOKEN}"},
                "settle_seconds": 5,
                "ignore_json_paths": [],
                "containment_decision": "<fill after review>",
            },
        ],
    }


def bootstrap_shadow_read_config(report_dir: str, config_path: str = "") -> tuple[Path, bool]:
    resolved_path = _shadow_read_config_path(report_dir, config_path)
    created = _write_json_if_missing(resolved_path, _build_shadow_read_config_template())
    return resolved_path, created


def bootstrap_dual_write_config(report_dir: str, config_path: str = "") -> tuple[Path, bool]:
    resolved_path = _dual_write_config_path(report_dir, config_path)
    created = _write_json_if_missing(resolved_path, _build_dual_write_config_template())
    return resolved_path, created


def _resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            env_key = match.group(1)
            env_value = os.getenv(env_key)
            if env_value is None:
                raise ValueError(
                    f"Missing environment variable for shadow read config placeholder: {env_key}"
                )
            return env_value

        return ENV_PLACEHOLDER_PATTERN.sub(replace, value)

    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]

    if isinstance(value, dict):
        return {str(key): _resolve_env_placeholders(item) for key, item in value.items()}

    return value


def _merge_mapping(base: Any, override: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in (base or {}, override or {}):
        if not isinstance(source, dict):
            raise ValueError("Shadow read scenario mappings must be JSON objects")
        for key, value in source.items():
            merged[str(key)] = value
    return merged


def _validate_http_url(url: str, *, scenario_name: str, field_name: str) -> str:
    normalized = url.strip()
    if "${" in normalized:
        raise ValueError(
            f"Shadow read scenario '{scenario_name}' has unresolved placeholder in {field_name}: {normalized}"
        )
    if not normalized.startswith(("http://", "https://")):
        raise ValueError(
            f"Shadow read scenario '{scenario_name}' requires an absolute http(s) {field_name}: {normalized}"
        )
    return normalized


def _load_shadow_read_config(
    *,
    report_dir: str,
    config_path: str,
) -> tuple[Path, dict[str, str], list[ShadowReadScenario]]:
    resolved_path = _shadow_read_config_path(report_dir, config_path)
    if not resolved_path.exists():
        path, _ = bootstrap_shadow_read_config(report_dir, str(resolved_path))
        raise FileNotFoundError(
            f"Shadow read config not found. A template was created at {path}; fill the URLs and rerun."
        )

    config_payload = _resolve_env_placeholders(json.loads(resolved_path.read_text(encoding="utf-8")))
    scenarios_payload = config_payload.get("scenarios") or []
    if not isinstance(scenarios_payload, list) or not scenarios_payload:
        raise ValueError(f"Shadow read config has no scenarios: {resolved_path}")

    scenarios: list[ShadowReadScenario] = []
    for entry in scenarios_payload:
        if not isinstance(entry, dict):
            raise ValueError("Each shadow read scenario must be a JSON object")

        name = str(entry.get("name") or "").strip()
        if not name:
            raise ValueError("Shadow read scenario is missing 'name'")

        scope = str(entry.get("scope") or "general").strip() or "general"
        method = str(entry.get("method") or "GET").strip().upper() or "GET"
        primary_url = _validate_http_url(
            str(entry.get("primary_url") or ""),
            scenario_name=name,
            field_name="primary_url",
        )
        shadow_url = _validate_http_url(
            str(entry.get("shadow_url") or ""),
            scenario_name=name,
            field_name="shadow_url",
        )

        common_headers = _merge_mapping(entry.get("headers"), None)
        common_params = _merge_mapping(entry.get("params"), None)
        common_json = entry.get("json")
        ignore_json_paths = tuple(str(path) for path in entry.get("ignore_json_paths") or [])

        scenarios.append(
            ShadowReadScenario(
                name=name,
                scope=scope,
                method=method,
                primary_url=primary_url,
                shadow_url=shadow_url,
                primary_headers={
                    key: str(value)
                    for key, value in _merge_mapping(common_headers, entry.get("primary_headers")).items()
                    if str(value).strip()
                },
                shadow_headers={
                    key: str(value)
                    for key, value in _merge_mapping(common_headers, entry.get("shadow_headers")).items()
                    if str(value).strip()
                },
                primary_params=_merge_mapping(common_params, entry.get("primary_params")),
                shadow_params=_merge_mapping(common_params, entry.get("shadow_params")),
                primary_json=entry.get("primary_json", common_json),
                shadow_json=entry.get("shadow_json", common_json),
                ignore_json_paths=ignore_json_paths,
            )
        )

    metadata = {
        "owner": str(config_payload.get("owner") or "").strip(),
        "scope": str(config_payload.get("scope") or "").strip(),
        "primary_label": str(config_payload.get("primary_label") or "").strip(),
        "shadow_label": str(config_payload.get("shadow_label") or "").strip(),
    }
    return resolved_path, metadata, scenarios


def _parse_response_payload(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        try:
            return response.json()
        except ValueError:
            return response.text
    return response.text


def _execute_shadow_read_request(
    client: httpx.Client,
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any],
    json_payload: Any | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = client.request(
            method,
            url,
            headers=headers or None,
            params=params or None,
            json=json_payload,
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "content_type": response.headers.get("content-type", ""),
            "payload": _parse_response_payload(response),
            "error": "",
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status_code": None,
            "latency_ms": latency_ms,
            "content_type": "",
            "payload": None,
            "error": str(exc),
        }


def _normalize_payload(payload: Any, ignore_paths: set[str], path: str = "$") -> Any:
    if path in ignore_paths:
        return IGNORED_PAYLOAD

    if isinstance(payload, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(payload):
            child_path = f"$.{key}" if path == "$" else f"{path}.{key}"
            child_value = _normalize_payload(payload[key], ignore_paths, child_path)
            if child_value is not IGNORED_PAYLOAD:
                normalized[key] = child_value
        return normalized

    if isinstance(payload, list):
        normalized_list: list[Any] = []
        for index, item in enumerate(payload):
            child_path = f"{path}[{index}]"
            child_value = _normalize_payload(item, ignore_paths, child_path)
            if child_value is not IGNORED_PAYLOAD:
                normalized_list.append(child_value)
        return normalized_list

    return payload


def _payload_preview(payload: Any, *, error: str = "", limit: int = 220) -> str:
    if error:
        preview = error
    elif isinstance(payload, str):
        preview = payload
    else:
        preview = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    preview = preview.replace("\n", " ").strip()
    if len(preview) <= limit:
        return preview
    return preview[: limit - 3] + "..."


def _compare_shadow_read_pair(
    primary: dict[str, Any],
    shadow: dict[str, Any],
    *,
    ignore_json_paths: tuple[str, ...],
) -> tuple[str, str, str]:
    if primary.get("error") or shadow.get("error"):
        return (
            "request_error",
            _payload_preview(primary.get("payload"), error=str(primary.get("error") or "")),
            _payload_preview(shadow.get("payload"), error=str(shadow.get("error") or "")),
        )

    if primary.get("status_code") != shadow.get("status_code"):
        return (
            "status_mismatch",
            _payload_preview(primary.get("payload")),
            _payload_preview(shadow.get("payload")),
        )

    normalized_primary = _normalize_payload(primary.get("payload"), set(ignore_json_paths))
    normalized_shadow = _normalize_payload(shadow.get("payload"), set(ignore_json_paths))
    if normalized_primary != normalized_shadow:
        return (
            "payload_mismatch",
            _payload_preview(normalized_primary),
            _payload_preview(normalized_shadow),
        )

    return "", "", ""


def _execute_shadow_read_pair(
    scenario: ShadowReadScenario,
    timeout_seconds: float,
) -> dict[str, Any]:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        primary = _execute_shadow_read_request(
            client,
            method=scenario.method,
            url=scenario.primary_url,
            headers=scenario.primary_headers,
            params=scenario.primary_params,
            json_payload=scenario.primary_json,
        )
        shadow = _execute_shadow_read_request(
            client,
            method=scenario.method,
            url=scenario.shadow_url,
            headers=scenario.shadow_headers,
            params=scenario.shadow_params,
            json_payload=scenario.shadow_json,
        )

    mismatch_reason, primary_preview, shadow_preview = _compare_shadow_read_pair(
        primary,
        shadow,
        ignore_json_paths=scenario.ignore_json_paths,
    )
    return {
        "scenario": scenario.name,
        "scope": scenario.scope,
        "primary": primary,
        "shadow": shadow,
        "request_error": mismatch_reason == "request_error",
        "status_mismatch": mismatch_reason == "status_mismatch",
        "payload_mismatch": mismatch_reason == "payload_mismatch",
        "mismatch_reason": mismatch_reason,
        "primary_preview": primary_preview,
        "shadow_preview": shadow_preview,
    }


def _shadow_read_iterations(duration_seconds: float, interval_seconds: float) -> int:
    if duration_seconds <= 0:
        return 1
    if interval_seconds <= 0:
        return 1
    return max(1, int(math.ceil(duration_seconds / interval_seconds)))


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, int(math.ceil(len(sorted_values) * percentile / 100.0)) - 1))
    return sorted_values[index]


def _format_metric(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _render_shadow_read_summary_markdown(
    *,
    report_dir: Path,
    config_path: Path,
    scope_label: str,
    owner: str,
    primary_label: str,
    shadow_label: str,
    duration_seconds: float,
    interval_seconds: float,
    iterations: int,
    started_at: str,
    ended_at: str,
    scenario_summaries: list[dict[str, Any]],
    mismatches: list[dict[str, Any]],
) -> str:
    lines = [
        "# Shadow Read Summary",
        "",
        f"- Scope: {scope_label}",
        f"- Sample window: {iterations} samples over {int(duration_seconds)}s at {int(interval_seconds)}s intervals",
        f"- Started at: {started_at}",
        f"- Ended at: {ended_at}",
        f"- Owner: {owner}",
        f"- Config path: {config_path}",
        f"- Primary label: {primary_label}",
        f"- Shadow label: {shadow_label}",
        f"- Total scenarios: {len(scenario_summaries)}",
        f"- Total mismatches: {len(mismatches)}",
        "",
        "## Scenario Results",
        "",
        f"| Scenario | Scope | Samples | Status mismatches | Payload mismatches | {primary_label} P95 ms | {shadow_label} P95 ms | Mean delta ms |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for item in scenario_summaries:
        lines.append(
            "| {name} | {scope} | {samples} | {status_mismatches} | {payload_mismatches} | {primary_p95} | {shadow_p95} | {delta_mean} |".format(
                name=item["name"],
                scope=item["scope"],
                samples=item["samples"],
                status_mismatches=item["status_mismatches"],
                payload_mismatches=item["payload_mismatches"],
                primary_p95=_format_metric(item["primary_p95_ms"]),
                shadow_p95=_format_metric(item["shadow_p95_ms"]),
                delta_mean=_format_metric(item["mean_latency_delta_ms"]),
            )
        )

    lines.extend(["", "## Mismatch Samples", ""])
    if not mismatches:
        lines.append("- None observed.")
    else:
        for mismatch in mismatches[:10]:
            lines.append(
                "- {scenario} iteration {iteration} at {sampled_at}: {reason}; {primary_label}={primary_preview}; {shadow_label}={shadow_preview}".format(
                    scenario=mismatch["scenario"],
                    iteration=mismatch["iteration"],
                    sampled_at=mismatch["sampled_at"],
                    reason=mismatch["mismatch_reason"],
                    primary_label=primary_label,
                    primary_preview=mismatch["primary_preview"],
                    shadow_label=shadow_label,
                    shadow_preview=mismatch["shadow_preview"],
                )
            )

    return "\n".join(lines) + "\n"


def capture_shadow_read_summary(
    *,
    report_dir: str,
    config_path: str = "",
    duration_seconds: float = 900.0,
    interval_seconds: float = 30.0,
    timeout_seconds: float = 10.0,
    owner: str = "",
    scope_label: str = "",
    primary_label: str = "",
    shadow_label: str = "",
    iterations: int | None = None,
    execute_pair: Any | None = None,
    sleep_fn: Any | None = None,
) -> dict[str, Any]:
    report_dir_path = Path(report_dir)
    report_dir_path.mkdir(parents=True, exist_ok=True)
    (report_dir_path / "evidence").mkdir(exist_ok=True)

    resolved_config_path, metadata, scenarios = _load_shadow_read_config(
        report_dir=report_dir,
        config_path=config_path,
    )
    resolved_owner = owner.strip() or metadata.get("owner") or "<assign owner>"
    resolved_scope = scope_label.strip() or metadata.get("scope") or ", ".join(
        dict.fromkeys(scenario.scope for scenario in scenarios)
    )
    resolved_primary_label = primary_label.strip() or metadata.get("primary_label") or "primary"
    resolved_shadow_label = shadow_label.strip() or metadata.get("shadow_label") or "shadow"
    resolved_iterations = iterations or _shadow_read_iterations(duration_seconds, interval_seconds)
    pair_executor = execute_pair or _execute_shadow_read_pair
    resolved_sleep = sleep_fn or time.sleep

    started_at = _utc_timestamp()
    results: list[dict[str, Any]] = []
    for iteration in range(1, resolved_iterations + 1):
        sampled_at = _utc_timestamp()
        for scenario in scenarios:
            pair_result = pair_executor(scenario, timeout_seconds)
            pair_result["iteration"] = iteration
            pair_result["sampled_at"] = sampled_at
            results.append(pair_result)
        if iteration < resolved_iterations and interval_seconds > 0:
            resolved_sleep(interval_seconds)
    ended_at = _utc_timestamp()

    scenario_summaries: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_results = [item for item in results if item["scenario"] == scenario.name]
        primary_latencies = [float(item["primary"]["latency_ms"]) for item in scenario_results]
        shadow_latencies = [float(item["shadow"]["latency_ms"]) for item in scenario_results]
        latency_deltas = [
            float(item["shadow"]["latency_ms"]) - float(item["primary"]["latency_ms"])
            for item in scenario_results
        ]
        scenario_summaries.append(
            {
                "name": scenario.name,
                "scope": scenario.scope,
                "samples": len(scenario_results),
                "status_mismatches": sum(1 for item in scenario_results if item["status_mismatch"]),
                "payload_mismatches": sum(1 for item in scenario_results if item["payload_mismatch"]),
                "request_errors": sum(1 for item in scenario_results if item["request_error"]),
                "primary_p50_ms": _percentile(primary_latencies, 50),
                "primary_p95_ms": _percentile(primary_latencies, 95),
                "shadow_p50_ms": _percentile(shadow_latencies, 50),
                "shadow_p95_ms": _percentile(shadow_latencies, 95),
                "mean_latency_delta_ms": (
                    round(sum(latency_deltas) / len(latency_deltas), 2) if latency_deltas else None
                ),
            }
        )
        mismatches.extend(
            item
            for item in scenario_results
            if item["request_error"] or item["status_mismatch"] or item["payload_mismatch"]
        )

    summary = {
        "kind": "shadow-read",
        "report_dir": str(report_dir_path),
        "config_path": str(resolved_config_path),
        "owner": resolved_owner,
        "scope": resolved_scope,
        "primary_label": resolved_primary_label,
        "shadow_label": resolved_shadow_label,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds,
        "interval_seconds": interval_seconds,
        "iterations": resolved_iterations,
        "scenario_summaries": scenario_summaries,
        "mismatches": mismatches,
        "results": results,
        "artifacts": {
            "summary_path": str(report_dir_path / "shadow-read-summary.md"),
            "evidence_path": str(report_dir_path / "evidence/shadow-read-results.json"),
        },
    }
    _write_json(report_dir_path / "evidence/shadow-read-results.json", summary)
    (report_dir_path / "shadow-read-summary.md").write_text(
        _render_shadow_read_summary_markdown(
            report_dir=report_dir_path,
            config_path=resolved_config_path,
            scope_label=resolved_scope,
            owner=resolved_owner,
            primary_label=resolved_primary_label,
            shadow_label=resolved_shadow_label,
            duration_seconds=duration_seconds,
            interval_seconds=interval_seconds,
            iterations=resolved_iterations,
            started_at=started_at,
            ended_at=ended_at,
            scenario_summaries=scenario_summaries,
            mismatches=mismatches,
        ),
        encoding="utf-8",
    )
    return summary


def _validate_optional_http_url(url: str, *, scenario_name: str, field_name: str) -> str | None:
    normalized = url.strip()
    if not normalized:
        return None
    return _validate_http_url(normalized, scenario_name=scenario_name, field_name=field_name)


def _load_dual_write_config(
    *,
    report_dir: str,
    config_path: str,
) -> tuple[Path, dict[str, str], list[DualWriteScenario]]:
    resolved_path = _dual_write_config_path(report_dir, config_path)
    if not resolved_path.exists():
        path, _ = bootstrap_dual_write_config(report_dir, str(resolved_path))
        raise FileNotFoundError(
            f"Dual-write config not found. A template was created at {path}; fill the URLs and rerun."
        )

    config_payload = _resolve_env_placeholders(json.loads(resolved_path.read_text(encoding="utf-8")))
    scenarios_payload = config_payload.get("scenarios") or []
    if not isinstance(scenarios_payload, list) or not scenarios_payload:
        raise ValueError(f"Dual-write config has no scenarios: {resolved_path}")

    scenarios: list[DualWriteScenario] = []
    for entry in scenarios_payload:
        if not isinstance(entry, dict):
            raise ValueError("Each dual-write scenario must be a JSON object")

        name = str(entry.get("name") or "").strip()
        if not name:
            raise ValueError("Dual-write scenario is missing 'name'")

        scope = str(entry.get("scope") or "general").strip() or "general"
        write_method = str(entry.get("write_method") or entry.get("method") or "POST").strip().upper()
        verify_method = str(entry.get("verify_method") or "GET").strip().upper()

        write_headers = _merge_mapping(entry.get("write_headers"), entry.get("headers"))
        write_params = _merge_mapping(entry.get("write_params"), entry.get("params"))
        verify_headers = _merge_mapping(entry.get("verify_headers"), None)
        verify_params = _merge_mapping(entry.get("verify_params"), None)
        write_json = entry.get("write_json", entry.get("json"))
        verify_json = entry.get("verify_json")
        ignore_json_paths = tuple(str(path) for path in entry.get("ignore_json_paths") or [])

        primary_write_url = _validate_http_url(
            str(entry.get("primary_write_url") or ""),
            scenario_name=name,
            field_name="primary_write_url",
        )
        primary_verify_url = _validate_http_url(
            str(entry.get("primary_verify_url") or ""),
            scenario_name=name,
            field_name="primary_verify_url",
        )
        shadow_verify_url = _validate_http_url(
            str(entry.get("shadow_verify_url") or ""),
            scenario_name=name,
            field_name="shadow_verify_url",
        )
        shadow_write_url = _validate_optional_http_url(
            str(entry.get("shadow_write_url") or ""),
            scenario_name=name,
            field_name="shadow_write_url",
        )

        scenarios.append(
            DualWriteScenario(
                name=name,
                scope=scope,
                write_method=write_method,
                primary_write_url=primary_write_url,
                shadow_write_url=shadow_write_url,
                primary_write_headers={
                    key: str(value)
                    for key, value in _merge_mapping(write_headers, entry.get("primary_write_headers")).items()
                    if str(value).strip()
                },
                shadow_write_headers={
                    key: str(value)
                    for key, value in _merge_mapping(write_headers, entry.get("shadow_write_headers")).items()
                    if str(value).strip()
                },
                primary_write_params=_merge_mapping(write_params, entry.get("primary_write_params")),
                shadow_write_params=_merge_mapping(write_params, entry.get("shadow_write_params")),
                primary_write_json=entry.get("primary_write_json", write_json),
                shadow_write_json=entry.get("shadow_write_json", write_json),
                verify_method=verify_method,
                primary_verify_url=primary_verify_url,
                shadow_verify_url=shadow_verify_url,
                primary_verify_headers={
                    key: str(value)
                    for key, value in _merge_mapping(verify_headers, entry.get("primary_verify_headers")).items()
                    if str(value).strip()
                },
                shadow_verify_headers={
                    key: str(value)
                    for key, value in _merge_mapping(verify_headers, entry.get("shadow_verify_headers")).items()
                    if str(value).strip()
                },
                primary_verify_params=_merge_mapping(verify_params, entry.get("primary_verify_params")),
                shadow_verify_params=_merge_mapping(verify_params, entry.get("shadow_verify_params")),
                primary_verify_json=entry.get("primary_verify_json", verify_json),
                shadow_verify_json=entry.get("shadow_verify_json", verify_json),
                ignore_json_paths=ignore_json_paths,
                settle_seconds=float(entry.get("settle_seconds") or 0.0),
                containment_decision=str(entry.get("containment_decision") or "").strip(),
            )
        )

    metadata = {
        "owner": str(config_payload.get("owner") or "").strip(),
        "scope": str(config_payload.get("scope") or "").strip(),
        "containment_decision": str(config_payload.get("containment_decision") or "").strip(),
        "primary_label": str(config_payload.get("primary_label") or "").strip(),
        "shadow_label": str(config_payload.get("shadow_label") or "").strip(),
    }
    return resolved_path, metadata, scenarios


def _render_dual_write_summary_markdown(
    *,
    config_path: Path,
    owner: str,
    scope_label: str,
    containment_decision: str,
    primary_label: str,
    shadow_label: str,
    scenario_summaries: list[dict[str, Any]],
    mismatches: list[dict[str, Any]],
    started_at: str,
    ended_at: str,
    mutation_mode: str,
) -> str:
    lines = [
        "# Dual-Write Summary",
        "",
        f"- Scope: {scope_label}",
        f"- Started at: {started_at}",
        f"- Ended at: {ended_at}",
        f"- Owner: {owner}",
        f"- Containment decision: {containment_decision}",
        f"- Config path: {config_path}",
        f"- Mutation mode: {mutation_mode}",
        f"- Primary label: {primary_label}",
        f"- Shadow label: {shadow_label}",
        f"- Total scenarios: {len(scenario_summaries)}",
        f"- Total mismatches: {len(mismatches)}",
        "",
        "## Scenario Results",
        "",
        f"| Scenario | Scope | {primary_label} write | {shadow_label} write | {primary_label} verify | {shadow_label} verify | Mismatch | Containment decision |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for item in scenario_summaries:
        lines.append(
            "| {name} | {scope} | {primary_write_status} | {shadow_write_status} | {primary_verify_status} | {shadow_verify_status} | {mismatch_reason} | {containment_decision} |".format(
                name=item["name"],
                scope=item["scope"],
                primary_write_status=item["primary_write_status"],
                shadow_write_status=item["shadow_write_status"],
                primary_verify_status=item["primary_verify_status"],
                shadow_verify_status=item["shadow_verify_status"],
                mismatch_reason=item["mismatch_reason"] or "-",
                containment_decision=item["containment_decision"],
            )
        )

    lines.extend(["", "## Mismatch Samples", ""])
    if not mismatches:
        lines.append("- None observed.")
    else:
        for mismatch in mismatches[:10]:
            lines.append(
                "- {scenario} at {sampled_at}: {reason}; {primary_label}={primary_preview}; {shadow_label}={shadow_preview}; containment={containment_decision}".format(
                    scenario=mismatch["scenario"],
                    sampled_at=mismatch["sampled_at"],
                    reason=mismatch["mismatch_reason"],
                    primary_label=primary_label,
                    primary_preview=mismatch["primary_preview"],
                    shadow_label=shadow_label,
                    shadow_preview=mismatch["shadow_preview"],
                    containment_decision=mismatch["containment_decision"],
                )
            )
    return "\n".join(lines) + "\n"


def capture_dual_write_summary(
    *,
    report_dir: str,
    config_path: str = "",
    timeout_seconds: float = 10.0,
    owner: str = "",
    scope_label: str = "",
    containment_decision: str = "",
    primary_label: str = "",
    shadow_label: str = "",
    allow_mutations: bool = False,
    execute_request: Any | None = None,
    sleep_fn: Any | None = None,
) -> dict[str, Any]:
    resolved_allow_mutations = allow_mutations or _is_truthy(os.getenv("DUAL_WRITE_ALLOW_MUTATIONS"))
    if not resolved_allow_mutations:
        raise PermissionError(
            "Dual-write capture requires explicit mutation approval. Set DUAL_WRITE_ALLOW_MUTATIONS=true or pass --allow-mutations."
        )

    report_dir_path = Path(report_dir)
    report_dir_path.mkdir(parents=True, exist_ok=True)
    (report_dir_path / "evidence").mkdir(exist_ok=True)

    resolved_config_path, metadata, scenarios = _load_dual_write_config(
        report_dir=report_dir,
        config_path=config_path,
    )
    resolved_owner = owner.strip() or metadata.get("owner") or "<assign owner>"
    resolved_scope = scope_label.strip() or metadata.get("scope") or ", ".join(
        dict.fromkeys(scenario.scope for scenario in scenarios)
    )
    resolved_containment = (
        containment_decision.strip() or metadata.get("containment_decision") or "<fill after review>"
    )
    resolved_primary_label = primary_label.strip() or metadata.get("primary_label") or "primary"
    resolved_shadow_label = shadow_label.strip() or metadata.get("shadow_label") or "shadow"
    request_executor = execute_request or _execute_shadow_read_request
    resolved_sleep = sleep_fn or time.sleep

    results: list[dict[str, Any]] = []
    started_at = _utc_timestamp()
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        for scenario in scenarios:
            primary_write = request_executor(
                client,
                method=scenario.write_method,
                url=scenario.primary_write_url,
                headers=scenario.primary_write_headers,
                params=scenario.primary_write_params,
                json_payload=scenario.primary_write_json,
            )
            shadow_write: dict[str, Any] | None = None
            if scenario.shadow_write_url:
                shadow_write = request_executor(
                    client,
                    method=scenario.write_method,
                    url=scenario.shadow_write_url,
                    headers=scenario.shadow_write_headers,
                    params=scenario.shadow_write_params,
                    json_payload=scenario.shadow_write_json,
                )

            if scenario.settle_seconds > 0:
                resolved_sleep(scenario.settle_seconds)

            primary_verify = request_executor(
                client,
                method=scenario.verify_method,
                url=scenario.primary_verify_url,
                headers=scenario.primary_verify_headers,
                params=scenario.primary_verify_params,
                json_payload=scenario.primary_verify_json,
            )
            shadow_verify = request_executor(
                client,
                method=scenario.verify_method,
                url=scenario.shadow_verify_url,
                headers=scenario.shadow_verify_headers,
                params=scenario.shadow_verify_params,
                json_payload=scenario.shadow_verify_json,
            )

            sampled_at = _utc_timestamp()
            write_status_mismatch = bool(
                shadow_write is not None
                and not primary_write.get("error")
                and not shadow_write.get("error")
                and primary_write.get("status_code") != shadow_write.get("status_code")
            )
            verify_mismatch_reason, primary_preview, shadow_preview = _compare_shadow_read_pair(
                primary_verify,
                shadow_verify,
                ignore_json_paths=scenario.ignore_json_paths,
            )

            mismatch_reason = ""
            if primary_write.get("error"):
                mismatch_reason = "primary_write_error"
                primary_preview = _payload_preview(
                    primary_write.get("payload"), error=str(primary_write.get("error") or "")
                )
                shadow_preview = _payload_preview(shadow_write.get("payload") if shadow_write else None)
            elif shadow_write is not None and shadow_write.get("error"):
                mismatch_reason = "shadow_write_error"
                primary_preview = _payload_preview(primary_write.get("payload"))
                shadow_preview = _payload_preview(
                    shadow_write.get("payload"), error=str(shadow_write.get("error") or "")
                )
            elif write_status_mismatch:
                mismatch_reason = "write_status_mismatch"
                primary_preview = _payload_preview(primary_write.get("payload"))
                shadow_preview = _payload_preview(shadow_write.get("payload") if shadow_write else None)
            else:
                mismatch_reason = verify_mismatch_reason

            results.append(
                {
                    "scenario": scenario.name,
                    "scope": scenario.scope,
                    "sampled_at": sampled_at,
                    "primary_write": primary_write,
                    "shadow_write": shadow_write,
                    "primary_verify": primary_verify,
                    "shadow_verify": shadow_verify,
                    "write_status_mismatch": write_status_mismatch,
                    "request_error": bool(primary_write.get("error") or (shadow_write or {}).get("error")),
                    "verify_status_mismatch": mismatch_reason == "status_mismatch",
                    "verify_payload_mismatch": mismatch_reason == "payload_mismatch",
                    "mismatch_reason": mismatch_reason,
                    "primary_preview": primary_preview,
                    "shadow_preview": shadow_preview,
                    "containment_decision": scenario.containment_decision or resolved_containment,
                }
            )
    ended_at = _utc_timestamp()

    scenario_summaries: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for item in results:
        scenario_summaries.append(
            {
                "name": item["scenario"],
                "scope": item["scope"],
                "primary_write_status": item["primary_write"].get("status_code") or item["primary_write"].get("error") or "-",
                "shadow_write_status": (
                    (item["shadow_write"] or {}).get("status_code")
                    or (item["shadow_write"] or {}).get("error")
                    or ("mirrored-by-deploy" if item["shadow_write"] is None else "-")
                ),
                "primary_verify_status": item["primary_verify"].get("status_code") or item["primary_verify"].get("error") or "-",
                "shadow_verify_status": item["shadow_verify"].get("status_code") or item["shadow_verify"].get("error") or "-",
                "mismatch_reason": item["mismatch_reason"],
                "containment_decision": item["containment_decision"],
            }
        )
        if item["mismatch_reason"]:
            mismatches.append(item)

    summary = {
        "kind": "dual-write",
        "report_dir": str(report_dir_path),
        "config_path": str(resolved_config_path),
        "owner": resolved_owner,
        "scope": resolved_scope,
        "containment_decision": resolved_containment,
        "primary_label": resolved_primary_label,
        "shadow_label": resolved_shadow_label,
        "started_at": started_at,
        "ended_at": ended_at,
        "allow_mutations": resolved_allow_mutations,
        "scenario_summaries": scenario_summaries,
        "mismatches": mismatches,
        "results": results,
        "artifacts": {
            "summary_path": str(report_dir_path / "dual-write-summary.md"),
            "evidence_path": str(report_dir_path / "evidence/dual-write-results.json"),
        },
    }
    _write_json(report_dir_path / "evidence/dual-write-results.json", summary)
    (report_dir_path / "dual-write-summary.md").write_text(
        _render_dual_write_summary_markdown(
            config_path=resolved_config_path,
            owner=resolved_owner,
            scope_label=resolved_scope,
            containment_decision=resolved_containment,
            primary_label=resolved_primary_label,
            shadow_label=resolved_shadow_label,
            scenario_summaries=scenario_summaries,
            mismatches=mismatches,
            started_at=started_at,
            ended_at=ended_at,
            mutation_mode="approved",
        ),
        encoding="utf-8",
    )
    return summary


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def _markdown_field_has_value(content: str, label: str) -> bool:
    target_prefix = f"- {label}:"
    for line in content.splitlines():
        if not line.startswith(target_prefix):
            continue
        value = line.split(":", 1)[1].strip()
        return bool(value) and not REVIEW_PLACEHOLDER_PATTERN.search(value)
    return False


def _markdown_table_row_populated(content: str, row_name: str, *, min_nonempty_cells: int = 1) -> bool:
    prefix = f"| {row_name} |"
    for line in content.splitlines():
        if not line.startswith(prefix):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")][1:]
        return sum(1 for cell in cells if cell) >= min_nonempty_cells
    return False


def _markdown_review_complete(
    path: Path,
    *,
    required_fields: tuple[str, ...] = (),
    required_rows: tuple[str, ...] = (),
    required_markers: tuple[str, ...] = (),
) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "reviewed": False, "path": str(path), "missing": ["file"]}

    content = path.read_text(encoding="utf-8")
    missing: list[str] = []
    if not content.strip():
        missing.append("nonempty")
    if REVIEW_PLACEHOLDER_PATTERN.search(content):
        missing.append("placeholders")
    for label in required_fields:
        if not _markdown_field_has_value(content, label):
            missing.append(f"field:{label}")
    for row in required_rows:
        if not _markdown_table_row_populated(content, row):
            missing.append(f"row:{row}")
    for marker in required_markers:
        if marker not in content:
            missing.append(f"marker:{marker}")

    return {
        "exists": True,
        "reviewed": not missing,
        "path": str(path),
        "missing": missing,
    }


def capture_rollback_verification(
    *,
    report_dir: str,
    backup_dir: str,
    trigger_used: str = "",
    smoke_suite_rerun: str = "",
    backlog_reconciliation: str = "",
    final_decision: str = "",
    restore_command: str = "",
    public_health_url: str = "",
    admin_runtime_metrics_url: str = "",
    admin_runtime_alerts_url: str = "",
    admin_token: str = "",
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    report_dir_path = Path(report_dir)
    report_dir_path.mkdir(parents=True, exist_ok=True)
    evidence_dir = report_dir_path / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    resolved_backup_dir = Path(backup_dir).expanduser().resolve()

    postgres_dump = _locate_backup_postgres_dump(resolved_backup_dir)
    minio_dir = resolved_backup_dir / "minio"
    compose_ps = resolved_backup_dir / "compose-ps.txt"
    if not postgres_dump.exists():
        raise FileNotFoundError(f"PostgreSQL dump not found in backup directory: {postgres_dump}")
    if not minio_dir.exists():
        raise FileNotFoundError(f"MinIO backup directory not found: {minio_dir}")

    headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else None
    http_checks: list[dict[str, Any]] = []
    if public_health_url:
        http_checks.append(
            _capture_http_payload(
                url=public_health_url,
                destination=evidence_dir / "rollback-public-health.json",
                timeout_seconds=timeout_seconds,
            )
        )
    if admin_runtime_metrics_url:
        http_checks.append(
            _capture_http_payload(
                url=admin_runtime_metrics_url,
                destination=evidence_dir / "rollback-admin-runtime-metrics.json",
                headers=headers,
                timeout_seconds=timeout_seconds,
            )
        )
    if admin_runtime_alerts_url:
        http_checks.append(
            _capture_http_payload(
                url=admin_runtime_alerts_url,
                destination=evidence_dir / "rollback-admin-runtime-alerts.json",
                headers=headers,
                timeout_seconds=timeout_seconds,
            )
        )

    summary = {
        "kind": "rollback-verification",
        "report_dir": str(report_dir_path),
        "backup_dir": str(resolved_backup_dir),
        "captured_at": _utc_timestamp(),
        "trigger_used": trigger_used.strip() or "make ops-restore-baseline BACKUP_DIR=<path>",
        "restore_command": restore_command.strip() or f"make ops-restore-baseline BACKUP_DIR={resolved_backup_dir}",
        "smoke_suite_rerun": smoke_suite_rerun.strip() or "auth,dashboard,notifications,scanner ingest,TradingAgents webhook",
        "backlog_reconciliation": backlog_reconciliation.strip() or "<record outcome>",
        "final_decision": final_decision.strip() or "<fill after review>",
        "backup_artifacts": {
            "postgres_dump": str(postgres_dump),
            "postgres_dump_bytes": postgres_dump.stat().st_size,
            "minio_dir": str(minio_dir),
            "minio_file_count": _count_files(minio_dir),
            "compose_ps": str(compose_ps) if compose_ps.exists() else None,
            "backup_readable": postgres_dump.stat().st_size > 0,
        },
        "http_checks": http_checks,
        "artifacts": {
            "summary_path": str(report_dir_path / "rollback-verification.md"),
            "evidence_path": str(evidence_dir / "rollback-verification.json"),
        },
    }

    markdown = "\n".join(
        [
            "# Rollback Verification",
            "",
            f"- Trigger used: {summary['trigger_used']}",
            f"- Backup dir: {resolved_backup_dir}",
            f"- PostgreSQL dump readable: yes ({summary['backup_artifacts']['postgres_dump_bytes']} bytes)",
            f"- MinIO mirror readable: yes ({summary['backup_artifacts']['minio_file_count']} files)",
            f"- Restore command: {summary['restore_command']}",
            f"- Smoke suite rerun: {summary['smoke_suite_rerun']}",
            f"- Backlog reconciliation: {summary['backlog_reconciliation']}",
            f"- Final decision: {summary['final_decision']}",
        ]
    ) + "\n"
    (report_dir_path / "rollback-verification.md").write_text(markdown, encoding="utf-8")
    _write_json(evidence_dir / "rollback-verification.json", summary)
    return summary


def validate_cutover_signoff(
    *,
    report_dir: str,
    load_report_dir: str,
    backup_dir: str = "",
    k8s_validation_summary: str = "",
    rollout_evidence_path: str = "",
) -> dict[str, Any]:
    report_dir_path = Path(report_dir)
    load_report_dir_path = Path(load_report_dir)
    evidence_dir = report_dir_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    load_summary = _markdown_review_complete(
        load_report_dir_path / "baseline-summary.md",
        required_fields=("QA sign-off", "Backend sign-off"),
        required_rows=("Total requests", "Error rate", "P95 latency"),
    )
    cutover_record = _markdown_review_complete(
        report_dir_path / "canary-rollback-rehearsal.md",
        required_fields=("Release SHA", "QA owner", "Backend owner", "On-call reviewer", "Approval status"),
        required_rows=("Shadow read", "Rollback drill", "Public API 5xx rate"),
    )
    shadow_read = _markdown_review_complete(
        report_dir_path / "shadow-read-summary.md",
        required_fields=("Owner",),
        required_markers=("Total scenarios:",),
    )
    dual_write = _markdown_review_complete(
        report_dir_path / "dual-write-summary.md",
        required_fields=("Owner", "Containment decision"),
        required_markers=("Total scenarios:",),
    )
    rollback_verification = _markdown_review_complete(
        report_dir_path / "rollback-verification.md",
        required_fields=("Trigger used", "Smoke suite rerun", "Final decision"),
    )
    openapi_diff = _markdown_review_complete(
        report_dir_path / "openapi" / "openapi-diff.md",
    )

    rollback_evidence_path = evidence_dir / "rollback-verification.json"
    backup_readable = False
    if rollback_evidence_path.exists():
        rollback_payload = json.loads(rollback_evidence_path.read_text(encoding="utf-8"))
        backup_readable = bool(
            rollback_payload.get("backup_artifacts", {}).get("backup_readable")
        )
    elif backup_dir:
        backup_readable = _locate_backup_postgres_dump(Path(backup_dir)).exists()

    resolved_k8s_summary = Path(k8s_validation_summary) if k8s_validation_summary.strip() else report_dir_path / "k8s" / "validation" / "summary.json"
    rollout_evidence = Path(rollout_evidence_path) if rollout_evidence_path.strip() else None
    if rollout_evidence and rollout_evidence.exists() and rollout_evidence.stat().st_size > 0:
        deployment_posture = "rollout_verified"
    elif resolved_k8s_summary.exists():
        deployment_posture = "handoff_baseline"
    else:
        deployment_posture = "compose_vm_baseline"

    checks = {
        "load_summary_reviewed": load_summary,
        "cutover_record_reviewed": cutover_record,
        "shadow_read_reviewed": shadow_read,
        "dual_write_reviewed": dual_write,
        "rollback_verification_reviewed": rollback_verification,
        "openapi_diff_reviewed": openapi_diff,
        "backup_readable_verified": {
            "exists": backup_readable,
            "reviewed": backup_readable,
            "path": str(rollback_evidence_path if rollback_evidence_path.exists() else backup_dir),
            "missing": [] if backup_readable else ["backup_readable"],
        },
        "k8s_validation_summary": {
            "exists": resolved_k8s_summary.exists(),
            "reviewed": resolved_k8s_summary.exists(),
            "path": str(resolved_k8s_summary),
            "missing": [] if resolved_k8s_summary.exists() else ["summary.json"],
        },
    }
    ready = all(
        checks[key]["reviewed"]
        for key in (
            "load_summary_reviewed",
            "cutover_record_reviewed",
            "shadow_read_reviewed",
            "dual_write_reviewed",
            "rollback_verification_reviewed",
            "openapi_diff_reviewed",
            "backup_readable_verified",
        )
    )
    summary = {
        "kind": "cutover-signoff",
        "report_dir": str(report_dir_path),
        "load_report_dir": str(load_report_dir_path),
        "deployment_posture": deployment_posture,
        "ready": ready,
        "checks": checks,
        "artifacts": {
            "summary_json": str(evidence_dir / "cutover-signoff-summary.json"),
            "summary_markdown": str(report_dir_path / "cutover-signoff-summary.md"),
        },
    }
    _write_json(evidence_dir / "cutover-signoff-summary.json", summary)
    markdown_lines = [
        "# Cutover Signoff Summary",
        "",
        f"- Ready for cutover: {'yes' if ready else 'no'}",
        f"- Deployment posture: {deployment_posture}",
        f"- Load summary reviewed: {'yes' if load_summary['reviewed'] else 'no'}",
        f"- Cutover record reviewed: {'yes' if cutover_record['reviewed'] else 'no'}",
        f"- Shadow read summary reviewed: {'yes' if shadow_read['reviewed'] else 'no'}",
        f"- Dual-write summary reviewed: {'yes' if dual_write['reviewed'] else 'no'}",
        f"- Rollback verification reviewed: {'yes' if rollback_verification['reviewed'] else 'no'}",
        f"- OpenAPI diff reviewed: {'yes' if openapi_diff['reviewed'] else 'no'}",
        f"- Backup readable verified: {'yes' if backup_readable else 'no'}",
        f"- K8s validation summary present: {'yes' if resolved_k8s_summary.exists() else 'no'}",
        "",
        "## Missing Checks",
        "",
    ]
    missing_items = []
    for name, details in checks.items():
        if details["reviewed"]:
            continue
        missing_items.append(f"- {name}: {', '.join(details['missing'])}")
    if not missing_items:
        markdown_lines.append("- None.")
    else:
        markdown_lines.extend(missing_items)
    (report_dir_path / "cutover-signoff-summary.md").write_text(
        "\n".join(markdown_lines) + "\n",
        encoding="utf-8",
    )
    return summary


def build_load_command(host: str, users: str, spawn_rate: str, duration: str) -> str:
    return " ".join(
        [
            f"LOAD_TEST_HOST={_display(host, '<set before run>')}",
            f"LOAD_USERS={_display(users, '5')}",
            f"LOAD_SPAWN_RATE={_display(spawn_rate, '1')}",
            f"LOAD_DURATION={_display(duration, '1m')}",
            "make load-baseline",
        ]
    )


def bootstrap_load_report(
    *,
    template_path: str,
    report_prefix: str,
    environment: str,
    release_sha: str,
    run_id: str,
    qa_owner: str,
    backend_owner: str,
    command: str,
    scenario_mix: str,
    host: str,
    users: str,
    spawn_rate: str,
    duration: str,
    disposable_fixtures: str,
) -> tuple[Path, bool]:
    report_prefix_path = Path(report_prefix)
    report_dir_path = report_prefix_path.parent
    report_dir_path.mkdir(parents=True, exist_ok=True)
    (report_dir_path / "screenshots").mkdir(exist_ok=True)
    (report_dir_path / "evidence").mkdir(exist_ok=True)
    summary_path = report_prefix_path.parent / "baseline-summary.md"
    if summary_path.exists():
        _write_json_if_missing(
            report_dir_path / "artifact-manifest.json",
            {
                "kind": "load-baseline",
                "environment": _display(environment, "staging"),
                "release_sha": _display(release_sha, "<fill before review>"),
                "run_id": _display(run_id, report_dir_path.name),
                "report_prefix": str(report_prefix_path),
                "summary_path": str(summary_path),
                "artifacts": {
                    "csv": f"{report_prefix}_stats.csv",
                    "html": f"{report_prefix}.html",
                    "screenshots_dir": str(report_dir_path / "screenshots"),
                    "evidence_dir": str(report_dir_path / "evidence"),
                },
            },
        )
        return summary_path, False

    template = Path(template_path).read_text(encoding="utf-8")

    content = template
    replacements = {
        "Environment": _display(environment, "staging"),
        "Release SHA": _display(release_sha, "<fill before review>"),
        "Run UTC timestamp": _display(run_id, "<set before run>"),
        "QA owner": _display(qa_owner, "<assign owner>"),
        "Backend owner": _display(backend_owner, "<assign owner>"),
        "Command": _display(command, build_load_command(host, users, spawn_rate, duration)),
        "Scenario mix": _display(scenario_mix, ", ".join(DEFAULT_LOAD_SCENARIOS)),
        "Host": _display(host, "<set before run>"),
        "Users": _display(users, "5"),
        "Spawn rate": _display(spawn_rate, "1"),
        "Duration": _display(duration, "1m"),
        "Disposable fixtures used": _display(disposable_fixtures, ", ".join(DEFAULT_LOAD_FIXTURES)),
        "CSV path": f"{report_prefix}_stats.csv",
        "HTML path": f"{report_prefix}.html",
        "Dashboard / screenshots": f"{report_prefix_path.parent}/screenshots/",
    }
    for label, value in replacements.items():
        content = _replace_markdown_field(content, label, value)

    _write_json_if_missing(
        report_dir_path / "artifact-manifest.json",
        {
            "kind": "load-baseline",
            "environment": _display(environment, "staging"),
            "release_sha": _display(release_sha, "<fill before review>"),
            "run_id": _display(run_id, report_dir_path.name),
            "report_prefix": str(report_prefix_path),
            "summary_path": str(summary_path),
            "artifacts": {
                "csv": f"{report_prefix}_stats.csv",
                "html": f"{report_prefix}.html",
                "screenshots_dir": str(report_dir_path / "screenshots"),
                "evidence_dir": str(report_dir_path / "evidence"),
            },
        },
    )

    return summary_path, _write_if_missing(summary_path, content)


def bootstrap_cutover_report(
    *,
    template_path: str,
    report_dir: str,
    environment: str,
    release_sha: str,
    run_id: str,
    qa_owner: str,
    backend_owner: str,
    on_call_reviewer: str,
    canary_percentage: str,
    feature_flags: str,
    migration_revision: str,
    rollback_target_version: str,
) -> tuple[Path, bool]:
    report_dir_path = Path(report_dir)
    report_dir_path.mkdir(parents=True, exist_ok=True)
    (report_dir_path / "screenshots").mkdir(exist_ok=True)
    (report_dir_path / "logs").mkdir(exist_ok=True)
    (report_dir_path / "evidence").mkdir(exist_ok=True)
    (report_dir_path / "openapi").mkdir(exist_ok=True)
    shadow_read_config_path, _ = bootstrap_shadow_read_config(report_dir)
    dual_write_config_path, _ = bootstrap_dual_write_config(report_dir)
    record_path = report_dir_path / "canary-rollback-rehearsal.md"
    if record_path.exists():
        _write_json_if_missing(
            report_dir_path / "artifact-manifest.json",
            {
                "kind": "cutover-rehearsal",
                "environment": _display(environment, "staging"),
                "release_sha": _display(release_sha, "<fill before rehearsal>"),
                "run_id": _display(run_id, report_dir_path.name),
                "record_path": str(record_path),
                "artifacts": {
                    "screenshots_dir": str(report_dir_path / "screenshots"),
                    "logs_dir": str(report_dir_path / "logs"),
                    "evidence_dir": str(report_dir_path / "evidence"),
                    "openapi_dir": str(report_dir_path / "openapi"),
                    "shadow_read_config": str(shadow_read_config_path),
                    "dual_write_config": str(dual_write_config_path),
                    "shadow_read_summary": str(report_dir_path / "shadow-read-summary.md"),
                    "dual_write_summary": str(report_dir_path / "dual-write-summary.md"),
                    "rollback_checks": str(report_dir_path / "rollback-verification.md"),
                },
            },
        )
        return record_path, False

    template = Path(template_path).read_text(encoding="utf-8")

    content = template
    replacements = {
        "Environment": _display(environment, "staging"),
        "Release SHA": _display(release_sha, "<fill before rehearsal>"),
        "Rehearsal UTC timestamp": _display(run_id, report_dir_path.name),
        "QA owner": _display(qa_owner, "<assign owner>"),
        "Backend owner": _display(backend_owner, "<assign owner>"),
        "On-call reviewer": _display(on_call_reviewer, "<assign reviewer>"),
        "Canary percentage": _display(canary_percentage, "<planned percentage>"),
        "Feature flags changed": _display(feature_flags, "<record changed flags>"),
        "Migration revision at start": _display(migration_revision, "<record alembic revision>"),
        "Rollback target version": _display(rollback_target_version, "<record stable version>"),
    }
    for label, value in replacements.items():
        content = _replace_markdown_field(content, label, value)

    _write_if_missing(
        report_dir_path / "shadow-read-summary.md",
        "# Shadow Read Summary\n\n- Scope:\n- Sample window:\n- Mismatches:\n- Owner:\n",
    )
    _write_if_missing(
        report_dir_path / "dual-write-summary.md",
        "# Dual-Write Summary\n\n- Scope:\n- Sample window:\n- Mismatches:\n- Containment decision:\n",
    )
    _write_if_missing(
        report_dir_path / "rollback-verification.md",
        "# Rollback Verification\n\n- Trigger used:\n- Smoke suite rerun:\n- Backlog reconciliation:\n- Final decision:\n",
    )
    _write_json_if_missing(
        report_dir_path / "artifact-manifest.json",
        {
            "kind": "cutover-rehearsal",
            "environment": _display(environment, "staging"),
            "release_sha": _display(release_sha, "<fill before rehearsal>"),
            "run_id": _display(run_id, report_dir_path.name),
            "record_path": str(record_path),
            "artifacts": {
                "screenshots_dir": str(report_dir_path / "screenshots"),
                "logs_dir": str(report_dir_path / "logs"),
                "evidence_dir": str(report_dir_path / "evidence"),
                "openapi_dir": str(report_dir_path / "openapi"),
                "shadow_read_config": str(shadow_read_config_path),
                "dual_write_config": str(dual_write_config_path),
                "shadow_read_summary": str(report_dir_path / "shadow-read-summary.md"),
                "dual_write_summary": str(report_dir_path / "dual-write-summary.md"),
                "rollback_checks": str(report_dir_path / "rollback-verification.md"),
            },
        },
    )

    return record_path, _write_if_missing(record_path, content)


def capture_load_evidence(
    *,
    report_prefix: str,
    public_health_url: str,
    public_metrics_url: str = "",
    public_metrics_token: str = "",
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    report_prefix_path = Path(report_prefix)
    report_dir_path = report_prefix_path.parent
    evidence_dir = report_dir_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    load_backfill = _backfill_load_summary(report_prefix)
    http_checks: list[dict[str, Any]] = []
    if public_health_url.strip():
        http_checks.append(
            _capture_http_evidence(
                url=public_health_url,
                destination=evidence_dir / "public-health.json",
                timeout_seconds=timeout_seconds,
            )
        )
    if public_metrics_url:
        metrics_headers = (
            {"Authorization": f"Bearer {public_metrics_token}"}
            if public_metrics_token
            else None
        )
        http_checks.append(
            _capture_http_evidence(
                url=public_metrics_url,
                destination=evidence_dir / "public-metrics.txt",
                headers=metrics_headers,
                timeout_seconds=timeout_seconds,
            )
        )

    summary = {
        "kind": "load-evidence",
        "captured_at": _display(os.getenv("LOAD_RUN_ID"), "manual"),
        "report_prefix": str(report_prefix_path),
        "http_checks": http_checks,
        "load_summary": load_backfill,
        "artifacts": {
            "csv_exists": Path(f"{report_prefix}_stats.csv").exists(),
            "html_exists": Path(f"{report_prefix}.html").exists(),
            "summary_exists": (report_dir_path / "baseline-summary.md").exists(),
        },
    }
    _write_json(evidence_dir / "load-evidence-summary.json", summary)
    return summary


def capture_cutover_evidence(
    *,
    report_dir: str,
    public_health_url: str,
    admin_runtime_metrics_url: str = "",
    admin_runtime_alerts_url: str = "",
    admin_token: str = "",
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    report_dir_path = Path(report_dir)
    evidence_dir = report_dir_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (report_dir_path / "openapi").mkdir(exist_ok=True)
    headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else None

    http_checks: list[dict[str, Any]] = []
    if public_health_url.strip():
        http_checks.append(
            _capture_http_evidence(
                url=public_health_url,
                destination=evidence_dir / "public-health.json",
                timeout_seconds=timeout_seconds,
            )
        )
    if admin_runtime_metrics_url:
        http_checks.append(
            _capture_http_evidence(
                url=admin_runtime_metrics_url,
                destination=evidence_dir / "admin-runtime-metrics.json",
                headers=headers,
                timeout_seconds=timeout_seconds,
            )
        )
    if admin_runtime_alerts_url:
        http_checks.append(
            _capture_http_evidence(
                url=admin_runtime_alerts_url,
                destination=evidence_dir / "admin-runtime-alerts.json",
                headers=headers,
                timeout_seconds=timeout_seconds,
            )
        )

    summary = {
        "kind": "cutover-evidence",
        "captured_at": _display(os.getenv("CUTOVER_RUN_ID"), report_dir_path.name),
        "report_dir": str(report_dir_path),
        "http_checks": http_checks,
        "artifacts": {
            "record_exists": (report_dir_path / "canary-rollback-rehearsal.md").exists(),
            "openapi_dir_exists": (report_dir_path / "openapi").exists(),
            "compose_ps_exists": (report_dir_path / "logs/compose-ps.txt").exists(),
            "compose_log_exists": (report_dir_path / "logs/compose.log").exists(),
            "shadow_read_summary_exists": (report_dir_path / "shadow-read-summary.md").exists(),
            "dual_write_summary_exists": (report_dir_path / "dual-write-summary.md").exists(),
            "rollback_checks_exists": (report_dir_path / "rollback-verification.md").exists(),
        },
    }
    _write_json(evidence_dir / "cutover-validation.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap load and cutover report artifacts.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    load_parser = subparsers.add_parser(
        "load-baseline",
        help="Create a prefilled load baseline summary next to raw Locust artifacts.",
    )
    load_parser.add_argument(
        "--template-path", default="ops/reports/load/baseline-summary-template.md"
    )
    load_parser.add_argument("--report-prefix", required=True)
    load_parser.add_argument("--environment", default=os.getenv("LOAD_TEST_ENVIRONMENT", "staging"))
    load_parser.add_argument(
        "--release-sha", default=os.getenv("RELEASE_SHA", os.getenv("GITHUB_SHA", ""))
    )
    load_parser.add_argument("--run-id", default=os.getenv("LOAD_RUN_ID", ""))
    load_parser.add_argument("--qa-owner", default=os.getenv("QA_OWNER", ""))
    load_parser.add_argument("--backend-owner", default=os.getenv("BACKEND_OWNER", ""))
    load_parser.add_argument("--command", default="")
    load_parser.add_argument("--scenario-mix", default=", ".join(DEFAULT_LOAD_SCENARIOS))
    load_parser.add_argument("--host", default=os.getenv("LOAD_TEST_HOST", ""))
    load_parser.add_argument("--users", default=os.getenv("LOAD_USERS", ""))
    load_parser.add_argument("--spawn-rate", default=os.getenv("LOAD_SPAWN_RATE", ""))
    load_parser.add_argument("--duration", default=os.getenv("LOAD_DURATION", ""))
    load_parser.add_argument("--disposable-fixtures", default=", ".join(DEFAULT_LOAD_FIXTURES))

    load_capture_parser = subparsers.add_parser(
        "capture-load-evidence",
        help="Capture post-run HTTP evidence and artifact presence for a load baseline.",
    )
    load_capture_parser.add_argument("--report-prefix", required=True)
    load_capture_parser.add_argument(
        "--public-health-url",
        default=os.getenv("LOAD_PUBLIC_HEALTH_URL", ""),
    )
    load_capture_parser.add_argument(
        "--public-metrics-url",
        default=os.getenv("LOAD_PUBLIC_METRICS_URL", ""),
    )
    load_capture_parser.add_argument(
        "--public-metrics-token",
        default=os.getenv("LOAD_PUBLIC_METRICS_TOKEN", ""),
    )
    load_capture_parser.add_argument("--timeout-seconds", type=float, default=10.0)

    cutover_parser = subparsers.add_parser(
        "cutover-rehearsal",
        help="Create a prefilled cutover rehearsal record with screenshots/log directories.",
    )
    cutover_parser.add_argument(
        "--template-path", default="ops/reports/cutover/canary-rollback-rehearsal-template.md"
    )
    cutover_parser.add_argument("--report-dir", required=True)
    cutover_parser.add_argument(
        "--environment", default=os.getenv("CUTOVER_ENVIRONMENT", "staging")
    )
    cutover_parser.add_argument(
        "--release-sha", default=os.getenv("RELEASE_SHA", os.getenv("GITHUB_SHA", ""))
    )
    cutover_parser.add_argument("--run-id", default=os.getenv("CUTOVER_RUN_ID", ""))
    cutover_parser.add_argument("--qa-owner", default=os.getenv("QA_OWNER", ""))
    cutover_parser.add_argument("--backend-owner", default=os.getenv("BACKEND_OWNER", ""))
    cutover_parser.add_argument("--on-call-reviewer", default=os.getenv("ON_CALL_REVIEWER", ""))
    cutover_parser.add_argument("--canary-percentage", default="")
    cutover_parser.add_argument("--feature-flags", default="")
    cutover_parser.add_argument("--migration-revision", default="")
    cutover_parser.add_argument("--rollback-target-version", default="")

    cutover_capture_parser = subparsers.add_parser(
        "capture-cutover-evidence",
        help="Capture health and runtime evidence for a cutover rehearsal bundle.",
    )
    cutover_capture_parser.add_argument("--report-dir", required=True)
    cutover_capture_parser.add_argument(
        "--public-health-url",
        default=os.getenv("STACK_PUBLIC_HEALTH_URL", ""),
    )
    cutover_capture_parser.add_argument(
        "--admin-runtime-metrics-url",
        default=os.getenv("ADMIN_RUNTIME_METRICS_URL", ""),
    )
    cutover_capture_parser.add_argument(
        "--admin-runtime-alerts-url",
        default=os.getenv("ADMIN_RUNTIME_ALERTS_URL", ""),
    )
    cutover_capture_parser.add_argument(
        "--admin-token",
        default=os.getenv("ADMIN_RUNTIME_TOKEN", ""),
    )
    cutover_capture_parser.add_argument("--timeout-seconds", type=float, default=10.0)

    dual_write_parser = subparsers.add_parser(
        "capture-dual-write",
        help="Run dual-write parity verification against configured write and readback scenarios.",
    )
    dual_write_parser.add_argument("--report-dir", required=True)
    dual_write_parser.add_argument(
        "--config-path",
        default=os.getenv("DUAL_WRITE_CONFIG_PATH", ""),
    )
    dual_write_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("DUAL_WRITE_TIMEOUT_SECONDS", "10")),
    )
    dual_write_parser.add_argument("--owner", default=os.getenv("DUAL_WRITE_OWNER", ""))
    dual_write_parser.add_argument(
        "--scope-label",
        default=os.getenv("DUAL_WRITE_SCOPE", ""),
    )
    dual_write_parser.add_argument(
        "--containment-decision",
        default=os.getenv("DUAL_WRITE_CONTAINMENT_DECISION", ""),
    )
    dual_write_parser.add_argument(
        "--primary-label",
        default=os.getenv("DUAL_WRITE_PRIMARY_LABEL", ""),
    )
    dual_write_parser.add_argument(
        "--shadow-label",
        default=os.getenv("DUAL_WRITE_SHADOW_LABEL", ""),
    )
    dual_write_parser.add_argument(
        "--allow-mutations",
        action="store_true",
        default=_is_truthy(os.getenv("DUAL_WRITE_ALLOW_MUTATIONS")),
    )

    shadow_read_parser = subparsers.add_parser(
        "capture-shadow-read",
        help="Run HTTP parity sampling for cutover shadow reads and write summary artifacts.",
    )
    shadow_read_parser.add_argument("--report-dir", required=True)
    shadow_read_parser.add_argument(
        "--config-path",
        default=os.getenv("SHADOW_READ_CONFIG_PATH", ""),
    )
    shadow_read_parser.add_argument(
        "--duration-seconds",
        type=float,
        default=float(os.getenv("SHADOW_READ_DURATION_SECONDS", "900")),
    )
    shadow_read_parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.getenv("SHADOW_READ_INTERVAL_SECONDS", "30")),
    )
    shadow_read_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("SHADOW_READ_TIMEOUT_SECONDS", "10")),
    )
    shadow_read_parser.add_argument("--owner", default=os.getenv("SHADOW_READ_OWNER", ""))
    shadow_read_parser.add_argument(
        "--scope-label",
        default=os.getenv("SHADOW_READ_SCOPE", ""),
    )
    shadow_read_parser.add_argument(
        "--primary-label",
        default=os.getenv("SHADOW_READ_PRIMARY_LABEL", ""),
    )
    shadow_read_parser.add_argument(
        "--shadow-label",
        default=os.getenv("SHADOW_READ_SHADOW_LABEL", ""),
    )

    rollback_parser = subparsers.add_parser(
        "capture-rollback-verification",
        help="Record backup readability and rollback smoke evidence for a cutover run.",
    )
    rollback_parser.add_argument("--report-dir", required=True)
    rollback_parser.add_argument("--backup-dir", required=True)
    rollback_parser.add_argument(
        "--trigger-used",
        default=os.getenv("ROLLBACK_VERIFY_TRIGGER_USED", ""),
    )
    rollback_parser.add_argument(
        "--smoke-suite-rerun",
        default=os.getenv("ROLLBACK_VERIFY_SMOKE_SUITE", ""),
    )
    rollback_parser.add_argument(
        "--backlog-reconciliation",
        default=os.getenv("ROLLBACK_VERIFY_BACKLOG_RECONCILIATION", ""),
    )
    rollback_parser.add_argument(
        "--final-decision",
        default=os.getenv("ROLLBACK_VERIFY_FINAL_DECISION", ""),
    )
    rollback_parser.add_argument(
        "--restore-command",
        default=os.getenv("ROLLBACK_VERIFY_RESTORE_COMMAND", ""),
    )
    rollback_parser.add_argument(
        "--public-health-url",
        default=os.getenv("STACK_PUBLIC_HEALTH_URL", ""),
    )
    rollback_parser.add_argument(
        "--admin-runtime-metrics-url",
        default=os.getenv("ADMIN_RUNTIME_METRICS_URL", ""),
    )
    rollback_parser.add_argument(
        "--admin-runtime-alerts-url",
        default=os.getenv("ADMIN_RUNTIME_ALERTS_URL", ""),
    )
    rollback_parser.add_argument(
        "--admin-token",
        default=os.getenv("ADMIN_RUNTIME_TOKEN", ""),
    )
    rollback_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("ROLLBACK_VERIFY_TIMEOUT_SECONDS", "10")),
    )

    signoff_parser = subparsers.add_parser(
        "validate-cutover-signoff",
        help="Validate that required cutover artifacts are populated and ready for signoff.",
    )
    signoff_parser.add_argument("--report-dir", required=True)
    signoff_parser.add_argument("--load-report-dir", required=True)
    signoff_parser.add_argument("--backup-dir", default=os.getenv("BACKUP_DIR", ""))
    signoff_parser.add_argument(
        "--k8s-validation-summary",
        default=os.getenv("SIGNOFF_K8S_VALIDATION_SUMMARY", ""),
    )
    signoff_parser.add_argument(
        "--rollout-evidence-path",
        default=os.getenv("SIGNOFF_ROLLOUT_EVIDENCE_PATH", ""),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "load-baseline":
        path, created = bootstrap_load_report(
            template_path=args.template_path,
            report_prefix=args.report_prefix,
            environment=args.environment,
            release_sha=args.release_sha,
            run_id=args.run_id,
            qa_owner=args.qa_owner,
            backend_owner=args.backend_owner,
            command=args.command,
            scenario_mix=args.scenario_mix,
            host=args.host,
            users=args.users,
            spawn_rate=args.spawn_rate,
            duration=args.duration,
            disposable_fixtures=args.disposable_fixtures,
        )
        status = "Created" if created else "Preserved"
        print(f"{status} load summary: {path}")
        return 0

    if args.subcommand == "capture-load-evidence":
        summary = capture_load_evidence(
            report_prefix=args.report_prefix,
            public_health_url=args.public_health_url,
            public_metrics_url=args.public_metrics_url,
            public_metrics_token=args.public_metrics_token,
            timeout_seconds=args.timeout_seconds,
        )
        print(
            "Captured load evidence: "
            f"{Path(args.report_prefix).parent / 'evidence' / 'load-evidence-summary.json'}"
        )
        return 0

    if args.subcommand == "cutover-rehearsal":
        path, created = bootstrap_cutover_report(
            template_path=args.template_path,
            report_dir=args.report_dir,
            environment=args.environment,
            release_sha=args.release_sha,
            run_id=args.run_id,
            qa_owner=args.qa_owner,
            backend_owner=args.backend_owner,
            on_call_reviewer=args.on_call_reviewer,
            canary_percentage=args.canary_percentage,
            feature_flags=args.feature_flags,
            migration_revision=args.migration_revision,
            rollback_target_version=args.rollback_target_version,
        )
        status = "Created" if created else "Preserved"
        print(f"{status} cutover record: {path}")
        return 0

    if args.subcommand == "capture-dual-write":
        summary = capture_dual_write_summary(
            report_dir=args.report_dir,
            config_path=args.config_path,
            timeout_seconds=args.timeout_seconds,
            owner=args.owner,
            scope_label=args.scope_label,
            containment_decision=args.containment_decision,
            primary_label=args.primary_label,
            shadow_label=args.shadow_label,
            allow_mutations=args.allow_mutations,
        )
        print(
            "Captured dual-write evidence: "
            f"{Path(args.report_dir) / 'evidence' / 'dual-write-results.json'}"
        )
        return 0

    if args.subcommand == "capture-shadow-read":
        summary = capture_shadow_read_summary(
            report_dir=args.report_dir,
            config_path=args.config_path,
            duration_seconds=args.duration_seconds,
            interval_seconds=args.interval_seconds,
            timeout_seconds=args.timeout_seconds,
            owner=args.owner,
            scope_label=args.scope_label,
            primary_label=args.primary_label,
            shadow_label=args.shadow_label,
        )
        print(
            "Captured shadow read evidence: "
            f"{Path(args.report_dir) / 'evidence' / 'shadow-read-results.json'}"
        )
        return 0

    if args.subcommand == "capture-rollback-verification":
        summary = capture_rollback_verification(
            report_dir=args.report_dir,
            backup_dir=args.backup_dir,
            trigger_used=args.trigger_used,
            smoke_suite_rerun=args.smoke_suite_rerun,
            backlog_reconciliation=args.backlog_reconciliation,
            final_decision=args.final_decision,
            restore_command=args.restore_command,
            public_health_url=args.public_health_url,
            admin_runtime_metrics_url=args.admin_runtime_metrics_url,
            admin_runtime_alerts_url=args.admin_runtime_alerts_url,
            admin_token=args.admin_token,
            timeout_seconds=args.timeout_seconds,
        )
        print(
            "Captured rollback verification: "
            f"{Path(args.report_dir) / 'evidence' / 'rollback-verification.json'}"
        )
        return 0

    if args.subcommand == "validate-cutover-signoff":
        summary = validate_cutover_signoff(
            report_dir=args.report_dir,
            load_report_dir=args.load_report_dir,
            backup_dir=args.backup_dir,
            k8s_validation_summary=args.k8s_validation_summary,
            rollout_evidence_path=args.rollout_evidence_path,
        )
        print(
            "Validated cutover signoff: "
            f"{Path(args.report_dir) / 'evidence' / 'cutover-signoff-summary.json'}"
        )
        return 0

    summary = capture_cutover_evidence(
        report_dir=args.report_dir,
        public_health_url=args.public_health_url,
        admin_runtime_metrics_url=args.admin_runtime_metrics_url,
        admin_runtime_alerts_url=args.admin_runtime_alerts_url,
        admin_token=args.admin_token,
        timeout_seconds=args.timeout_seconds,
    )
    print(
        "Captured cutover evidence: "
        f"{Path(args.report_dir) / 'evidence' / 'cutover-validation.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
