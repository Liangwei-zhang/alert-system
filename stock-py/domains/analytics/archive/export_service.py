from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from infra.analytics.clickhouse_client import ClickHouseClient

if TYPE_CHECKING:
    from infra.storage.object_storage import ObjectStorageClient


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ArchiveExportService:
    def __init__(
        self,
        client: ClickHouseClient,
        storage_client: ObjectStorageClient | None = None,
    ) -> None:
        self.client = client
        if storage_client is None:
            from infra.storage.object_storage import ObjectStorageClient

            storage_client = ObjectStorageClient()
        self.storage = storage_client

    async def export_partition(self, table: str, partition_key: str) -> dict[str, Any] | None:
        start_at, end_at = self._partition_window(partition_key)
        rows = await self.client.query_rows(table, start_at=start_at, end_at=end_at)
        matched = [row for row in rows if self._matches_partition(row, partition_key)]
        if not matched:
            return None
        object_key = await self.upload_to_object_storage(table, partition_key, matched)
        manifest = {
            "table": table,
            "partition_key": partition_key,
            "row_count": len(matched),
            "object_key": object_key,
            "exported_at": utcnow().isoformat(),
        }
        await self.storage.put_json(
            f"analytics-archive/{table}/{partition_key}/manifest.json", manifest
        )
        return manifest

    async def upload_to_object_storage(
        self, table: str, partition_key: str, rows: list[dict[str, Any]]
    ) -> str:
        body = "\n".join(
            json.dumps(row, separators=(",", ":"), ensure_ascii=False, default=str) for row in rows
        )
        compressed = gzip.compress(body.encode("utf-8"))
        key = f"analytics-archive/{table}/{partition_key}/rows.jsonl.gz"
        await self.storage.put_bytes(key, compressed)
        return key

    @staticmethod
    def _matches_partition(row: dict[str, Any], partition_key: str) -> bool:
        for key in ("occurred_at", "as_of_date", "recorded_at", "created_at"):
            value = row.get(key)
            if isinstance(value, str) and value.startswith(partition_key):
                return True
        return False

    @staticmethod
    def _partition_window(partition_key: str) -> tuple[datetime, datetime]:
        start_at = datetime.strptime(partition_key, "%Y-%m").replace(tzinfo=timezone.utc)
        if start_at.month == 12:
            next_month = start_at.replace(year=start_at.year + 1, month=1)
        else:
            next_month = start_at.replace(month=start_at.month + 1)
        return start_at, next_month - timedelta(microseconds=1)
