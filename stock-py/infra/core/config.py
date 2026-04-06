from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class FileBackedEnvSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(self, field, field_name: str) -> tuple[Any, str, bool]:
        aliases = list(getattr(getattr(field, "validation_alias", None), "choices", []))
        aliases.append(field_name.upper())
        seen: set[str] = set()
        for alias in aliases:
            env_key = str(alias).strip()
            if not env_key or env_key in seen:
                continue
            seen.add(env_key)
            file_path = os.getenv(f"{env_key}_FILE")
            if not file_path:
                continue
            payload = Path(file_path).read_text(encoding="utf-8").strip()
            return payload, field_name, False
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for field_name, field in self.settings_cls.model_fields.items():
            value, key, value_is_complex = self.get_field_value(field, field_name)
            if value is None:
                continue
            prepared = self.prepare_field_value(key, field, value, value_is_complex)
            if prepared is not None:
                data[key] = prepared
        return data


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            FileBackedEnvSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

    project_name: str = Field(
        default="StockPy API",
        validation_alias=AliasChoices("PROJECT_NAME"),
    )
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT"),
    )
    debug: bool = Field(default=True, validation_alias=AliasChoices("DEBUG"))
    version: str = Field(default="1.0.0", validation_alias=AliasChoices("VERSION"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))

    public_api_host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("PUBLIC_API_HOST", "HOST"),
    )
    public_api_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PUBLIC_API_PORT", "PORT"),
    )
    admin_api_host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("ADMIN_API_HOST"),
    )
    admin_api_port: int = Field(
        default=8001,
        validation_alias=AliasChoices("ADMIN_API_PORT"),
    )
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        validation_alias=AliasChoices("ALLOWED_ORIGINS"),
    )

    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/stock_py",
        validation_alias=AliasChoices("DATABASE_URL"),
    )
    database_pool_mode: str = Field(
        default="direct",
        validation_alias=AliasChoices("DATABASE_POOL_MODE"),
    )
    database_echo: bool = Field(
        default=False,
        validation_alias=AliasChoices("DATABASE_ECHO"),
    )
    pgbouncer_admin_url: str = Field(
        default="",
        validation_alias=AliasChoices("PGBOUNCER_ADMIN_URL"),
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL"),
    )
    cache_fill_lock_ttl_seconds: int = Field(
        default=15,
        validation_alias=AliasChoices("CACHE_FILL_LOCK_TTL_SECONDS"),
    )
    cache_fill_lock_wait_timeout_ms: int = Field(
        default=1000,
        validation_alias=AliasChoices("CACHE_FILL_LOCK_WAIT_TIMEOUT_MS"),
    )
    cache_fill_lock_poll_interval_ms: int = Field(
        default=50,
        validation_alias=AliasChoices("CACHE_FILL_LOCK_POLL_INTERVAL_MS"),
    )
    cache_fill_lock_refresh_interval_ms: int = Field(
        default=5000,
        validation_alias=AliasChoices("CACHE_FILL_LOCK_REFRESH_INTERVAL_MS"),
    )
    account_dashboard_cache_ttl_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices("ACCOUNT_DASHBOARD_CACHE_TTL_SECONDS"),
    )
    account_profile_cache_ttl_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices("ACCOUNT_PROFILE_CACHE_TTL_SECONDS"),
    )
    trade_info_cache_ttl_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices("TRADE_INFO_CACHE_TTL_SECONDS"),
    )
    push_devices_cache_ttl_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices("PUSH_DEVICES_CACHE_TTL_SECONDS"),
    )
    email_code_cleanup_interval_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices("EMAIL_CODE_CLEANUP_INTERVAL_SECONDS"),
    )

    secret_key: str = Field(
        default="change-me-in-production",
        validation_alias=AliasChoices("SECRET_KEY"),
    )
    algorithm: str = Field(default="HS256", validation_alias=AliasChoices("ALGORITHM"))
    access_token_expire_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES"),
    )
    rate_limit_per_minute: int = Field(
        default=60,
        validation_alias=AliasChoices("RATE_LIMIT_PER_MINUTE"),
    )
    idempotency_ttl_seconds: int = Field(
        default=86_400,
        validation_alias=AliasChoices("IDEMPOTENCY_TTL_SECONDS"),
    )
    scheduler_heartbeat_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices("SCHEDULER_HEARTBEAT_SECONDS"),
    )
    http_timeout_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices("HTTP_TIMEOUT_SECONDS"),
    )
    tradingagents_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("TRADINGAGENTS_WEBHOOK_SECRET"),
    )
    trade_link_secret: str = Field(
        default="change-me-trade-link-secret",
        validation_alias=AliasChoices("TRADE_LINK_SECRET"),
    )
    internal_signal_ingest_secret: str = Field(
        default="",
        validation_alias=AliasChoices("INTERNAL_SIGNAL_INGEST_SECRET"),
    )
    internal_sidecar_secret: str = Field(
        default="",
        validation_alias=AliasChoices("INTERNAL_SIDECAR_SECRET"),
    )
    web_push_public_key: str = Field(
        default="",
        validation_alias=AliasChoices("WEB_PUSH_PUBLIC_KEY"),
    )
    web_push_private_key: str = Field(
        default="",
        validation_alias=AliasChoices("WEB_PUSH_PRIVATE_KEY"),
    )
    web_push_subject: str = Field(
        default="mailto:admin@stockpy.com",
        validation_alias=AliasChoices("WEB_PUSH_SUBJECT"),
    )
    smtp_host: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_HOST"),
    )
    smtp_port: int = Field(
        default=587,
        validation_alias=AliasChoices("SMTP_PORT"),
    )
    smtp_username: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_USERNAME"),
    )
    smtp_password: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_PASSWORD"),
    )
    smtp_use_tls: bool = Field(
        default=True,
        validation_alias=AliasChoices("SMTP_USE_TLS"),
    )
    smtp_timeout_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices("SMTP_TIMEOUT_SECONDS"),
    )
    email_from_address: str = Field(
        default="noreply@stockpy.local",
        validation_alias=AliasChoices("EMAIL_FROM_ADDRESS"),
    )
    email_from_name: str = Field(
        default="StockPy",
        validation_alias=AliasChoices("EMAIL_FROM_NAME"),
    )
    telegram_bot_token: str = Field(
        default="",
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN"),
    )
    telegram_api_base_url: str = Field(
        default="https://api.telegram.org",
        validation_alias=AliasChoices("TELEGRAM_API_BASE_URL"),
    )
    object_storage_root: str = Field(
        default=".local/object-storage",
        validation_alias=AliasChoices("OBJECT_STORAGE_ROOT"),
    )
    object_storage_backend: str = Field(
        default="local",
        validation_alias=AliasChoices("OBJECT_STORAGE_BACKEND"),
    )
    object_storage_bucket: str = Field(
        default="stock-py",
        validation_alias=AliasChoices("OBJECT_STORAGE_BUCKET"),
    )
    object_storage_prefix: str = Field(
        default="",
        validation_alias=AliasChoices("OBJECT_STORAGE_PREFIX"),
    )
    object_storage_endpoint_url: str = Field(
        default="",
        validation_alias=AliasChoices("OBJECT_STORAGE_ENDPOINT_URL"),
    )
    object_storage_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("OBJECT_STORAGE_REGION"),
    )
    object_storage_access_key_id: str = Field(
        default="",
        validation_alias=AliasChoices("OBJECT_STORAGE_ACCESS_KEY_ID"),
    )
    object_storage_secret_access_key: str = Field(
        default="",
        validation_alias=AliasChoices("OBJECT_STORAGE_SECRET_ACCESS_KEY"),
    )
    object_storage_force_path_style: bool = Field(
        default=True,
        validation_alias=AliasChoices("OBJECT_STORAGE_FORCE_PATH_STYLE"),
    )
    analytics_backend: str = Field(
        default="local",
        validation_alias=AliasChoices("ANALYTICS_BACKEND"),
    )
    clickhouse_host: str = Field(
        default="",
        validation_alias=AliasChoices("CLICKHOUSE_HOST"),
    )
    clickhouse_port: int = Field(
        default=8123,
        validation_alias=AliasChoices("CLICKHOUSE_PORT"),
    )
    clickhouse_database: str = Field(
        default="default",
        validation_alias=AliasChoices("CLICKHOUSE_DATABASE"),
    )
    clickhouse_username: str = Field(
        default="default",
        validation_alias=AliasChoices("CLICKHOUSE_USERNAME"),
    )
    clickhouse_password: str = Field(
        default="",
        validation_alias=AliasChoices("CLICKHOUSE_PASSWORD"),
    )
    clickhouse_secure: bool = Field(
        default=False,
        validation_alias=AliasChoices("CLICKHOUSE_SECURE"),
    )
    clickhouse_verify_tls: bool = Field(
        default=True,
        validation_alias=AliasChoices("CLICKHOUSE_VERIFY_TLS"),
    )
    clickhouse_connect_timeout_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices("CLICKHOUSE_CONNECT_TIMEOUT_SECONDS"),
    )
    clickhouse_table_ttl_days: int = Field(
        default=180,
        validation_alias=AliasChoices("CLICKHOUSE_TABLE_TTL_DAYS"),
    )
    event_broker_backend: str = Field(
        default="redis",
        validation_alias=AliasChoices("EVENT_BROKER_BACKEND"),
    )
    event_broker_stream_name: str = Field(
        default="stock-py.events",
        validation_alias=AliasChoices("EVENT_BROKER_STREAM_NAME"),
    )
    event_broker_kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        validation_alias=AliasChoices("EVENT_BROKER_KAFKA_BOOTSTRAP_SERVERS"),
    )
    event_broker_kafka_topic: str = Field(
        default="stock-py.events",
        validation_alias=AliasChoices("EVENT_BROKER_KAFKA_TOPIC"),
    )
    event_broker_kafka_auto_offset_reset: str = Field(
        default="earliest",
        validation_alias=AliasChoices("EVENT_BROKER_KAFKA_AUTO_OFFSET_RESET"),
    )
    event_broker_group_name: str = Field(
        default="stock-py.dispatchers",
        validation_alias=AliasChoices("EVENT_BROKER_GROUP_NAME"),
    )
    event_broker_batch_size: int = Field(
        default=100,
        validation_alias=AliasChoices("EVENT_BROKER_BATCH_SIZE"),
    )
    event_broker_block_ms: int = Field(
        default=1000,
        validation_alias=AliasChoices("EVENT_BROKER_BLOCK_MS"),
    )
    event_broker_claim_idle_ms: int = Field(
        default=30000,
        validation_alias=AliasChoices("EVENT_BROKER_CLAIM_IDLE_MS"),
    )
    event_relay_poll_seconds: float = Field(
        default=1.0,
        validation_alias=AliasChoices("EVENT_RELAY_POLL_SECONDS"),
    )
    event_outbox_max_attempts: int = Field(
        default=3,
        validation_alias=AliasChoices("EVENT_OUTBOX_MAX_ATTEMPTS"),
    )
    retention_worker_poll_seconds: float = Field(
        default=3600.0,
        validation_alias=AliasChoices("RETENTION_WORKER_POLL_SECONDS"),
    )
    retention_cleanup_batch_size: int = Field(
        default=1000,
        validation_alias=AliasChoices("RETENTION_CLEANUP_BATCH_SIZE"),
    )
    retention_message_outbox_retention_days: int = Field(
        default=30,
        validation_alias=AliasChoices("RETENTION_MESSAGE_OUTBOX_RETENTION_DAYS"),
    )
    retention_message_receipt_archive_days: int = Field(
        default=60,
        validation_alias=AliasChoices("RETENTION_MESSAGE_RECEIPT_ARCHIVE_DAYS"),
    )
    retention_event_outbox_retention_days: int = Field(
        default=30,
        validation_alias=AliasChoices("RETENTION_EVENT_OUTBOX_RETENTION_DAYS"),
    )
    retention_partition_archive_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("RETENTION_PARTITION_ARCHIVE_ENABLED"),
    )
    retention_partition_archive_max_partitions_per_run: int = Field(
        default=6,
        validation_alias=AliasChoices("RETENTION_PARTITION_ARCHIVE_MAX_PARTITIONS_PER_RUN"),
    )
    retention_notification_partition_retention_days: int = Field(
        default=90,
        validation_alias=AliasChoices("RETENTION_NOTIFICATION_PARTITION_RETENTION_DAYS"),
    )
    retention_receipt_archive_partition_retention_days: int = Field(
        default=180,
        validation_alias=AliasChoices("RETENTION_RECEIPT_ARCHIVE_PARTITION_RETENTION_DAYS"),
    )
    retention_event_outbox_partition_retention_days: int = Field(
        default=90,
        validation_alias=AliasChoices("RETENTION_EVENT_OUTBOX_PARTITION_RETENTION_DAYS"),
    )
    retention_advisory_lock_key: int = Field(
        default=4_202_604,
        validation_alias=AliasChoices("RETENTION_ADVISORY_LOCK_KEY"),
    )
    runtime_metrics_window_minutes: int = Field(
        default=15,
        validation_alias=AliasChoices("RUNTIME_METRICS_WINDOW_MINUTES"),
    )
    runtime_alert_broker_lag_threshold: int = Field(
        default=200,
        validation_alias=AliasChoices("RUNTIME_ALERT_BROKER_LAG_THRESHOLD"),
    )
    runtime_alert_pgbouncer_waiting_clients_threshold: int = Field(
        default=10,
        validation_alias=AliasChoices("RUNTIME_ALERT_PGBOUNCER_WAITING_CLIENTS_THRESHOLD"),
    )
    runtime_alert_redis_memory_percent_threshold: float = Field(
        default=85.0,
        validation_alias=AliasChoices("RUNTIME_ALERT_REDIS_MEMORY_PERCENT_THRESHOLD"),
    )
    runtime_alert_clickhouse_write_failure_rate_threshold: float = Field(
        default=5.0,
        validation_alias=AliasChoices("RUNTIME_ALERT_CLICKHOUSE_WRITE_FAILURE_RATE_THRESHOLD"),
    )
    runtime_alert_object_storage_archive_failure_rate_threshold: float = Field(
        default=5.0,
        validation_alias=AliasChoices(
            "RUNTIME_ALERT_OBJECT_STORAGE_ARCHIVE_FAILURE_RATE_THRESHOLD"
        ),
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return ["*"]
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return ["*"]
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        raise TypeError("ALLOWED_ORIGINS must be a JSON array or comma-separated string")

    @field_validator("database_pool_mode", mode="before")
    @classmethod
    def _parse_database_pool_mode(cls, value: Any) -> str:
        normalized = str(value or "direct").strip().lower()
        if normalized not in {"direct", "pgbouncer"}:
            raise ValueError("DATABASE_POOL_MODE must be either 'direct' or 'pgbouncer'")
        return normalized

    @field_validator("event_broker_backend", mode="before")
    @classmethod
    def _parse_event_broker_backend(cls, value: Any) -> str:
        normalized = str(value or "redis").strip().lower()
        if normalized not in {"redis", "kafka"}:
            raise ValueError("EVENT_BROKER_BACKEND must be either 'redis' or 'kafka'")
        return normalized

    @field_validator("event_broker_kafka_auto_offset_reset", mode="before")
    @classmethod
    def _parse_event_broker_kafka_auto_offset_reset(cls, value: Any) -> str:
        normalized = str(value or "earliest").strip().lower()
        if normalized not in {"earliest", "latest"}:
            raise ValueError(
                "EVENT_BROKER_KAFKA_AUTO_OFFSET_RESET must be either 'earliest' or 'latest'"
            )
        return normalized

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
