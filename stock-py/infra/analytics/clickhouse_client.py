from __future__ import annotations

import asyncio
import json
import shlex
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Protocol

import httpx

from infra.core.config import get_settings
from infra.observability.external_operation_metrics import record_external_operation


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_table_name(table: str) -> str:
    normalized = table.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("table name is required")
    return normalized


def _partition_key_from_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m")


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return None


def _extract_timestamp(row: dict[str, Any]) -> Any:
    for key in (
        "occurred_at",
        "as_of_date",
        "created_at",
        "recorded_at",
        "started_at",
        "completed_at",
    ):
        if row.get(key) not in (None, ""):
            return row.get(key)
    return None


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    def normalize(value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, dict):
            return {str(key): normalize(inner) for key, inner in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [normalize(item) for item in value]
        return value

    normalized = {str(key): normalize(value) for key, value in row.items()}
    normalized.setdefault("recorded_at", _utcnow().isoformat())
    return normalized


def _partition_key_for_row(row: dict[str, Any]) -> str:
    timestamp = _parse_datetime(_extract_timestamp(row))
    if timestamp is None:
        timestamp = _utcnow()
    return _partition_key_from_datetime(timestamp)


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
    order_by: str | None = None,
    descending: bool = False,
    timestamp_field: str | None = None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if any(row.get(key) != value for key, value in (filters or {}).items()):
            continue
        row_timestamp = _parse_datetime(
            row.get(timestamp_field) if timestamp_field else _extract_timestamp(row)
        )
        if start_at is not None and row_timestamp is not None and row_timestamp < start_at:
            continue
        if end_at is not None and row_timestamp is not None and row_timestamp > end_at:
            continue
        filtered.append(row)

    if order_by:
        filtered.sort(key=lambda item: item.get(order_by), reverse=descending)
    if limit is not None:
        return filtered[:limit]
    return filtered


def _format_clickhouse_datetime(value: datetime | None) -> str:
    normalized = value or _utcnow()
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    normalized = normalized.astimezone(timezone.utc)
    return normalized.strftime("%Y-%m-%d %H:%M:%S.%f")


class ClickHouseBackend(Protocol):
    async def execute(
        self, statement: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...

    async def insert_rows(self, table: str, rows: Iterable[dict[str, Any]]) -> int: ...

    async def query_rows(
        self,
        table: str,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        descending: bool = False,
        timestamp_field: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def list_partitions(self, table: str) -> list[str]: ...

    async def ping(self) -> dict[str, Any]: ...


class LocalClickHouseBackend:
    def __init__(self, root_path: str | None = None) -> None:
        if root_path is None:
            root_path = str(Path(get_settings().object_storage_root) / "clickhouse")
        self.root = Path(root_path)

    def _table_path(self, table: str) -> Path:
        return (self.root / f"{_normalized_table_name(table)}.jsonl").resolve()

    def _table_directory(self, table: str) -> Path:
        return (self.root / _normalized_table_name(table)).resolve()

    def _partition_path(self, table: str, partition_key: str) -> Path:
        return (self._table_directory(table) / f"{partition_key}.jsonl").resolve()

    async def execute(
        self, statement: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del parameters
        tokens = shlex.split(statement)
        if len(tokens) >= 3 and tokens[0].lower() == "truncate" and tokens[1].lower() == "table":
            path = self._table_path(tokens[2])
            directory = self._table_directory(tokens[2])

            def _truncate() -> None:
                path.unlink(missing_ok=True)
                if directory.exists():
                    shutil.rmtree(directory)

            await asyncio.to_thread(_truncate)
            return {"ok": True, "statement": statement, "affected_rows": 0}
        return {"ok": True, "statement": statement}

    async def insert_rows(self, table: str, rows: Iterable[dict[str, Any]]) -> int:
        payload = [_normalize_row(row) for row in rows]
        if not payload:
            return 0
        batches: dict[Path, list[str]] = defaultdict(list)
        for row in payload:
            partition_key = _partition_key_for_row(row)
            batches[self._partition_path(table, partition_key)].append(
                json.dumps(row, separators=(",", ":"), ensure_ascii=False, default=str) + "\n"
            )

        def _append_batches() -> None:
            for path, lines in batches.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write("".join(lines))

        await asyncio.to_thread(_append_batches)
        return len(payload)

    async def query_rows(
        self,
        table: str,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        descending: bool = False,
        timestamp_field: str | None = None,
    ) -> list[dict[str, Any]]:
        paths = self._candidate_paths(table, start_at=start_at, end_at=end_at)
        if not paths:
            return []
        contents = await asyncio.gather(
            *(asyncio.to_thread(path.read_text, "utf-8") for path in paths)
        )
        rows = [
            json.loads(line)
            for content in contents
            for line in content.splitlines()
            if line.strip()
        ]
        return _filter_rows(
            rows,
            start_at=start_at,
            end_at=end_at,
            filters=filters,
            limit=limit,
            order_by=order_by,
            descending=descending,
            timestamp_field=timestamp_field,
        )

    async def list_partitions(self, table: str) -> list[str]:
        partitions = {
            path.stem
            for path in sorted(self._table_directory(table).glob("*.jsonl"))
            if path.is_file() and path.stem
        }
        legacy_path = self._table_path(table)
        if legacy_path.exists():
            content = await asyncio.to_thread(legacy_path.read_text, "utf-8")
            for line in content.splitlines():
                if not line.strip():
                    continue
                partitions.add(_partition_key_for_row(json.loads(line)))
        return sorted(partition for partition in partitions if partition)

    async def ping(self) -> dict[str, Any]:
        return {"ok": True, "backend": "local", "root": str(self.root)}

    def _candidate_paths(
        self,
        table: str,
        *,
        start_at: datetime | None,
        end_at: datetime | None,
    ) -> list[Path]:
        paths: list[Path] = []
        legacy_path = self._table_path(table)
        if legacy_path.exists():
            paths.append(legacy_path)

        table_directory = self._table_directory(table)
        if not table_directory.exists():
            return paths

        start_partition = _partition_key_from_datetime(start_at) if start_at else None
        end_partition = _partition_key_from_datetime(end_at) if end_at else None
        for path in sorted(table_directory.glob("*.jsonl")):
            partition_key = path.stem
            if start_partition is not None and partition_key < start_partition:
                continue
            if end_partition is not None and partition_key > end_partition:
                continue
            paths.append(path)
        return paths


class ClickHouseHttpBackend:
    _MISSING_ENTITY_EXCEPTION_CODES = {"60", "81"}
    _MISSING_ENTITY_MARKERS = (
        "UNKNOWN_TABLE",
        "UNKNOWN_DATABASE",
        "DOESN'T EXIST",
        "DOES NOT EXIST",
    )

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        username: str | None = None,
        password: str | None = None,
        secure: bool | None = None,
        verify_tls: bool | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.host = str(host if host is not None else settings.clickhouse_host).strip()
        self.port = int(port if port is not None else settings.clickhouse_port)
        self.database = str(database if database is not None else settings.clickhouse_database)
        self.username = str(username if username is not None else settings.clickhouse_username)
        self.password = str(password if password is not None else settings.clickhouse_password)
        self.secure = bool(settings.clickhouse_secure if secure is None else secure)
        self.verify_tls = bool(settings.clickhouse_verify_tls if verify_tls is None else verify_tls)
        self.timeout_seconds = float(
            settings.clickhouse_connect_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        self._initialized_tables: set[str] = set()

    @property
    def base_url(self) -> str:
        if self.host.startswith("http://") or self.host.startswith("https://"):
            return self.host.rstrip("/")
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.host}:{self.port}"

    async def execute(
        self, statement: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del parameters
        tokens = shlex.split(statement)
        if len(tokens) >= 3 and tokens[0].lower() == "truncate" and tokens[1].lower() == "table":
            table = _normalized_table_name(tokens[2])
            await self._post_query(f"TRUNCATE TABLE {table}")
            return {"ok": True, "statement": statement, "affected_rows": 0}
        await self._post_query(statement)
        return {"ok": True, "statement": statement}

    async def insert_rows(self, table: str, rows: Iterable[dict[str, Any]]) -> int:
        normalized_table = _normalized_table_name(table)
        payload = [_normalize_row(row) for row in rows]
        if not payload:
            return 0
        started_at = perf_counter()
        records = []
        for row in payload:
            event_at = _parse_datetime(_extract_timestamp(row)) or _utcnow()
            recorded_at = _parse_datetime(row.get("recorded_at")) or event_at
            records.append(
                {
                    "payload": json.dumps(row, separators=(",", ":"), ensure_ascii=False),
                    "event_at": _format_clickhouse_datetime(event_at),
                    "recorded_at": _format_clickhouse_datetime(recorded_at),
                    "partition_key": _partition_key_for_row(row),
                }
            )
        body = "\n".join(
            json.dumps(record, separators=(",", ":"), ensure_ascii=False) for record in records
        )
        try:
            await self._ensure_table(normalized_table)
            await self._post_query(
                f"INSERT INTO {normalized_table} (payload,event_at,recorded_at,partition_key) FORMAT JSONEachRow",
                content=body.encode("utf-8"),
            )
        except Exception as exc:
            await record_external_operation(
                "clickhouse",
                "insert_rows",
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=(perf_counter() - started_at) * 1000,
            )
            raise
        await record_external_operation(
            "clickhouse",
            "insert_rows",
            success=True,
            latency_ms=(perf_counter() - started_at) * 1000,
        )
        return len(records)

    async def query_rows(
        self,
        table: str,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        descending: bool = False,
        timestamp_field: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_table = _normalized_table_name(table)
        time_column = "recorded_at" if timestamp_field == "recorded_at" else "event_at"
        clauses = ["1 = 1"]
        if start_at is not None:
            clauses.append(
                f"{time_column} >= toDateTime64('{_format_clickhouse_datetime(start_at)}', 6, 'UTC')"
            )
        if end_at is not None:
            clauses.append(
                f"{time_column} <= toDateTime64('{_format_clickhouse_datetime(end_at)}', 6, 'UTC')"
            )
        query = (
            f"SELECT payload FROM {normalized_table} WHERE {' AND '.join(clauses)} "
            f"ORDER BY {time_column} {'DESC' if descending else 'ASC'} FORMAT JSONEachRow"
        )
        try:
            response_text = await self._post_query(query)
        except httpx.HTTPStatusError as exc:
            if self._is_missing_entity_error(exc):
                return []
            raise

        rows = []
        for line in response_text.splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            rows.append(json.loads(payload["payload"]))
        return _filter_rows(
            rows,
            start_at=start_at,
            end_at=end_at,
            filters=filters,
            limit=limit,
            order_by=order_by,
            descending=descending,
            timestamp_field=timestamp_field,
        )

    async def list_partitions(self, table: str) -> list[str]:
        normalized_table = _normalized_table_name(table)
        try:
            response_text = await self._post_query(
                f"SELECT DISTINCT partition_key FROM {normalized_table} "
                "ORDER BY partition_key FORMAT JSONEachRow"
            )
        except httpx.HTTPStatusError as exc:
            if self._is_missing_entity_error(exc):
                return []
            raise
        partitions: list[str] = []
        for line in response_text.splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            partition_key = str(payload.get("partition_key") or "")
            if partition_key:
                partitions.append(partition_key)
        return sorted(dict.fromkeys(partitions))

    async def _ensure_table(self, table: str) -> None:
        if table in self._initialized_tables:
            return
        ttl_days = max(int(get_settings().clickhouse_table_ttl_days), 0)
        ttl_clause = f" TTL recorded_at + INTERVAL {ttl_days} DAY" if ttl_days > 0 else ""
        await self._post_query(
            " ".join(
                (
                    f"CREATE TABLE IF NOT EXISTS {table}",
                    "(",
                    "payload String,",
                    "event_at DateTime64(6, 'UTC'),",
                    "recorded_at DateTime64(6, 'UTC'),",
                    "partition_key String",
                    ")",
                    "ENGINE = MergeTree()",
                    "PARTITION BY partition_key",
                    "ORDER BY (partition_key, event_at, recorded_at)",
                    ttl_clause,
                )
            )
        )
        self._initialized_tables.add(table)

    async def ping(self) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            verify=self.verify_tls,
            auth=(self.username, self.password) if self.username else None,
        ) as client:
            response = await client.get(f"{self.base_url}/ping")
            response.raise_for_status()
        return {"ok": True, "backend": "clickhouse", "database": self.database}

    async def _post_query(self, query: str, *, content: bytes | None = None) -> str:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            verify=self.verify_tls,
            auth=(self.username, self.password) if self.username else None,
        ) as client:
            response = await client.post(
                f"{self.base_url}/",
                params={"database": self.database, "query": query},
                content=content,
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
            response.raise_for_status()
            return response.text

    @staticmethod
    def _is_missing_entity_error(exc: httpx.HTTPStatusError) -> bool:
        response = exc.response
        if response is None:
            return False

        exception_code = str(response.headers.get("X-ClickHouse-Exception-Code", "")).strip()
        if exception_code in ClickHouseHttpBackend._MISSING_ENTITY_EXCEPTION_CODES:
            return True

        response_text = response.text.upper()
        return any(marker in response_text for marker in ClickHouseHttpBackend._MISSING_ENTITY_MARKERS)


class ClickHouseClient:
    def __init__(
        self,
        root_path: str | None = None,
        *,
        backend: str | None = None,
        backend_impl: ClickHouseBackend | None = None,
    ) -> None:
        selected_backend = str(backend or get_settings().analytics_backend).strip().lower()
        if backend_impl is not None:
            self.backend = selected_backend
            self.impl = backend_impl
        elif selected_backend == "clickhouse":
            self.backend = "clickhouse"
            self.impl = ClickHouseHttpBackend()
        else:
            self.backend = "local"
            self.impl = LocalClickHouseBackend(root_path=root_path)

    async def execute(
        self, statement: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self.impl.execute(statement, parameters=parameters)

    async def insert_rows(self, table: str, rows: Iterable[dict[str, Any]]) -> int:
        return await self.impl.insert_rows(table, rows)

    async def query_rows(
        self,
        table: str,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        descending: bool = False,
        timestamp_field: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self.impl.query_rows(
            table,
            start_at=start_at,
            end_at=end_at,
            filters=filters,
            limit=limit,
            order_by=order_by,
            descending=descending,
            timestamp_field=timestamp_field,
        )

    async def list_partitions(self, table: str) -> list[str]:
        return await self.impl.list_partitions(table)

    async def ping(self) -> dict[str, Any]:
        return await self.impl.ping()


@lru_cache(maxsize=1)
def get_clickhouse_client() -> ClickHouseClient:
    return ClickHouseClient()
