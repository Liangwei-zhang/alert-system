from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import shlex
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit
from uuid import uuid4

DEFAULT_LOAD_HOST = "http://127.0.0.1:8080"
DEFAULT_ADMIN_URL = "http://127.0.0.1:8001"


@dataclass(frozen=True, slots=True)
class CalibrationRule:
    env_key: str
    metric_name: str
    default_value: float
    multiplier: float
    headroom: float = 0.0
    minimum: float = 0.0
    maximum: float | None = None
    decimals: int = 0


@dataclass(frozen=True, slots=True)
class PrometheusThresholdRule:
    env_key: str
    expr_path: str
    summary_path: str
    expr_template: str
    summary_template: str


CALIBRATION_RULES: tuple[CalibrationRule, ...] = (
    CalibrationRule(
        env_key="RUNTIME_ALERT_BROKER_LAG_THRESHOLD",
        metric_name="event_broker_consumer_lag_total",
        default_value=200,
        multiplier=2.0,
        headroom=20.0,
        minimum=50.0,
        decimals=0,
    ),
    CalibrationRule(
        env_key="RUNTIME_ALERT_PGBOUNCER_WAITING_CLIENTS_THRESHOLD",
        metric_name="pgbouncer_clients_waiting",
        default_value=10,
        multiplier=2.0,
        headroom=2.0,
        minimum=2.0,
        decimals=0,
    ),
    CalibrationRule(
        env_key="RUNTIME_ALERT_REDIS_MEMORY_PERCENT_THRESHOLD",
        metric_name="redis_memory_utilization_percent",
        default_value=85.0,
        multiplier=1.1,
        minimum=75.0,
        maximum=95.0,
        decimals=2,
    ),
    CalibrationRule(
        env_key="RUNTIME_ALERT_CLICKHOUSE_WRITE_FAILURE_RATE_THRESHOLD",
        metric_name="clickhouse_write_failure_rate_percent",
        default_value=5.0,
        multiplier=2.0,
        minimum=1.0,
        maximum=100.0,
        decimals=2,
    ),
    CalibrationRule(
        env_key="RUNTIME_ALERT_OBJECT_STORAGE_ARCHIVE_FAILURE_RATE_THRESHOLD",
        metric_name="object_storage_archive_failure_rate_percent",
        default_value=5.0,
        multiplier=2.0,
        minimum=1.0,
        maximum=100.0,
        decimals=2,
    ),
)

DEFAULT_K8S_IMAGE_NAME = "ghcr.io/openclaw/stock-py"
DEFAULT_K8S_MONITORING_SECRET_NAME = "stock-py-monitoring-secret"

PROMETHEUS_THRESHOLD_RULES: tuple[PrometheusThresholdRule, ...] = (
    PrometheusThresholdRule(
        env_key="RUNTIME_ALERT_BROKER_LAG_THRESHOLD",
        expr_path="/spec/groups/0/rules/3/expr",
        summary_path="/spec/groups/0/rules/3/annotations/summary",
        expr_template="max(stock_signal_admin_event_broker_consumer_lag_total) > {value}",
        summary_template="Broker consumer lag is above {value}",
    ),
    PrometheusThresholdRule(
        env_key="RUNTIME_ALERT_PGBOUNCER_WAITING_CLIENTS_THRESHOLD",
        expr_path="/spec/groups/0/rules/4/expr",
        summary_path="/spec/groups/0/rules/4/annotations/summary",
        expr_template="max(stock_signal_admin_pgbouncer_clients_waiting) > {value}",
        summary_template="PgBouncer waiting clients are above {value}",
    ),
    PrometheusThresholdRule(
        env_key="RUNTIME_ALERT_REDIS_MEMORY_PERCENT_THRESHOLD",
        expr_path="/spec/groups/0/rules/5/expr",
        summary_path="/spec/groups/0/rules/5/annotations/summary",
        expr_template="max(stock_signal_admin_redis_memory_utilization_percent) > {value}",
        summary_template="Redis memory utilization is above {value}%",
    ),
    PrometheusThresholdRule(
        env_key="RUNTIME_ALERT_CLICKHOUSE_WRITE_FAILURE_RATE_THRESHOLD",
        expr_path="/spec/groups/0/rules/6/expr",
        summary_path="/spec/groups/0/rules/6/annotations/summary",
        expr_template="max(stock_signal_admin_clickhouse_write_failure_rate_percent) > {value}",
        summary_template="ClickHouse write failure rate is above {value}%",
    ),
    PrometheusThresholdRule(
        env_key="RUNTIME_ALERT_OBJECT_STORAGE_ARCHIVE_FAILURE_RATE_THRESHOLD",
        expr_path="/spec/groups/0/rules/7/expr",
        summary_path="/spec/groups/0/rules/7/annotations/summary",
        expr_template="max(stock_signal_admin_object_storage_archive_failure_rate_percent) > {value}",
        summary_template="Object storage archive failure rate is above {value}%",
    ),
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _rewrite_compose_service_host(url: str) -> str:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").strip().lower()
    if hostname not in {"postgres", "pgbouncer"}:
        return url

    port_map = {
        "postgres": int(os.getenv("POSTGRES_HOST_PORT", "5432")),
        "pgbouncer": int(os.getenv("PGBOUNCER_HOST_PORT", "6432")),
    }
    username = parsed.username or ""
    password = parsed.password or ""
    auth = username
    if password:
        auth = f"{auth}:{password}"
    if auth:
        auth = f"{auth}@"
    rewritten = SplitResult(
        scheme=parsed.scheme,
        netloc=f"{auth}127.0.0.1:{port_map[hostname]}",
        path=parsed.path,
        query=parsed.query,
        fragment=parsed.fragment,
    )
    return urlunsplit(rewritten)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _shell_assignment(key: str, value: Any) -> str:
    return f"{key}={shlex.quote(str(value))}"


def write_env_file(path: Path, values: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(_shell_assignment(key, values[key]) for key in sorted(values)) + "\n"
    path.write_text(content, encoding="utf-8")


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        normalized_key = key.removeprefix("export ").strip()
        parsed = shlex.split(raw_value, posix=True)
        if not parsed:
            values[normalized_key] = ""
            continue
        values[normalized_key] = parsed[0] if len(parsed) == 1 else " ".join(parsed)
    return values


def _yaml_quote(value: Any) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _default_namespace(environment: str) -> str:
    normalized = environment.strip().lower()
    return "stock-py" if normalized == "production" else f"stock-py-{normalized}"


def _default_ingress_host(environment: str) -> str:
    normalized = environment.strip().lower()
    return "stock-py.example.com" if normalized == "production" else f"stock-py-{normalized}.example.com"


def _resolve_kustomize_path(raw_path: str, *, environment: str) -> Path:
    if raw_path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = _project_root() / candidate
        return candidate.resolve()

    overlay_path = _project_root() / "ops" / "k8s" / "overlays" / environment
    if overlay_path.is_dir():
        return overlay_path.resolve()
    return (_project_root() / "ops" / "k8s" / "base").resolve()


def _default_release_image() -> str:
    explicit = os.getenv("K8S_RELEASE_IMAGE") or os.getenv("RELEASE_IMAGE")
    if explicit:
        return explicit.strip()
    release_sha = (os.getenv("RELEASE_SHA") or "").strip()
    if release_sha:
        return f"{DEFAULT_K8S_IMAGE_NAME}:{release_sha}"
    return ""


def _parse_image_reference(image_reference: str) -> dict[str, str]:
    reference = image_reference.strip()
    if not reference:
        return {}

    if "@" in reference:
        new_name, digest = reference.rsplit("@", 1)
        return {"newName": new_name, "digest": digest}

    tail = reference.rsplit("/", 1)[-1]
    if ":" in tail:
        new_name, new_tag = reference.rsplit(":", 1)
        return {"newName": new_name, "newTag": new_tag}

    return {"newName": reference}


def _build_images_block(image_reference: str) -> list[str]:
    parsed = _parse_image_reference(image_reference)
    if not parsed:
        return []

    lines = ["images:", f"  - name: {DEFAULT_K8S_IMAGE_NAME}"]
    for key in ("newName", "newTag", "digest"):
        value = parsed.get(key)
        if value:
            lines.append(f"    {key}: {value}")
    return lines


def _default_threshold_values() -> dict[str, str]:
    defaults: dict[str, str] = {}
    for rule in CALIBRATION_RULES:
        defaults[rule.env_key] = str(_rule_default(rule))
    return defaults


def _build_runtime_threshold_config_patch(values: dict[str, str]) -> str:
    lines = [
        "apiVersion: v1",
        "kind: ConfigMap",
        "metadata:",
        "  name: stock-py-runtime",
        "data:",
    ]
    for rule in CALIBRATION_RULES:
        lines.append(f"  {rule.env_key}: {_yaml_quote(values[rule.env_key])}")
    return "\n".join(lines) + "\n"


def _build_runtime_threshold_json_patch(values: dict[str, str]) -> str:
    lines: list[str] = []
    for rule in PROMETHEUS_THRESHOLD_RULES:
        threshold = values[rule.env_key]
        lines.extend(
            [
                "- op: replace",
                f"  path: {rule.expr_path}",
                f"  value: {_yaml_quote(rule.expr_template.format(value=threshold))}",
                "- op: replace",
                f"  path: {rule.summary_path}",
                f"  value: {_yaml_quote(rule.summary_template.format(value=threshold))}",
            ]
        )
    return "\n".join(lines) + "\n"


def _build_ingress_patch(host: str) -> str:
    return "\n".join(
        [
            "apiVersion: networking.k8s.io/v1",
            "kind: Ingress",
            "metadata:",
            "  name: stock-py",
            "spec:",
            "  rules:",
            f"    - host: {host}",
            "      http:",
            "        paths:",
            "          - path: /",
            "            pathType: Prefix",
            "            backend:",
            "              service:",
            "                name: public-api",
            "                port:",
            "                  number: 8000",
            "          - path: /v1/admin",
            "            pathType: Prefix",
            "            backend:",
            "              service:",
            "                name: admin-api",
            "                port:",
            "                  number: 8001",
        ]
    ) + "\n"


def _build_monitoring_secret_patch(secret_name: str) -> str:
    return "---\n".join(
        [
            "\n".join(
                [
                    "apiVersion: monitoring.coreos.com/v1",
                    "kind: ServiceMonitor",
                    "metadata:",
                    "  name: public-api",
                    "spec:",
                    "  endpoints:",
                    "    - bearerTokenSecret:",
                    f"        name: {secret_name}",
                    "        key: publicMonitoringBearer",
                ]
            ),
            "\n".join(
                [
                    "apiVersion: monitoring.coreos.com/v1",
                    "kind: ServiceMonitor",
                    "metadata:",
                    "  name: admin-api",
                    "spec:",
                    "  endpoints:",
                    "    - bearerTokenSecret:",
                    f"        name: {secret_name}",
                    "        key: adminMetricsBearer",
                ]
            ),
        ]
    ) + "\n"


def load_local_dev_settings(root: Path | None = None) -> None:
    project_root = root or _project_root()
    secret_dir = project_root / "ops/secrets/dev"
    fallback_files = {
        "DATABASE_URL": secret_dir / "direct_database_url.txt",
        "PGBOUNCER_ADMIN_URL": secret_dir / "pgbouncer_admin_url.txt",
        "SECRET_KEY": secret_dir / "app_secret_key.txt",
        "TRADE_LINK_SECRET": secret_dir / "trade_link_secret.txt",
    }
    for env_key, path in fallback_files.items():
        if os.getenv(env_key) or not path.exists():
            continue
        value = _read_text(path)
        if env_key in {"DATABASE_URL", "PGBOUNCER_ADMIN_URL"}:
            value = _rewrite_compose_service_host(value)
        os.environ[env_key] = value

    from infra.core.config import get_settings

    get_settings.cache_clear()


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rule_default(rule: CalibrationRule) -> int | float:
    if rule.decimals == 0:
        return int(rule.default_value)
    return round(rule.default_value, rule.decimals)


def _round_value(value: float, decimals: int) -> int | float:
    if decimals == 0:
        return int(math.ceil(value))
    return round(value, decimals)


def recommend_runtime_alerts(
    metrics_payload: dict[str, Any],
    *,
    allow_tightening: bool = False,
) -> list[dict[str, Any]]:
    metric_values: dict[str, list[float]] = {}
    for point in metrics_payload.get("metrics", []):
        metric_name = str(point.get("name") or "").strip()
        if not metric_name:
            continue
        value = _coerce_float(point.get("value"))
        if value is None:
            continue
        metric_values.setdefault(metric_name, []).append(value)

    recommendations: list[dict[str, Any]] = []
    for rule in CALIBRATION_RULES:
        observed = None
        if metric_values.get(rule.metric_name):
            observed = max(metric_values[rule.metric_name])

        reason = "default_preserved"
        suggested = rule.default_value
        if observed is not None and observed > 0:
            suggested = max(rule.minimum, (observed * rule.multiplier) + rule.headroom)
            if rule.maximum is not None:
                suggested = min(rule.maximum, suggested)
            if not allow_tightening:
                suggested = max(rule.default_value, suggested)
            reason = "scaled_observed_peak"

        rounded = _round_value(suggested, rule.decimals)
        recommendations.append(
            {
                "env_key": rule.env_key,
                "metric_name": rule.metric_name,
                "observed_peak": observed,
                "suggested_value": rounded,
                "default_value": _rule_default(rule),
                "reason": reason,
            }
        )

    return recommendations


def resolve_runtime_metrics_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_dir():
        directory_candidates = (
            candidate / "evidence" / "admin-runtime-metrics.json",
            candidate / "admin-runtime-metrics.json",
        )
        for directory_candidate in directory_candidates:
            if directory_candidate.exists():
                return directory_candidate
    return candidate


def calibrate_runtime_alerts(
    *,
    metrics_path: str,
    output_env: str,
    output_json: str,
    allow_tightening: bool = False,
) -> dict[str, Any]:
    resolved_metrics_path = resolve_runtime_metrics_path(metrics_path)
    payload = json.loads(resolved_metrics_path.read_text(encoding="utf-8"))
    recommendations = recommend_runtime_alerts(payload, allow_tightening=allow_tightening)
    env_values = {item["env_key"]: item["suggested_value"] for item in recommendations}
    write_env_file(Path(output_env), env_values)
    summary = {
        "metrics_path": str(resolved_metrics_path),
        "output_env": output_env,
        "allow_tightening": allow_tightening,
        "recommendations": recommendations,
    }
    _write_json(Path(output_json), summary)
    return summary


def render_k8s_cutover_overrides(
    *,
    runtime_alert_env: str,
    output_dir: str,
    environment: str,
    base_kustomize_path: str = "",
    namespace: str = "",
    ingress_host: str = "",
    release_image: str = "",
    monitoring_secret_name: str = DEFAULT_K8S_MONITORING_SECRET_NAME,
    output_json: str = "",
) -> dict[str, Any]:
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    resolved_environment = environment.strip().lower() or "staging"
    resolved_namespace = namespace.strip() or _default_namespace(resolved_environment)
    resolved_ingress_host = ingress_host.strip() or _default_ingress_host(resolved_environment)
    resolved_release_image = release_image.strip() or _default_release_image()
    resolved_base_path = _resolve_kustomize_path(
        base_kustomize_path,
        environment=resolved_environment,
    )

    threshold_values = _default_threshold_values()
    threshold_values.update(_read_env_file(Path(runtime_alert_env)))

    kustomization_lines = [
        "apiVersion: kustomize.config.k8s.io/v1beta1",
        "kind: Kustomization",
        f"namespace: {resolved_namespace}",
        "resources:",
        f"  - {os.path.relpath(resolved_base_path, output_root)}",
        "patches:",
        "  - path: runtime-alert-thresholds.patch.yaml",
        "  - path: ingress-host.patch.yaml",
        "  - path: prometheus-runtime-thresholds.patch.yaml",
        "    target:",
        "      group: monitoring.coreos.com",
        "      version: v1",
        "      kind: PrometheusRule",
        "      name: stock-py-runtime",
    ]
    if monitoring_secret_name.strip() and monitoring_secret_name != DEFAULT_K8S_MONITORING_SECRET_NAME:
        kustomization_lines.append("  - path: monitoring-secret.patch.yaml")

    image_block = _build_images_block(resolved_release_image)
    if image_block:
        kustomization_lines.extend(image_block)

    _write_text(output_root / "kustomization.yaml", "\n".join(kustomization_lines) + "\n")
    _write_text(
        output_root / "runtime-alert-thresholds.patch.yaml",
        _build_runtime_threshold_config_patch(threshold_values),
    )
    _write_text(output_root / "ingress-host.patch.yaml", _build_ingress_patch(resolved_ingress_host))
    _write_text(
        output_root / "prometheus-runtime-thresholds.patch.yaml",
        _build_runtime_threshold_json_patch(threshold_values),
    )
    if monitoring_secret_name.strip() and monitoring_secret_name != DEFAULT_K8S_MONITORING_SECRET_NAME:
        _write_text(
            output_root / "monitoring-secret.patch.yaml",
            _build_monitoring_secret_patch(monitoring_secret_name.strip()),
        )

    summary = {
        "environment": resolved_environment,
        "namespace": resolved_namespace,
        "ingress_host": resolved_ingress_host,
        "release_image": resolved_release_image or None,
        "base_kustomize_path": str(resolved_base_path),
        "overlay_kustomization": str(output_root / "kustomization.yaml"),
        "runtime_alert_env": str(Path(runtime_alert_env).resolve()),
        "threshold_values": threshold_values,
        "monitoring_secret_name": monitoring_secret_name.strip()
        or DEFAULT_K8S_MONITORING_SECRET_NAME,
    }
    resolved_output_json = Path(output_json).resolve() if output_json else output_root / "summary.json"
    _write_json(resolved_output_json, summary)
    summary["output_json"] = str(resolved_output_json)
    return summary


def _access_claims(user: Any, *, is_admin: bool = False) -> dict[str, Any]:
    claims = {
        "type": "access",
        "plan": str(getattr(user, "plan", "free")),
        "locale": str(getattr(user, "locale", "en-US")),
        "timezone": str(getattr(user, "timezone", "UTC")),
    }
    if is_admin:
        claims["is_admin"] = True
        claims["scopes"] = ["admin:runtime", "admin:tasks"]
    return claims


async def bootstrap_local_fixtures(
    *,
    output_env: str,
    output_json: str,
    host: str,
    admin_url: str,
    user_email: str,
    admin_email: str,
    trade_symbol: str,
    trade_action: str,
    trade_shares: float,
    trade_price: float,
    trade_expiry_hours: int,
    locale: str,
    timezone_name: str,
) -> dict[str, Any]:
    load_local_dev_settings()

    from domains.auth.repository import SessionRepository, UserRepository
    from domains.trades.link_security import get_link_signer
    from domains.trades.repository import TradeRepository
    from infra.db.session import get_session_factory
    from infra.security.token_signer import get_token_signer

    session_factory = get_session_factory()
    token_signer = get_token_signer()
    link_signer = get_link_signer()

    trade_id = str(uuid4())
    now = _utcnow()
    access_expires_at = now + timedelta(minutes=30)
    refresh_expires_at = now + timedelta(days=30)
    admin_expires_at = now + timedelta(minutes=30)

    async with session_factory() as session:
        user_repository = UserRepository(session)
        session_repository = SessionRepository(session)
        trade_repository = TradeRepository(session)

        user = await user_repository.upsert_by_email(user_email, locale, timezone_name)
        await user_repository.update_last_login(user.id, locale, timezone_name)

        access_token = token_signer.sign(
            user.id,
            claims=_access_claims(user),
            expires_in=access_expires_at - now,
        )
        refresh_token = token_signer.sign(
            user.id,
            claims={"type": "refresh", "plan": str(getattr(user, "plan", "free"))},
            expires_in=refresh_expires_at - now,
        )
        await session_repository.create_session(
            token_hash=_hash_token(access_token),
            user_id=user.id,
            expires_at=access_expires_at,
            device_info={"kind": "access", "source": "local-rehearsal"},
        )
        await session_repository.create_session(
            token_hash=_hash_token(refresh_token),
            user_id=user.id,
            expires_at=refresh_expires_at,
            device_info={"kind": "refresh", "source": "local-rehearsal"},
        )

        admin_user = await user_repository.upsert_by_email(admin_email, locale, timezone_name)
        admin_access_token = token_signer.sign(
            admin_user.id,
            claims=_access_claims(admin_user, is_admin=True),
            expires_in=admin_expires_at - now,
        )
        await session_repository.create_session(
            token_hash=_hash_token(admin_access_token),
            user_id=admin_user.id,
            expires_at=admin_expires_at,
            device_info={"kind": "access", "source": "local-rehearsal", "admin": True},
        )

        link_token, link_sig, expires_at = link_signer.create_link(
            user.id,
            trade_symbol,
            expiry_hours=trade_expiry_hours,
        )
        suggested_amount = round(float(trade_shares) * float(trade_price), 2)
        await trade_repository.create(
            trade_id=trade_id,
            user_id=user.id,
            symbol=trade_symbol.upper(),
            action=trade_action.lower(),
            suggested_shares=trade_shares,
            suggested_price=trade_price,
            suggested_amount=suggested_amount,
            link_token=link_token,
            link_sig=link_sig,
            expires_at=expires_at,
            extra={"source": "local-rehearsal"},
        )

        await session.commit()

    env_values = {
        "ADMIN_RUNTIME_TOKEN": admin_access_token,
        "ADMIN_RUNTIME_URL": admin_url,
        "LOAD_TEST_ACCESS_TOKEN": access_token,
        "LOAD_TEST_AUTH_EMAIL": user_email,
        "LOAD_TEST_ENABLE_TRADE_MUTATIONS": "false",
        "LOAD_TEST_HOST": host,
        "LOAD_TEST_REFRESH_TOKEN": refresh_token,
        "LOAD_TEST_TRADE_ID": trade_id,
        "LOAD_TEST_TRADE_TOKEN": link_token,
    }
    write_env_file(Path(output_env), env_values)

    summary = {
        "output_env": output_env,
        "host": host,
        "admin_url": admin_url,
        "user_email": user_email,
        "admin_email": admin_email,
        "user_id": int(getattr(user, "id", 0)),
        "admin_user_id": int(getattr(admin_user, "id", 0)),
        "trade": {
            "id": trade_id,
            "symbol": trade_symbol.upper(),
            "action": trade_action.lower(),
            "suggested_shares": trade_shares,
            "suggested_price": trade_price,
            "suggested_amount": suggested_amount,
            "expires_at": expires_at.isoformat(),
        },
        "generated_at": now.isoformat(),
    }
    _write_json(Path(output_json), summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap local rehearsal fixtures and threshold recommendations."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-fixtures",
        help="Create local access/admin tokens and a disposable trade fixture env file.",
    )
    bootstrap_parser.add_argument("--output-env", required=True)
    bootstrap_parser.add_argument("--output-json", required=True)
    bootstrap_parser.add_argument("--host", default=os.getenv("LOAD_TEST_HOST", DEFAULT_LOAD_HOST))
    bootstrap_parser.add_argument(
        "--admin-url",
        default=os.getenv("ADMIN_RUNTIME_URL", DEFAULT_ADMIN_URL),
    )
    bootstrap_parser.add_argument(
        "--user-email",
        default=os.getenv("LOAD_TEST_AUTH_EMAIL", "loadtest@example.com"),
    )
    bootstrap_parser.add_argument(
        "--admin-email",
        default=os.getenv("ADMIN_BOOTSTRAP_EMAIL", "admin-loadtest@example.com"),
    )
    bootstrap_parser.add_argument(
        "--trade-symbol", default=os.getenv("LOAD_TEST_TRADE_SYMBOL", "AAPL")
    )
    bootstrap_parser.add_argument(
        "--trade-action", default=os.getenv("LOAD_TEST_TRADE_ACTION", "buy")
    )
    bootstrap_parser.add_argument("--trade-shares", type=float, default=10.0)
    bootstrap_parser.add_argument("--trade-price", type=float, default=182.5)
    bootstrap_parser.add_argument("--trade-expiry-hours", type=int, default=24)
    bootstrap_parser.add_argument("--locale", default=os.getenv("LOAD_TEST_LOCALE", "en-US"))
    bootstrap_parser.add_argument("--timezone", default=os.getenv("LOAD_TEST_TIMEZONE", "UTC"))

    calibrate_parser = subparsers.add_parser(
        "calibrate-thresholds",
        help="Recommend runtime alert thresholds from captured admin runtime metrics.",
    )
    calibrate_parser.add_argument("--metrics-path", required=True)
    calibrate_parser.add_argument("--output-env", required=True)
    calibrate_parser.add_argument("--output-json", required=True)
    calibrate_parser.add_argument("--allow-tightening", action="store_true")

    k8s_parser = subparsers.add_parser(
        "render-k8s-overrides",
        help="Render a Kustomize overlay bundle from calibrated runtime alert thresholds.",
    )
    k8s_parser.add_argument("--runtime-alert-env", required=True)
    k8s_parser.add_argument("--output-dir", required=True)
    k8s_parser.add_argument(
        "--environment",
        default=os.getenv("CUTOVER_ENVIRONMENT", os.getenv("ENVIRONMENT", "staging")),
    )
    k8s_parser.add_argument(
        "--base-kustomize-path",
        default=os.getenv("K8S_BASE_KUSTOMIZE_PATH", ""),
    )
    k8s_parser.add_argument("--namespace", default=os.getenv("K8S_NAMESPACE", ""))
    k8s_parser.add_argument("--ingress-host", default=os.getenv("K8S_INGRESS_HOST", ""))
    k8s_parser.add_argument(
        "--release-image",
        default=_default_release_image(),
    )
    k8s_parser.add_argument(
        "--monitoring-secret-name",
        default=os.getenv("K8S_MONITORING_SECRET_NAME", DEFAULT_K8S_MONITORING_SECRET_NAME),
    )
    k8s_parser.add_argument("--output-json", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "bootstrap-fixtures":
        summary = asyncio.run(
            bootstrap_local_fixtures(
                output_env=args.output_env,
                output_json=args.output_json,
                host=args.host,
                admin_url=args.admin_url,
                user_email=args.user_email,
                admin_email=args.admin_email,
                trade_symbol=args.trade_symbol,
                trade_action=args.trade_action,
                trade_shares=args.trade_shares,
                trade_price=args.trade_price,
                trade_expiry_hours=args.trade_expiry_hours,
                locale=args.locale,
                timezone_name=args.timezone,
            )
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.subcommand == "render-k8s-overrides":
        summary = render_k8s_cutover_overrides(
            runtime_alert_env=args.runtime_alert_env,
            output_dir=args.output_dir,
            environment=args.environment,
            base_kustomize_path=args.base_kustomize_path,
            namespace=args.namespace,
            ingress_host=args.ingress_host,
            release_image=args.release_image,
            monitoring_secret_name=args.monitoring_secret_name,
            output_json=args.output_json,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    summary = calibrate_runtime_alerts(
        metrics_path=args.metrics_path,
        output_env=args.output_env,
        output_json=args.output_json,
        allow_tightening=bool(args.allow_tightening),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
